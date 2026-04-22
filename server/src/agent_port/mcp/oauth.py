import logging
from datetime import datetime, timedelta

import httpx
from sqlmodel import Session

from agent_port.db import engine
from agent_port.models.oauth import OAuthState
from agent_port.secrets.records import get_secret_value, upsert_secret

logger = logging.getLogger(__name__)

_EXPIRY_BUFFER = timedelta(seconds=60)


def is_token_expired(oauth_state: OAuthState) -> bool:
    """Return True if the access token is known to be expired (or expiring within 60s)."""
    if not oauth_state.obtained_at or not oauth_state.expires_in:
        return False
    expires_at = oauth_state.obtained_at + timedelta(seconds=int(oauth_state.expires_in))
    return datetime.utcnow() >= expires_at - _EXPIRY_BUFFER


def is_auth_error(e: BaseException, _seen: set | None = None) -> bool:
    """Return True if the exception chain/group contains a 401 or 403."""
    if _seen is None:
        _seen = set()
    eid = id(e)
    if eid in _seen:
        return False
    _seen.add(eid)

    if isinstance(e, httpx.HTTPStatusError) and e.response.status_code in (401, 403):
        return True
    if isinstance(e, BaseExceptionGroup):
        if any(is_auth_error(sub, _seen) for sub in e.exceptions):
            return True
    for chained in (e.__cause__, e.__context__):
        if chained and chained is not e and is_auth_error(chained, _seen):
            return True
    return False


async def refresh_tokens(oauth_state: OAuthState) -> OAuthState | None:
    """Attempt a refresh_token grant.

    Persists new tokens and returns updated OAuthState, or None on failure.
    """
    with Session(engine) as session:
        refresh_token = get_secret_value(session, oauth_state.refresh_token_secret_id)
        client_secret = get_secret_value(session, oauth_state.client_secret_secret_id)
    token_endpoint = oauth_state.token_endpoint
    client_id = oauth_state.client_id
    resource = oauth_state.resource
    if not refresh_token or not token_endpoint or not client_id:
        return None

    token_data: dict[str, str] = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }
    if client_secret:
        token_data["client_secret"] = client_secret
    if resource:
        token_data["resource"] = resource

    try:
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                token_endpoint,
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
    except Exception as exc:
        logger.warning("Token refresh HTTP request failed: %s", exc)
        return None

    if resp.status_code != 200:
        logger.warning("Token refresh failed (%s): %s", resp.status_code, resp.text)
        return None

    new_tokens = resp.json()

    with Session(engine) as session:
        state = session.get(OAuthState, oauth_state.id)
        if not state:
            return None
        access_token = new_tokens.get("access_token")
        if not access_token:
            logger.warning("Token refresh succeeded without an access_token")
            return None
        access_secret = upsert_secret(
            session,
            org_id=state.org_id,
            kind="integration_oauth_access_token",
            ref=f"oauth/{state.org_id}/{state.integration_id}/access_token",
            value=access_token,
            secret_id=state.access_token_secret_id,
        )
        state.access_token_secret_id = access_secret.id
        refreshed_token = new_tokens.get("refresh_token")
        if refreshed_token:
            refresh_secret = upsert_secret(
                session,
                org_id=state.org_id,
                kind="integration_oauth_refresh_token",
                ref=f"oauth/{state.org_id}/{state.integration_id}/refresh_token",
                value=refreshed_token,
                secret_id=state.refresh_token_secret_id,
            )
            state.refresh_token_secret_id = refresh_secret.id
        state.token_type = new_tokens.get("token_type", state.token_type)
        expires_in = new_tokens.get("expires_in")
        state.expires_in = int(expires_in) if expires_in is not None else state.expires_in
        state.obtained_at = datetime.utcnow()
        state.status = "connected"
        state.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(state)
        session.expunge(state)
        return state
