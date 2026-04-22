"""Instance-admin management endpoints.

All routes require is_admin=True on the current user. IS_CLOUD gating is a
UI concern — the backend always exposes these endpoints to admins so a
self-hoster can still manage the waitlist via direct API calls if they want.
"""

import hashlib
import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlmodel import Session, select

from agent_port.analytics import posthog_client
from agent_port.auth_tokens import create_access_token, create_impersonation_token
from agent_port.config import settings
from agent_port.db import get_session
from agent_port.dependencies import get_impersonator, require_admin
from agent_port.email import normalize_email
from agent_port.models.instance_settings import InstanceSettings
from agent_port.models.oauth_revoked_token import OAuthRevokedToken
from agent_port.models.user import User
from agent_port.models.waitlist import Waitlist

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Reused to extract the raw bearer for revocation on stop_impersonation.
# OAuth2PasswordBearer raises 401 if the header is missing, which is the
# right behaviour for stop.
_impersonation_bearer = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def _get_instance_settings(session: Session) -> InstanceSettings:
    row = session.get(InstanceSettings, 1)
    if row is None:
        row = InstanceSettings(id=1, waitlist_enabled=False)
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


class InstanceSettingsResponse(BaseModel):
    waitlist_enabled: bool


class UpdateInstanceSettingsRequest(BaseModel):
    waitlist_enabled: bool


@router.get("/settings", response_model=InstanceSettingsResponse)
def get_settings(
    session: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
) -> InstanceSettingsResponse:
    row = _get_instance_settings(session)
    return InstanceSettingsResponse(waitlist_enabled=row.waitlist_enabled)


@router.patch("/settings", response_model=InstanceSettingsResponse)
def update_settings(
    body: UpdateInstanceSettingsRequest,
    session: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
) -> InstanceSettingsResponse:
    row = _get_instance_settings(session)
    row.waitlist_enabled = body.waitlist_enabled
    session.add(row)
    session.commit()
    return InstanceSettingsResponse(waitlist_enabled=row.waitlist_enabled)


class WaitlistEntryResponse(BaseModel):
    id: uuid.UUID
    email: str
    added_at: datetime


class AddWaitlistEmailRequest(BaseModel):
    email: str


@router.get("/waitlist", response_model=list[WaitlistEntryResponse])
def list_waitlist(
    session: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
) -> list[WaitlistEntryResponse]:
    rows = session.exec(select(Waitlist).order_by(Waitlist.added_at.desc())).all()  # type: ignore[arg-type]
    return [WaitlistEntryResponse(id=r.id, email=r.email, added_at=r.added_at) for r in rows]


