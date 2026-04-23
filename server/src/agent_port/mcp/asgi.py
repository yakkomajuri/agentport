import hashlib
import json
import logging
import uuid

import jwt
from sqlmodel import Session, select

from agent_port.config import settings
from agent_port.db import engine
from agent_port.dependencies import AgentAuth
from agent_port.mcp.server import RequestMeta, _current_auth, _current_request_meta, session_manager
from agent_port.models.api_key import ApiKey
from agent_port.models.oauth_revoked_token import OAuthRevokedToken
from agent_port.models.org import Org
from agent_port.models.org_membership import OrgMembership
from agent_port.models.user import User

logger = logging.getLogger(__name__)


def _extract_header(scope: dict, header_name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key.lower() == header_name:
            return value.decode("utf-8")
    return None


def _is_token_revoked(token: str) -> bool:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with Session(engine) as session:
        row = session.get(OAuthRevokedToken, token_hash)
        return row is not None


def _authenticate(scope: dict) -> AgentAuth | None:  # noqa: C901
    """Replicate get_agent_auth logic for raw ASGI scope.

    Bearer JWT (OAuth) is checked first so that clients sending both
    Authorization and X-Api-Key headers (e.g. Claude Code after OAuth) use
    the OAuth token rather than hitting the API-key path and failing.
    """
    # 1. Try Bearer JWT (checked before API key so OAuth tokens always win)
    auth_header = _extract_header(scope, b"authorization") or ""
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer ") :]
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
                options={"verify_aud": False},
            )
        except jwt.PyJWTError as exc:
            logger.warning("MCP auth: JWT decode failed: %s", exc)
            return None

        # Reject refresh tokens
        if payload.get("token_use") == "refresh":
            logger.warning("MCP auth: refresh token presented on MCP endpoint")
            return None

        # Reject purpose-specific tokens that must not authenticate MCP calls
        # (e.g. email-verification session handles).
        token_use = payload.get("token_use")
        if token_use == "email_verification":
            logger.warning("MCP auth: email-verification token presented on MCP endpoint")
            return None

        # Reject revoked tokens — covers both OAuth access tokens and admin
        # impersonation tokens (both go through the shared revocation list).
        if token_use in ("mcp_access", "access", "impersonation") and _is_token_revoked(token):
            logger.warning("MCP auth: token is revoked")
            return None

        user_id = payload.get("sub")
        if user_id is None:
            logger.warning("MCP auth: token missing 'sub' claim")
            return None

        # OAuth access tokens minted by _issue_access_token carry
        # token_use="mcp_access" and embed the grant's org_id. Legacy tokens
        # using the bare "access" label (human login JWTs) are handled by the
        # membership-lookup branch below.
        if token_use == "mcp_access":
            if payload.get("aud") != f"{settings.base_url}/mcp":
                logger.warning("MCP auth: mcp_access token has invalid audience")
                return None
            org_id = payload.get("org_id")
            if not org_id:
                logger.warning("MCP auth: access token missing 'org_id' claim")
                return None
            with Session(engine) as session:
                user = session.get(User, uuid.UUID(user_id))
                if user is None or not user.is_active:
                    logger.warning("MCP auth: user %s not found or inactive", user_id)
                    return None
                org = session.get(Org, uuid.UUID(org_id))
                if not org:
                    logger.warning("MCP auth: org %s not found", org_id)
                    return None
                membership = session.exec(
                    select(OrgMembership)
                    .where(OrgMembership.user_id == uuid.UUID(user_id))
                    .where(OrgMembership.org_id == uuid.UUID(org_id))
                ).first()
                if not membership:
                    logger.warning("MCP auth: no membership for user %s in org %s", user_id, org_id)
                    return None
                return AgentAuth(org=org, user=user, api_key=None)

        # Legacy JWTs (no token_use claim) and impersonation tokens both
        # resolve the target's org from membership. Impersonation tokens
        # additionally carry an `impersonator_sub` claim which we resolve
        # into the admin User row for audit tagging downstream.
        with Session(engine) as session:
            user = session.get(User, uuid.UUID(user_id))
            if user is None or not user.is_active:
                logger.warning("MCP auth: legacy JWT — user %s not found or inactive", user_id)
                return None
            membership = session.exec(
                select(OrgMembership).where(OrgMembership.user_id == user.id)
            ).first()
            if not membership:
                logger.warning("MCP auth: legacy JWT — no membership for user %s", user_id)
                return None
            org = session.get(Org, membership.org_id)
            if not org:
                logger.warning("MCP auth: legacy JWT — org not found for user %s", user_id)
                return None

            impersonator: User | None = None
            if token_use == "impersonation":
                imp_sub = payload.get("impersonator_sub")
                if imp_sub:
                    try:
                        admin = session.get(User, uuid.UUID(imp_sub))
                    except (ValueError, TypeError):
                        admin = None
                    if admin and admin.is_active and admin.is_admin:
                        impersonator = admin
            return AgentAuth(org=org, user=user, api_key=None, impersonator=impersonator)

    # 2. Try API key
    raw_key = _extract_header(scope, b"x-api-key")
    if raw_key:
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        with Session(engine) as session:
            api_key = session.exec(
                select(ApiKey).where(ApiKey.key_hash == key_hash).where(ApiKey.is_active == True)  # noqa: E712
            ).first()
            if not api_key:
                logger.warning("MCP auth: invalid API key")
                return None
            org = session.get(Org, api_key.org_id)
            if not org:
                logger.warning("MCP auth: org not found for API key")
                return None
            return AgentAuth(org=org, user=None, api_key=api_key)

    if not auth_header:
        logger.warning("MCP auth: no Authorization header")
    else:
        logger.warning(
            "MCP auth: Authorization header scheme is not Bearer (got %r)", auth_header[:40]
        )
    return None


async def _send_401(send):
    resource_metadata_url = f"{settings.base_url}/.well-known/oauth-protected-resource/mcp"
    body = json.dumps({"error": "Not authenticated"}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                [b"content-type", b"application/json"],
                [b"content-length", str(len(body)).encode()],
                [
                    b"www-authenticate",
                    f'Bearer resource_metadata="{resource_metadata_url}"'.encode(),
                ],
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def mcp_asgi_app(scope, receive, send):
    """Auth-aware ASGI app that wraps the MCP session manager."""
    if scope["type"] == "http":
        auth = _authenticate(scope)
        if auth is None:
            await _send_401(send)
            return

        client = scope.get("client")
        meta = RequestMeta(
            ip=client[0] if client else None,
            user_agent=_extract_header(scope, b"user-agent"),
        )
        auth_token = _current_auth.set(auth)
        meta_token = _current_request_meta.set(meta)
        try:
            await session_manager.handle_request(scope, receive, send)
        finally:
            _current_auth.reset(auth_token)
            _current_request_meta.reset(meta_token)
    else:
        # Non-HTTP scopes (lifespan, etc.) pass through
        await session_manager.handle_request(scope, receive, send)
