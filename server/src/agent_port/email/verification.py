import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlmodel import Session

from agent_port.auth_tokens import (
    create_email_verification_session_token,
    decode_email_verification_session_token,
)
from agent_port.config import settings
from agent_port.email.send import send_email
from agent_port.email.templates import verification_email
from agent_port.models.user import User

EMAIL_VERIFICATION_CODE_TTL = timedelta(minutes=30)
EMAIL_VERIFICATION_RESEND_COOLDOWN = timedelta(minutes=10)
EMAIL_VERIFICATION_MAX_ATTEMPTS = 5

# Kept deliberately generic so the API cannot distinguish wrong vs. expired vs.
# burned codes for an attacker brute-forcing the 1M code space.
GENERIC_VERIFICATION_ERROR = "Invalid or expired verification code"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True)
class EmailVerificationChallenge:
    email: str
    verification_token: str
    resend_available_at: datetime | None


class VerificationEmailRateLimitedError(Exception):
    def __init__(self, resend_available_at: datetime):
        super().__init__("Verification email resend is rate limited")
        self.resend_available_at = resend_available_at


def get_email_verification_challenge(user: User) -> EmailVerificationChallenge:
    return EmailVerificationChallenge(
        email=user.email,
        verification_token=create_email_verification_session_token(str(user.id)),
        resend_available_at=get_email_verification_resend_available_at(user),
    )


def get_email_verification_required_detail(user: User) -> dict:
    challenge = get_email_verification_challenge(user)
    return {
        "error": "email_verification_required",
        "message": "Enter the 6-digit verification code we sent to your email.",
        "email": challenge.email,
        "verification_token": challenge.verification_token,
        "resend_available_at": (
            challenge.resend_available_at.isoformat() if challenge.resend_available_at else None
        ),
    }


def get_email_verification_resend_available_at(user: User) -> datetime | None:
    sent_at = _as_utc(user.email_verification_sent_at)
    if not sent_at:
        return None
    return sent_at + EMAIL_VERIFICATION_RESEND_COOLDOWN


def _normalize_verification_code(code: str) -> str:
    return "".join(ch for ch in code if ch.isdigit())


def _verification_code_hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _create_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def get_user_from_verification_session_token(token: str, session: Session) -> User:
    try:
        user_id = uuid.UUID(decode_email_verification_session_token(token))
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid or expired verification session") from exc

    user = session.get(User, user_id)
    if not user or not user.is_active:
        raise ValueError("Invalid or expired verification session")
    return user


def mark_email_verified(user: User, session: Session) -> None:
    user.email_verified = True
    user.email_verification_token_hash = None
    user.email_verification_code_hash = None
    user.email_verification_code_expires_at = None
    user.email_verification_attempts = 0
    session.add(user)
    session.commit()


def _burn_verification_code(user: User, session: Session) -> None:
    user.email_verification_code_hash = None
    user.email_verification_code_expires_at = None
    session.add(user)
    session.commit()


def send_verification_email(user: User, session: Session) -> datetime:
    now = _utcnow()
    # Cooldown only applies while the previously-issued code is still live.
    # If it was burned (5 wrong attempts) or never set, allow an immediate
    # resend so the user can recover without waiting.
    if user.email_verification_code_hash is not None:
        resend_available_at = get_email_verification_resend_available_at(user)
        if resend_available_at and resend_available_at > now:
            raise VerificationEmailRateLimitedError(resend_available_at)

    token = secrets.token_urlsafe(32)
    code = _create_verification_code()
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    code_hash = _verification_code_hash(code)
    user.email_verification_token_hash = token_hash
    user.email_verification_code_hash = code_hash
    user.email_verification_code_expires_at = now + EMAIL_VERIFICATION_CODE_TTL
    user.email_verification_sent_at = now
    user.email_verification_attempts = 0
    session.add(user)
    session.commit()

    verify_url = f"{settings.ui_base_url}/verify-email?token={token}"
    send_email(
        to=user.email,
        subject="Verify your email",
        html=verification_email(verify_url, code),
    )
    return user.email_verification_sent_at + EMAIL_VERIFICATION_RESEND_COOLDOWN


def verify_email_code(code: str, verification_token: str, session: Session) -> User:
    user = get_user_from_verification_session_token(verification_token, session)
    if user.email_verified:
        return user

    normalized_code = _normalize_verification_code(code)
    now = _utcnow()
    expires_at = _as_utc(user.email_verification_code_expires_at)

    code_is_live = bool(
        normalized_code and user.email_verification_code_hash and expires_at and expires_at >= now
    )
    if not code_is_live:
        raise ValueError(GENERIC_VERIFICATION_ERROR)

    if not secrets.compare_digest(
        user.email_verification_code_hash,
        _verification_code_hash(normalized_code),
    ):
        user.email_verification_attempts += 1
        if user.email_verification_attempts >= EMAIL_VERIFICATION_MAX_ATTEMPTS:
            _burn_verification_code(user, session)
        else:
            session.add(user)
            session.commit()
        raise ValueError(GENERIC_VERIFICATION_ERROR)

    mark_email_verified(user, session)
    return user