@router.post("/waitlist", response_model=WaitlistEntryResponse, status_code=201)
def add_waitlist_email(
    body: AddWaitlistEmailRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
) -> WaitlistEntryResponse:
    email = normalize_email(body.email)
    existing = session.exec(select(Waitlist).where(Waitlist.email == email)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already on waitlist")
    entry = Waitlist(email=email, added_by_user_id=admin.id)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return WaitlistEntryResponse(id=entry.id, email=entry.email, added_at=entry.added_at)


@router.delete("/waitlist/{entry_id}", status_code=204)
def remove_waitlist_email(
    entry_id: uuid.UUID,
    session: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
) -> None:
    entry = session.get(Waitlist, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Waitlist entry not found")
    session.delete(entry)
    session.commit()


class AdminUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    is_admin: bool
    is_active: bool
    created_at: datetime


@router.get("/users", response_model=list[AdminUserResponse])
def list_users(
    q: str | None = None,
    limit: int = 50,
    session: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
) -> list[AdminUserResponse]:
    limit = max(1, min(limit, 200))
    stmt = select(User)
    if q:
        stmt = stmt.where(User.email.ilike(f"%{q.strip()}%"))  # type: ignore[attr-defined]
    stmt = stmt.order_by(User.email).limit(limit)  # type: ignore[arg-type]
    rows = session.exec(stmt).all()
    return [
        AdminUserResponse(
            id=u.id,
            email=u.email,
            is_admin=u.is_admin,
            is_active=u.is_active,
            created_at=u.created_at,
        )
        for u in rows
    ]


# ─── Impersonation ────────────────────────────────────────────────────────────
# Admin support workflow: temporarily act as another user to reproduce a bug
# or walk through a problem with them. Tokens are deliberately short-lived,
# revocable, and every action taken under them is tagged with the admin's id
# in LogEntry.impersonator_user_id for audit.


class ImpersonateResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    target_user_id: str
    target_email: str


class StopImpersonationResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _revoke_bearer(token: str, session: Session) -> None:
    """Record the bearer token's hash so subsequent auth checks reject it.

    We hash with sha256 (same helper as OAuth revocation) so the plaintext
    token never sits at rest. `expires_at` is kept around so a future
    cleanup job can prune rows whose TTL has already lapsed."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    if session.get(OAuthRevokedToken, token_hash) is not None:
        return
    expires_at = int(time.time()) + settings.impersonation_ttl_minutes * 60
    session.add(OAuthRevokedToken(token_hash=token_hash, expires_at=expires_at))
    session.commit()


# NOTE: Declaration order matters — /impersonate/stop must be registered
# before /impersonate/{user_id} or Starlette will match "stop" as a
# user_id path parameter.


@router.post("/impersonate/stop", response_model=StopImpersonationResponse)
def stop_impersonation(
    token: str = Depends(_impersonation_bearer),
    session: Session = Depends(get_session),
) -> StopImpersonationResponse:
    """Revoke the current impersonation bearer and mint a fresh admin token.

    Accepts the impersonation bearer directly (no get_current_user dep)
    because the token's `sub` is the target user — not the admin — and the
    admin is who we want to return a fresh session to. The admin is
    recovered from the `impersonator_sub` claim."""
    import jwt as _jwt

    try:
        payload = _jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_aud": False},
        )
    except _jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    if payload.get("token_use") != "impersonation":
        raise HTTPException(
            status_code=400,
            detail={
                "error": "not_impersonating",
                "message": "The current token is not an impersonation token.",
            },
        )

    # Revocation is best-effort: even if subsequent checks fail, we want the
    # token hash recorded so reuse is blocked.
    _revoke_bearer(token, session)

    impersonator_sub = payload.get("impersonator_sub")
    if not impersonator_sub:
        raise HTTPException(status_code=400, detail="Malformed impersonation token")

    try:
        admin_id = uuid.UUID(impersonator_sub)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Malformed impersonation token")

    admin = session.get(User, admin_id)
    if admin is None or not admin.is_active or not admin.is_admin:
        raise HTTPException(status_code=401, detail="Impersonating admin is no longer valid")

    target_id = payload.get("sub")
    posthog_client.capture(
        distinct_id=str(admin.id),
        event="admin_impersonation_stopped",
        properties={
            "impersonated_user_id": str(target_id) if target_id else None,
            "jti": payload.get("jti"),
        },
    )

    new_token = create_access_token(str(admin.id))
    return StopImpersonationResponse(access_token=new_token)


@router.post("/impersonate/{user_id}", response_model=ImpersonateResponse)
def start_impersonation(
    user_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
    impersonator: User | None = Depends(get_impersonator),
) -> ImpersonateResponse:
    """Mint a short-lived bearer that lets the admin act as `user_id`.

    Refuses nested impersonation and refuses targeting other admins."""
    # No nested impersonation sessions. An admin who is already acting as
    # someone else must /stop first — otherwise the audit trail ends up
    # with ambiguous chains of impersonator_sub claims.
    if impersonator is not None:
        raise HTTPException(status_code=400, detail="already_impersonating")

    target = session.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="user_not_found")
    if not target.is_active:
        raise HTTPException(status_code=400, detail="user_inactive")

    # Don't let admins impersonate other admins — lateral access with
    # overlapping audit attribution is a trust-boundary hazard.
    if target.is_admin:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "cannot_impersonate_admin",
                "message": "Admins cannot impersonate other admins.",
            },
        )

    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="cannot_impersonate_self")

    token, jti = create_impersonation_token(str(admin.id), str(target.id))

    posthog_client.capture(
        distinct_id=str(admin.id),
        event="admin_impersonation_started",
        properties={
            "impersonated_user_id": str(target.id),
            "target_email": target.email,
            "jti": jti,
            "ttl_minutes": settings.impersonation_ttl_minutes,
            "requester_ip": request.client.host if request.client else None,
        },
    )

    return ImpersonateResponse(
        access_token=token,
        expires_in=settings.impersonation_ttl_minutes * 60,
        target_user_id=str(target.id),
        target_email=target.email,
    )
