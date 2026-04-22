"""Shared OAuth start logic used by both the REST API and MCP management tools."""

import base64
import hashlib
import re
import secrets
import string
from datetime import datetime
from urllib.parse import urlencode, urlparse

import httpx
from mcp.client.auth.utils import (
    build_oauth_authorization_server_metadata_discovery_urls,
    build_protected_resource_metadata_discovery_urls,
    create_client_registration_request,
    create_oauth_metadata_request,
    handle_auth_metadata_response,
    handle_protected_resource_response,
    handle_registration_response,
)
from mcp.shared.auth import OAuthClientMetadata
from sqlmodel import Session, select

from agent_port.config import settings
from agent_port.integrations import registry
from agent_port.models.integration import InstalledIntegration
from agent_port.models.oauth import OAuthState
from agent_port.secrets.records import delete_secret, upsert_secret


def _pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) using S256."""
    code_verifier = "".join(
        secrets.choice(string.ascii_letters + string.digits + "-._~") for _ in range(128)
    )
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return code_verifier, code_challenge


def _extract_resource_metadata_url(response: httpx.Response) -> str | None:
    """Extract resource_metadata URL from WWW-Authenticate header (RFC 9728)."""
    www_auth = response.headers.get("WWW-Authenticate", "")
    match = re.search(r'resource_metadata=(?:"([^"]+)"|([^\s,]+))', www_auth)
    return (match.group(1) or match.group(2)) if match else None


def _set_pending_oauth_state(
    session: Session,
    *,
    oauth_state: OAuthState | None,
    org_id,
    integration_id: str,
    client_id: str,
    client_secret: str | None,
    token_endpoint: str,
    state_token: str,
    scope: str | None,
    resource: str | None,
    code_verifier: str,
) -> OAuthState:
    if oauth_state is None:
        oauth_state = OAuthState(org_id=org_id, integration_id=integration_id)
        session.add(oauth_state)
        session.flush()

    oauth_state.client_id = client_id
    oauth_state.token_endpoint = token_endpoint
    oauth_state.state = state_token
    oauth_state.scope = scope
    oauth_state.resource = resource
    oauth_state.code_verifier = code_verifier
    oauth_state.token_type = None
    oauth_state.expires_in = None
    oauth_state.obtained_at = None
    oauth_state.status = "pending"
    oauth_state.updated_at = datetime.utcnow()

    delete_secret(session, oauth_state.access_token_secret_id)
    oauth_state.access_token_secret_id = None
    delete_secret(session, oauth_state.refresh_token_secret_id)
    oauth_state.refresh_token_secret_id = None

    if client_secret:
        secret = upsert_secret(
            session,
            org_id=org_id,
            kind="integration_oauth_client_secret",
            ref=f"oauth/{org_id}/{integration_id}/client_secret",
            value=client_secret,
            secret_id=oauth_state.client_secret_secret_id,
        )
        oauth_state.client_secret_secret_id = secret.id
    else:
        delete_secret(session, oauth_state.client_secret_secret_id)
        oauth_state.client_secret_secret_id = None

    session.add(oauth_state)
    return oauth_state


async def _start_configured_oauth(
    integration_id: str,
    oauth_auth,
    session: Session,
    org,
) -> dict:
    """Start OAuth flow for a pre-configured provider (e.g. Google)."""
    credentials = settings.get_oauth_credentials(oauth_auth.provider)
    if not credentials:
        raise ValueError(
            f"OAuth credentials not configured for provider '{oauth_auth.provider}'. "
            f"Set OAUTH_{oauth_auth.provider.upper()}_CLIENT_ID and "
            f"OAUTH_{oauth_auth.provider.upper()}_CLIENT_SECRET."
        )

    client_id, client_secret = credentials
    state_token = secrets.token_urlsafe(32)
    code_verifier, code_challenge = _pkce_pair()
    scope = " ".join(oauth_auth.scopes) if oauth_auth.scopes else None

    oauth_state = session.exec(
        select(OAuthState)
        .where(OAuthState.org_id == org.id)
        .where(OAuthState.integration_id == integration_id)
    ).first()

    _set_pending_oauth_state(
        session,
        oauth_state=oauth_state,
        org_id=org.id,
        integration_id=integration_id,
        client_id=client_id,
        client_secret=client_secret,
        token_endpoint=oauth_auth.token_url,
        state_token=state_token,
        scope=scope,
        resource=None,
        code_verifier=code_verifier,
    )
    session.commit()

    auth_params: dict[str, str] = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": settings.oauth_callback_url,
        "state": state_token,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    if scope:
        auth_params[oauth_auth.scope_param] = scope
    auth_params.update(oauth_auth.extra_auth_params)

    return {
        "authorization_url": f"{oauth_auth.authorization_url}?{urlencode(auth_params)}",
        "state": state_token,
    }


async def start_oauth_for_installed(
    session: Session,
    installed: InstalledIntegration,
    org,
) -> dict:
    """Start the OAuth flow for an installed integration.

    Returns {"authorization_url": str, "state": str}.
    Raises ValueError on configuration errors, httpx errors on network failures.
    """
    integration_id = installed.integration_id

    # Check for pre-configured OAuth (e.g. Google) — skip MCP discovery
    bundled = registry.get(installed.integration_id)
    if bundled:
        oauth_auth = next((a for a in bundled.auth if a.method == "oauth"), None)
        if oauth_auth and oauth_auth.provider:
            return await _start_configured_oauth(integration_id, oauth_auth, session, org)

    # MCP discovery flow
    state_token = secrets.token_urlsafe(32)
    code_verifier, code_challenge = _pkce_pair()
    server_url = installed.url

    async with httpx.AsyncClient(follow_redirects=True) as http:
        # Step 1: Probe MCP endpoint to get WWW-Authenticate resource_metadata hint
        www_auth_resource_url: str | None = None
        try:
            probe = await http.get(server_url, headers={"Accept": "application/json"})
            if probe.status_code == 401:
                www_auth_resource_url = _extract_resource_metadata_url(probe)
        except Exception:
            pass

        # Step 2: Discover Protected Resource Metadata (RFC 9728)
        prm_urls = build_protected_resource_metadata_discovery_urls(
            www_auth_resource_url, server_url
        )
        auth_server_url: str | None = None
        scope: str | None = None
        prm = None
        for url in prm_urls:
            try:
                resp = await http.send(create_oauth_metadata_request(url))
                prm = await handle_protected_resource_response(resp)
                if prm:
                    auth_server_url = str(prm.authorization_servers[0])
                    if prm.scopes_supported:
                        scope = " ".join(prm.scopes_supported)
                    break
            except Exception:
                continue

        # Step 3: Discover OAuth Authorization Server Metadata (RFC 8414)
        asm_urls = build_oauth_authorization_server_metadata_discovery_urls(
            auth_server_url, server_url
        )
        asm = None
        for url in asm_urls:
            try:
                resp = await http.send(create_oauth_metadata_request(url))
                ok, asm = await handle_auth_metadata_response(resp)
                if asm:
                    if scope is None and asm.scopes_supported:
                        scope = " ".join(asm.scopes_supported)
                    break
                if not ok:
                    break
            except Exception:
                continue

        if not asm or not asm.authorization_endpoint or not asm.token_endpoint:
            raise ValueError("Failed to discover OAuth endpoints for this integration")

        authorization_endpoint = str(asm.authorization_endpoint)
        token_endpoint = str(asm.token_endpoint)

        # Step 4: Dynamic Client Registration
        oauth_state = session.exec(
            select(OAuthState)
            .where(OAuthState.org_id == org.id)
            .where(OAuthState.integration_id == integration_id)
        ).first()

        client_metadata = OAuthClientMetadata(
            redirect_uris=[settings.oauth_callback_url],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            client_name="AgentPort",
            token_endpoint_auth_method="none",
        )
        parsed = urlparse(server_url)
        auth_base_url = f"{parsed.scheme}://{parsed.netloc}"
        reg_request = create_client_registration_request(asm, client_metadata, auth_base_url)
        try:
            reg_resp = await http.send(reg_request)
            client_info = await handle_registration_response(reg_resp)
            client_id = client_info.client_id
            client_secret = client_info.client_secret
        except Exception as exc:
            raise ValueError(f"Client registration failed: {exc}") from exc

    if not client_id:
        raise ValueError("Client registration did not return a client_id")

    resource_url: str | None = None
    if prm and prm.resource:
        resource_url = str(prm.resource)

    _set_pending_oauth_state(
        session,
        oauth_state=oauth_state,
        org_id=org.id,
        integration_id=integration_id,
        client_id=client_id,
        client_secret=client_secret,
        token_endpoint=token_endpoint,
        state_token=state_token,
        scope=scope,
        resource=resource_url,
        code_verifier=code_verifier,
    )
    session.commit()

    auth_params: dict[str, str] = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": settings.oauth_callback_url,
        "state": state_token,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    if resource_url:
        auth_params["resource"] = resource_url
    if scope:
        auth_params["scope"] = scope

    return {
        "authorization_url": f"{authorization_endpoint}?{urlencode(auth_params)}",
        "state": state_token,
    }
