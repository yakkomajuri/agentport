import logging
import secrets
from datetime import datetime
from urllib.parse import quote

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from agent_port.auth_start import start_oauth_for_installed
from agent_port.config import settings
from agent_port.db import get_session
from agent_port.dependencies import AgentAuth, get_agent_auth
from agent_port.mcp.refresh import refresh_one
from agent_port.models.integration import InstalledIntegration
from agent_port.models.oauth import OAuthState
from agent_port.secrets.records import delete_secret, get_secret_value, upsert_secret

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _store_oauth_tokens(
    session: Session,
    *,
    oauth_state: OAuthState,
    token_payload: dict,
) -> None:
    # Slack v2 user OAuth nests the user token under authed_user
    authed_user = token_payload.get("authed_user", {})
    access_token = token_payload.get("access_token") or authed_user.get("access_token")
    refresh_token = token_payload.get("refresh_token") or authed_user.get("refresh_token")
    oauth_state.token_type = token_payload.get("token_type") or authed_user.get("token_type")
    expires_in = token_payload.get("expires_in")
    oauth_state.expires_in = int(expires_in) if expires_in is not None else None
    oauth_state.obtained_at = datetime.utcnow()
    oauth_state.status = "connected"
    oauth_state.updated_at = datetime.utcnow()

    if access_token:
        secret = upsert_secret(
            session,
            org_id=oauth_state.org_id,
            kind="integration_oauth_access_token",
            ref=f"oauth/{oauth_state.org_id}/{oauth_state.integration_id}/access_token",
            value=access_token,
            secret_id=oauth_state.access_token_secret_id,
        )
        oauth_state.access_token_secret_id = secret.id
    else:
        delete_secret(session, oauth_state.access_token_secret_id)
        oauth_state.access_token_secret_id = None

    if refresh_token:
        secret = upsert_secret(
            session,
            org_id=oauth_state.org_id,
            kind="integration_oauth_refresh_token",
            ref=f"oauth/{oauth_state.org_id}/{oauth_state.integration_id}/refresh_token",
            value=refresh_token,
            secret_id=oauth_state.refresh_token_secret_id,
        )
        oauth_state.refresh_token_secret_id = secret.id
    else:
        delete_secret(session, oauth_state.refresh_token_secret_id)
        oauth_state.refresh_token_secret_id = None

    session.add(oauth_state)


@router.post("/{integration_id}/start")
async def start_oauth(
    integration_id: str,
    session: Session = Depends(get_session),
    agent_auth: AgentAuth = Depends(get_agent_auth),
) -> dict:
    installed = session.exec(
        select(InstalledIntegration)
        .where(InstalledIntegration.org_id == agent_auth.org.id)
        .where(InstalledIntegration.integration_id == integration_id)
    ).first()
    if not installed:
        raise HTTPException(
            status_code=404,
            detail=f"Installed integration '{integration_id}' not found",
        )
    if installed.auth_method != "oauth":
        raise HTTPException(status_code=400, detail="Integration is not configured for OAuth")
    try:
        return await start_oauth_for_installed(session, installed, agent_auth.org)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/callback")
async def oauth_callback(
    state: str,
    background_tasks: BackgroundTasks,
    code: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    # Find the pending OAuth flow matching this state token
    stmt = select(OAuthState).where(OAuthState.status == "pending")
    pending = session.exec(stmt).all()

    oauth_state = None
    for s in pending:
        stored_state = s.state or ""
        if stored_state and secrets.compare_digest(stored_state, state):
            oauth_state = s
            break

    if not oauth_state:
        raise HTTPException(status_code=400, detail="No matching OAuth flow found for this state")

    if error:
        detail = error_description or error
        _remove_installed(session, oauth_state.org_id, oauth_state.integration_id)
        raise HTTPException(status_code=400, detail=f"OAuth authorization failed: {detail}")
    if not code:
        _remove_installed(session, oauth_state.org_id, oauth_state.integration_id)
        raise HTTPException(status_code=400, detail="Missing authorization code")

    token_endpoint = oauth_state.token_endpoint
    client_id = oauth_state.client_id
    client_secret = get_secret_value(session, oauth_state.client_secret_secret_id)
    resource = oauth_state.resource
    if not token_endpoint or not client_id:
        _remove_installed(session, oauth_state.org_id, oauth_state.integration_id)
        raise HTTPException(status_code=400, detail="Stored OAuth state is incomplete")

    token_data: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.oauth_callback_url,
        "client_id": client_id,
        "code_verifier": oauth_state.code_verifier,
    }
    if resource:
        token_data["resource"] = resource
    if client_secret:
        token_data["client_secret"] = client_secret

    async with httpx.AsyncClient() as http:
        resp = await http.post(
            token_endpoint,
            data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if not resp.is_success:
        logger.warning(
            "OAuth token exchange failed for %s (HTTP %s): %s",
            oauth_state.integration_id,
            resp.status_code,
            resp.text,
        )
        _remove_installed(session, oauth_state.org_id, oauth_state.integration_id)
        raise HTTPException(
            status_code=502,
            detail="OAuth token exchange failed. Please try connecting the integration again.",
        )

    token_payload = resp.json()
    _store_oauth_tokens(session, oauth_state=oauth_state, token_payload=token_payload)

    installed = session.exec(
        select(InstalledIntegration)
        .where(InstalledIntegration.org_id == oauth_state.org_id)
        .where(InstalledIntegration.integration_id == oauth_state.integration_id)
    ).first()
    if installed:
        installed.connected = True
        session.add(installed)

    session.commit()

    if installed:
        background_tasks.add_task(refresh_one, installed.org_id, installed.integration_id)

    integration_path = quote(oauth_state.integration_id, safe="")
    return RedirectResponse(
        url=f"{settings.ui_base_url}/integrations/{integration_path}",
        status_code=302,
    )


def _remove_installed(session: Session, org_id, integration_id: str) -> None:
    """Remove the InstalledIntegration so the UI no longer shows 'Connected'."""
    installed = session.exec(
        select(InstalledIntegration)
        .where(InstalledIntegration.org_id == org_id)
        .where(InstalledIntegration.integration_id == integration_id)
    ).first()
    if installed:
        oauth_state = session.exec(
            select(OAuthState)
            .where(OAuthState.org_id == org_id)
            .where(OAuthState.integration_id == integration_id)
        ).first()
        if oauth_state:
            delete_secret(session, oauth_state.client_secret_secret_id)
            delete_secret(session, oauth_state.access_token_secret_id)
            delete_secret(session, oauth_state.refresh_token_secret_id)
            session.delete(oauth_state)
        if installed.auth_method == "token":
            delete_secret(session, installed.token_secret_id)
        session.delete(installed)
        session.commit()
