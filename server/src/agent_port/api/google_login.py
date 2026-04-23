"""Google sign-in for agent-port users.

This is completely independent from the Google integration OAuth flow. Its only
job is to let a user authenticate into agent-port using their Google account.

Flow:
    1. UI calls GET /api/auth/google/login → server stores a pending state row
       and returns a Google authorization URL.
    2. UI redirects the browser to Google.
    3. Google redirects to GET /api/auth/google/callback?code&state.
    4. Server exchanges the code, reads userinfo, upserts a user, mints a JWT,
       and redirects to `${ui_base_url}/login/google/callback#access_token=...`.
       The UI page reads the hash fragment, stores the token, and continues.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import string
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlmodel import Session, func, select

from agent_port.analytics import posthog_client
from agent_port.auth_tokens import create_access_token
from agent_port.config import settings
from agent_port.db import get_session
from agent_port.email import normalize_email
from agent_port.models.google_login_state import GoogleLoginState
from agent_port.models.instance_settings import InstanceSettings
from agent_port.models.org import Org
from agent_port.models.org_membership import OrgMembership
from agent_port.models.user import User
from agent_port.models.waitlist import Waitlist

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth/google", tags=["google-login"])

GOOGLE_AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_SCOPE = "openid email profile"

# Pending login rows older than this are swept on callback; anything older is
# almost certainly an abandoned flow.
STATE_TTL = timedelta(minutes=15)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _pkce_pair() -> tuple[str, str]:
    verifier = "".join(
        secrets.choice(string.ascii_letters + string.digits + "-._~") for _ in range(96)
    )
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def _callback_url() -> str:
    return f"{settings.base_url.rstrip('/')}/api/auth/google/callback"


def _require_configured() -> None:
    if not settings.google_login_client_id or not settings.google_login_client_secret:
        raise HTTPException(
            status_code=503,
            detail="Google login is not configured on this server.",
        )


def _sweep_expired(session: Session) -> None:
    cutoff = _utcnow() - STATE_TTL
    for row in session.exec(
        select(GoogleLoginState).where(GoogleLoginState.created_at < cutoff)
    ).all():
        session.delete(row)


def _ui_redirect_with_error(error_code: str) -> RedirectResponse:
    url = f"{settings.ui_base_url.rstrip('/')}/login?google_error={quote(error_code)}"
    return RedirectResponse(url=url, status_code=302)


def _ui_redirect_with_token(token: str) -> RedirectResponse:
    # Hash fragment keeps the token out of server logs / Referer headers while
    # still being readable by the client-side callback page.
    url = (
        f"{settings.ui_base_url.rstrip('/')}/login/google/callback"
        f"#access_token={quote(token)}&token_type=bearer"
    )
    return RedirectResponse(url=url, status_code=302)


async def _exchange_code(code: str, code_verifier: str) -> dict:
    async with httpx.AsyncClient() as http:
        resp = await http.post(
            GOOGLE_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": settings.google_login_client_id,
                "client_secret": settings.google_login_client_secret,
                "redirect_uri": _callback_url(),
                "code_verifier": code_verifier,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if not resp.is_success:
        logger.warning("Google token exchange failed (HTTP %s): %s", resp.status_code, resp.text)
        raise HTTPException(status_code=502, detail="Google token exchange failed")
    return resp.json()


async def _fetch_userinfo(access_token: str) -> dict:
    async with httpx.AsyncClient() as http:
        resp = await http.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if not resp.is_success:
        logger.warning("Google userinfo fetch failed (HTTP %s): %s", resp.status_code, resp.text)
        raise HTTPException(status_code=502, detail="Failed to read Google userinfo")
    return resp.json()


def _find_or_create_user(session: Session, *, sub: str, email: str, email_verified: bool) -> User:
    """Look up the user by Google sub, then by email. Create one if needed."""
    email = normalize_email(email)

    user = session.exec(select(User).where(User.google_sub == sub)).first()
    if user:
        if user.email != email:
            # Google is authoritative for their own accounts — keep our email
            # in sync if the Google account's email changes.
            user.email = email
            session.add(user)
        if not user.email_verified and email_verified:
            user.email_verified = True
            session.add(user)
        return user

    user = session.exec(select(User).where(User.email == email)).first()
    if user:
        # Existing local account with the same email — only link if Google
        # actually vouched for the email. Otherwise this is an account-takeover
        # primitive: any attacker-controlled Google identity that emits the
        # victim's email with email_verified=false would silently bind its
        # `sub` to the victim's row, and every subsequent Google sign-in by
        # that `sub` would authenticate as the victim.
        if not email_verified:
            raise HTTPException(status_code=403, detail="email_not_verified_by_idp")
        user.google_sub = sub
        if not user.email_verified:
            user.email_verified = True
        session.add(user)
        return user

    instance = session.get(InstanceSettings, 1)
    if instance and instance.waitlist_enabled:
        approved = session.exec(select(Waitlist).where(Waitlist.email == email)).first()
        if not approved:
            raise HTTPException(status_code=403, detail="Email not on waitlist.")

    if settings.block_signups:
        raise HTTPException(status_code=403, detail="Signups are disabled")
    is_first_self_hosted_user = False
    if settings.is_self_hosted:
        org_count = session.exec(select(func.count()).select_from(Org)).one()
        if org_count >= 1:
            raise HTTPException(
                status_code=409,
                detail="Server already has an organization (IS_SELF_HOSTED=true)",
            )
        is_first_self_hosted_user = True

    user = User(
        email=email,
        hashed_password=None,
        google_sub=sub,
        email_verified=email_verified or settings.skip_email_verification,
        is_admin=is_first_self_hosted_user,
    )
    org = Org(name=f"{email}'s organization")
    session.add(user)
    session.add(org)
    session.flush()

    session.add(OrgMembership(user_id=user.id, org_id=org.id, role="owner"))
    return user


@router.get("/login")
def start_google_login(session: Session = Depends(get_session)) -> dict:
    """Begin a Google sign-in flow. Returns the authorization URL."""
    _require_configured()
    _sweep_expired(session)

    state = secrets.token_urlsafe(32)
    code_verifier, code_challenge = _pkce_pair()

    session.add(GoogleLoginState(state=state, code_verifier=code_verifier))
    session.commit()

    params = {
        "response_type": "code",
        "client_id": settings.google_login_client_id,
        "redirect_uri": _callback_url(),
        "scope": GOOGLE_SCOPE,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "access_type": "online",
        "prompt": "select_account",
    }
    return {"authorization_url": f"{GOOGLE_AUTHORIZATION_URL}?{urlencode(params)}"}


@router.get("/callback")
async def google_login_callback(
    state: str,
    code: str | None = None,
    error: str | None = None,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Google redirects here after the user approves (or denies)."""
    _require_configured()

    pending = session.exec(select(GoogleLoginState).where(GoogleLoginState.state == state)).first()
    if not pending:
        return _ui_redirect_with_error("invalid_state")

    # One-time: delete the row regardless of outcome.
    code_verifier = pending.code_verifier
    session.delete(pending)
    session.commit()

    if error or not code:
        logger.info("Google login aborted: %s", error or "missing_code")
        return _ui_redirect_with_error(error or "missing_code")

    token_payload = await _exchange_code(code, code_verifier)
    access_token = token_payload.get("access_token")
    if not access_token:
        return _ui_redirect_with_error("token_exchange_failed")

    info = await _fetch_userinfo(access_token)
    sub = info.get("sub")
    email = info.get("email")
    email_verified = bool(info.get("email_verified", False))
    if not sub or not email:
        return _ui_redirect_with_error("missing_profile")

    try:
        user = _find_or_create_user(
            session, sub=str(sub), email=str(email), email_verified=email_verified
        )
    except HTTPException as exc:
        session.rollback()
        logger.info("Google login rejected: %s", exc.detail)
        if exc.status_code == 403 and exc.detail == "Email not on waitlist.":
            return _ui_redirect_with_error("not_on_waitlist")
        if exc.status_code == 403 and exc.detail == "email_not_verified_by_idp":
            return _ui_redirect_with_error("email_not_verified_by_idp")
        if exc.status_code == 403:
            return _ui_redirect_with_error("signups_disabled")
        if exc.status_code == 409:
            return _ui_redirect_with_error("self_hosted_org_exists")
        return _ui_redirect_with_error("login_failed")

    if not user.is_active:
        session.rollback()
        return _ui_redirect_with_error("account_disabled")

    session.commit()

    jwt_token = create_access_token(str(user.id))
    posthog_client.capture(
        distinct_id=str(user.id),
        event="user_logged_in",
        properties={"auth_method": "google"},
    )
    return _ui_redirect_with_token(jwt_token)


__all__ = ["router"]
