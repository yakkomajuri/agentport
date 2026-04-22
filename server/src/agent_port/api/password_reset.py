import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from agent_port.api.schemas import MessageResponse
from agent_port.config import settings
from agent_port.db import get_session
from agent_port.email import normalize_email, send_email
from agent_port.email.templates import password_reset_email
from agent_port.models.user import User
from agent_port.rate_limit import login_failure_ip_limiter
from agent_port.security import hash_password

router = APIRouter(prefix="/api/auth", tags=["password-reset"])

RESET_TOKEN_EXPIRY_HOURS = 1


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    # Every forgot-password call burns one slot in the same per-IP bucket as
    # failed logins. We can't distinguish hit-vs-miss here without leaking
    # which emails are registered, so treat every call as a potential abuse
    # event.
    dependencies=[Depends(login_failure_ip_limiter)],
)
def forgot_password(
    body: ForgotPasswordRequest,
    session: Session = Depends(get_session),
) -> MessageResponse:
    # Always return 200 to avoid email enumeration
    email = normalize_email(body.email)
    user = session.exec(select(User).where(User.email == email)).first()
    if user and user.is_active:
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        user.password_reset_token_hash = token_hash
        user.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(
            hours=RESET_TOKEN_EXPIRY_HOURS
        )
        session.add(user)
        session.commit()

        reset_url = f"{settings.ui_base_url}/reset-password?token={token}"
        send_email(
            to=user.email,
            subject="Reset your password",
            html=password_reset_email(reset_url),
        )

    return MessageResponse(message="If that email exists, a reset link has been sent")


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    body: ResetPasswordRequest,
    session: Session = Depends(get_session),
) -> MessageResponse:
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    user = session.exec(select(User).where(User.password_reset_token_hash == token_hash)).first()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    now = datetime.now(timezone.utc)
    expires = user.password_reset_expires_at
    if expires is None or expires.replace(tzinfo=timezone.utc) < now:
        user.password_reset_token_hash = None
        user.password_reset_expires_at = None
        session.add(user)
        session.commit()
        raise HTTPException(status_code=400, detail="Reset token has expired")

    user.hashed_password = hash_password(body.new_password)
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
    session.add(user)
    session.commit()
    return MessageResponse(message="Password has been reset successfully")
