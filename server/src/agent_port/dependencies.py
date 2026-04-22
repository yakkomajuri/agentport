import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select

from agent_port.config import settings
from agent_port.db import get_session
from agent_port.models.api_key import ApiKey
from agent_port.models.oauth_revoked_token import OAuthRevokedToken
from agent_port.models.org import Org
from agent_port.models.org_membership import OrgMembership
from agent_port.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


@dataclass
class AgentAuth:
    org: Org
    user: User | None  # None when authenticated via API key
    api_key: ApiKey | None  # None when authenticated via JWT
    # Populated when `user` is acting via an admin impersonation token. The
    # field holds the admin who initiated the session. Log writers and
    # downstream analytics must surface this so impersonated actions are
    # attributable to the admin, not the target.
    impersonator: User | None = None


def _is_token_revoked(token: str, session: Session) -> bool:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return session.get(OAuthRevokedToken, token_hash) is not None


def _decode_rest_bearer_token(
    token: str,
    session: Session,
    credentials_exception: HTTPException,
) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_aud": False},
        )
    except jwt.PyJWTError:
        raise credentials_exception

    token_use = payload.get("token_use")
    if token_use == "refresh":
        raise credentials_exception

    # Both regular access tokens and impersonation tokens participate in the
    # shared revocation list — stop_impersonation records the bearer hash so
    # a captured token stops working the instant the admin ends the session.
    if token_use in ("access", "impersonation") and _is_token_revoked(token, session):
        raise credentials_exception

    return payload


def _resolve_impersonator(payload: dict, session: Session) -> User | None:
    """Look up the admin behind an impersonation token, or None for normal tokens.

    Raises nothing — a stale or missing impersonator sub is treated as "no
    impersonator", since a normal access token simply won't carry the claim.
    We deliberately do NOT re-check `is_admin` here: if an admin gets demoted
    mid-session the audit log should still record that the original actor
    was the impersonator, and any endpoints that want to refuse the action
    (TOTP/password gates) already do so based on *presence* of the field."""
    imp_sub = payload.get("impersonator_sub")
    if not imp_sub:
        return None
    try:
        imp_uuid = uuid.UUID(imp_sub)
    except (ValueError, TypeError):
        return None
    admin = session.get(User, imp_uuid)
    if admin is None or not admin.is_active:
        return None
    return admin


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = _decode_rest_bearer_token(token, session, credentials_exception)
    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = session.get(User, uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def get_impersonator(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User | None:
    """Return the original admin when the current token is an impersonation token.

    Returns None for normal tokens, or when the impersonator is no longer
    active. Does not raise — callers decide how to handle absence. Used by
    endpoints that should refuse to run under impersonation (TOTP setup,
    password change) as well as /api/users/me for the banner."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = _decode_rest_bearer_token(token, session, credentials_exception)
    return _resolve_impersonator(payload, session)


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="admin_required")
    return current_user


def get_current_org(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Org:
    membership = session.exec(
        select(OrgMembership).where(OrgMembership.user_id == current_user.id)
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="User has no organization")
    org = session.get(Org, membership.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


def _org_for_user(user: User, session: Session) -> Org:
    membership = session.exec(select(OrgMembership).where(OrgMembership.user_id == user.id)).first()
    if not membership:
        raise HTTPException(status_code=403, detail="User has no organization")
    org = session.get(Org, membership.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


def get_agent_auth(
    request: Request,
    session: Session = Depends(get_session),
) -> AgentAuth:
    """Accepts X-API-Key header or Authorization: Bearer JWT.
    Use on agent-facing endpoints. Human-only endpoints keep get_current_user/get_current_org."""
    # 1. Try API key first
    raw_key = request.headers.get("X-API-Key")
    if raw_key:
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        api_key = session.exec(
            select(ApiKey).where(ApiKey.key_hash == key_hash).where(ApiKey.is_active == True)  # noqa: E712
        ).first()
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "X-API-Key"},
            )
        org = session.get(Org, api_key.org_id)
        if not org:
            raise HTTPException(status_code=500, detail="Organization not found for API key")
        # Update last_used_at — non-fatal
        try:
            api_key.last_used_at = datetime.utcnow()
            session.add(api_key)
            session.commit()
        except Exception:
            session.rollback()
        return AgentAuth(org=org, user=None, api_key=api_key)

    # 2. Try JWT Bearer token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer ") :]
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        payload = _decode_rest_bearer_token(token, session, credentials_exception)
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        user = session.get(User, uuid.UUID(user_id))
        if user is None or not user.is_active:
            raise credentials_exception

        org_id = payload.get("org_id") if payload.get("token_use") == "access" else None
        if org_id:
            org = session.get(Org, uuid.UUID(org_id))
            if not org:
                raise credentials_exception
            membership = session.exec(
                select(OrgMembership)
                .where(OrgMembership.user_id == user.id)
                .where(OrgMembership.org_id == org.id)
            ).first()
            if not membership:
                raise credentials_exception
        else:
            org = _org_for_user(user, session)
        impersonator = _resolve_impersonator(payload, session)
        return AgentAuth(org=org, user=user, api_key=None, impersonator=impersonator)

    # 3. No credentials
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
