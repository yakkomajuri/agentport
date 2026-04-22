import hashlib

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from agent_port.analytics import posthog_client
from agent_port.api.schemas import (
    MessageResponse,
    ResendVerificationResponse,
    VerifyEmailCodeResponse,
    VerifyEmailResponse,
)
from agent_port.auth_tokens import create_access_token
from agent_port.db import get_session
from agent_port.dependencies import get_current_user
from agent_port.email import normalize_email, send_verification_email
from agent_port.email.verification import (
    VerificationEmailRateLimitedError,
    get_user_from_verification_session_token,
    mark_email_verified,
    verify_email_code,
)
from agent_port.models.user import User
from agent_port.rate_limit import verify_email_code_ip_limiter, verify_email_ip_limiter

router = APIRouter(prefix="/api/auth", tags=["email-verification"])


class ResendByEmailRequest(BaseModel):
    email: str


class VerifyEmailCodeRequest(BaseModel):
    code: str
    verification_token: str


class ResendVerificationCodeRequest(BaseModel):
    verification_token: str


def _raise_resend_rate_limited(resend_available_at) -> None:
    raise HTTPException(
        status_code=429,
        detail={
            "error": "verification_email_rate_limited",
            "message": "Verification email already sent recently. Try again later.",
            "resend_available_at": resend_available_at.isoformat(),
        },
    )


@router.get(
    "/verify-email",
    response_model=VerifyEmailResponse,
    dependencies=[Depends(verify_email_ip_limiter)],
)
def verify_email(
    token: str,
    session: Session = Depends(get_session),
) -> VerifyEmailResponse:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    user = session.exec(
        select(User).where(User.email_verification_token_hash == token_hash)
    ).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    mark_email_verified(user, session)
    posthog_client.capture(distinct_id=str(user.id), event="email_verified")
    return VerifyEmailResponse(message="Email verified successfully", email=user.email)


@router.post(
    "/verify-email-code",
    response_model=VerifyEmailCodeResponse,
    dependencies=[Depends(verify_email_code_ip_limiter)],
)
def verify_email_code_route(
    body: VerifyEmailCodeRequest,
    session: Session = Depends(get_session),
) -> VerifyEmailCodeResponse:
    try:
        user = verify_email_code(body.code, body.verification_token, session)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    access_token = create_access_token(str(user.id))
    return VerifyEmailCodeResponse(
        message="Email verified successfully",
        access_token=access_token,
        token_type="bearer",
    )


@router.post("/resend-verification", response_model=ResendVerificationResponse)
def resend_verification(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ResendVerificationResponse:
    if current_user.email_verified:
        return ResendVerificationResponse(message="Email is already verified")

    try:
        resend_available_at = send_verification_email(current_user, session)
    except VerificationEmailRateLimitedError as exc:
        _raise_resend_rate_limited(exc.resend_available_at)
    return ResendVerificationResponse(
        message="Verification email sent",
        resend_available_at=resend_available_at,
    )


@router.post("/resend-verification-code", response_model=ResendVerificationResponse)
def resend_verification_code(
    body: ResendVerificationCodeRequest,
    session: Session = Depends(get_session),
) -> ResendVerificationResponse:
    try:
        user = get_user_from_verification_session_token(body.verification_token, session)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if user.email_verified:
        return ResendVerificationResponse(message="Email is already verified")

    try:
        resend_available_at = send_verification_email(user, session)
    except VerificationEmailRateLimitedError as exc:
        _raise_resend_rate_limited(exc.resend_available_at)
    return ResendVerificationResponse(
        message="Verification email sent",
        resend_available_at=resend_available_at,
    )


@router.post("/resend-verification-by-email", response_model=MessageResponse)
def resend_verification_by_email(
    body: ResendByEmailRequest,
    session: Session = Depends(get_session),
) -> MessageResponse:
    """Unauthenticated endpoint so users who cannot log in (email not yet
    verified) can request a new verification email."""
    email = normalize_email(body.email)
    user = session.exec(select(User).where(User.email == email)).first()
    if user and user.is_active and not user.email_verified:
        try:
            send_verification_email(user, session)
        except VerificationEmailRateLimitedError:
            pass
    # Always return the same message to prevent email enumeration.
    return MessageResponse(
        message="If that email is registered and unverified, a verification email has been sent"
    )
