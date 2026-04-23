import uuid
from datetime import datetime, timedelta, timezone

import jwt

from agent_port.config import settings

EMAIL_VERIFICATION_SESSION_TTL = timedelta(hours=1)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: str, *, impersonator_id: str | None = None) -> str:
    expire = _utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    claims: dict[str, object] = {"sub": user_id, "exp": expire, "token_use": "access"}
    if impersonator_id:
        claims["impersonator_sub"] = impersonator_id
    return jwt.encode(
        claims,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_impersonation_token(
    admin_user_id: str,
    target_user_id: str,
    ttl_minutes: int | None = None,
) -> tuple[str, str]:
    """Mint a short-lived token that lets an admin act as `target_user_id`.

    Returns (jwt, jti). The jti is needed so `stop_impersonation` can record
    revocation by jti as well as by token hash."""
    now = _utcnow()
    minutes = ttl_minutes if ttl_minutes is not None else settings.impersonation_ttl_minutes
    jti = str(uuid.uuid4())
    token = jwt.encode(
        {
            "sub": target_user_id,
            "impersonator_sub": admin_user_id,
            "token_use": "impersonation",
            "jti": jti,
            "iat": now,
            "exp": now + timedelta(minutes=minutes),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token, jti


def create_email_verification_session_token(user_id: str) -> str:
    expire = _utcnow() + EMAIL_VERIFICATION_SESSION_TTL
    return jwt.encode(
        {
            "sub": user_id,
            "exp": expire,
            "scope": "email_verification",
            "token_use": "email_verification",
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_email_verification_session_token(token: str) -> str:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.InvalidTokenError as exc:
        raise ValueError("Invalid or expired verification session") from exc

    if payload.get("scope") != "email_verification" or not payload.get("sub"):
        raise ValueError("Invalid or expired verification session")

    return str(payload["sub"])
