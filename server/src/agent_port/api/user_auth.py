import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlmodel import Session, select

from agent_port.analytics import posthog_client
from agent_port.auth_tokens import create_access_token
from agent_port.config import settings
from agent_port.db import get_session
from agent_port.email import normalize_email
from agent_port.email.verification import get_email_verification_required_detail
from agent_port.models.user import User
from agent_port.rate_limit import (
    ACCOUNT_LOCKOUT_SECONDS,
    ACCOUNT_LOCKOUT_THRESHOLD,
    login_failure_ip_limiter,
)
from agent_port.security import hash_password, verify_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["user-auth"])

# Same text for wrong-password and locked-account responses so the body is
# never an enumeration / lockout oracle — only the status code differs.
_AUTH_FAILURE_DETAIL = "Incorrect email or password"

# Precomputed bcrypt hash used to make login timing indistinguishable between
# "email not registered" and "email registered, wrong password". Verifying
# against this hash takes the same time as verifying a real user's password,
# which prevents a timing oracle from enumerating registered emails.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(32))


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _wrong_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=_AUTH_FAILURE_DETAIL,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _rate_limited(retry_after_seconds: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=_AUTH_FAILURE_DETAIL,
        headers={"Retry-After": str(max(retry_after_seconds, 1))},
    )


@router.post("/token", response_model=TokenResponse)
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
) -> TokenResponse:
    ip = _client_ip(request)

    retry_after = login_failure_ip_limiter.check(ip)
    if retry_after:
        raise _rate_limited(retry_after)

    now = datetime.now(timezone.utc)
    normalized_email = normalize_email(form.username)
    user = session.exec(select(User).where(User.email == normalized_email)).first()

    if user is not None and user.locked_until is not None:
        locked_until = user.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until > now:
            remaining = int((locked_until - now).total_seconds()) + 1
            raise _rate_limited(remaining)

    # Always run one bcrypt verify so response time doesn't leak which
    # branch we took — dummy hash when there's nothing real to check.
    if user is not None and user.hashed_password:
        password_ok = verify_password(form.password, user.hashed_password)
    else:
        verify_password(form.password, _DUMMY_HASH)
        password_ok = False

    if not user or not user.is_active or not password_ok:
        login_failure_ip_limiter.record(ip)
        if user is not None:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= ACCOUNT_LOCKOUT_THRESHOLD:
                user.locked_until = now + timedelta(seconds=ACCOUNT_LOCKOUT_SECONDS)
                logger.warning(
                    "account_locked user_id=%s ip=%s attempts=%s",
                    user.id,
                    ip,
                    user.failed_login_attempts,
                )
            session.add(user)
            session.commit()
        raise _wrong_credentials()

    assert user is not None  # narrowed by password_ok

    if user.failed_login_attempts or user.locked_until is not None:
        user.failed_login_attempts = 0
        user.locked_until = None
        session.add(user)
        session.commit()
    login_failure_ip_limiter.reset_ip(ip)

    if not settings.skip_email_verification and not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=get_email_verification_required_detail(user),
        )

    token = create_access_token(str(user.id))
    posthog_client.capture(
        distinct_id=str(user.id),
        event="user_logged_in",
        properties={"auth_method": "password"},
    )
    return TokenResponse(access_token=token)
