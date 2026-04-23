import hashlib
import json
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    RefreshToken,
    TokenError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyUrl
from sqlmodel import Session, select

from agent_port.config import settings
from agent_port.db import engine
from agent_port.models.oauth_auth_code import OAuthAuthCode
from agent_port.models.oauth_auth_request import OAuthAuthRequest
from agent_port.models.oauth_client import OAuthClient
from agent_port.models.oauth_revoked_token import OAuthRevokedToken
from agent_port.models.org_membership import OrgMembership
from agent_port.models.user import User
from agent_port.secrets.records import get_secret_value, upsert_secret


class AppAuthorizationCode(AuthorizationCode):
    user_id: uuid.UUID
    org_id: uuid.UUID


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _issue_access_token(
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    client_id: str,
    scopes: list[str],
) -> str:
    # Token is scoped exclusively to the /mcp resource — token_use="mcp_access"
    # (not the generic "access") so REST's _decode_rest_bearer_token rejects it
    # on sight. See security audit finding 09.
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user_id),
        "org_id": str(org_id),
        "client_id": client_id,
        "scope": " ".join(scopes),
        "token_use": "mcp_access",
        "aud": f"{settings.base_url}/mcp",
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
        "iat": now,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _issue_refresh_token(
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    client_id: str,
    scopes: list[str],
) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user_id),
        "org_id": str(org_id),
        "client_id": client_id,
        "scope": " ".join(scopes),
        "token_use": "refresh",
        "exp": now + timedelta(days=30),
        "iat": now,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _is_token_revoked(token_str: str) -> bool:
    token_hash = _hash_token(token_str)
    with Session(engine) as session:
        row = session.get(OAuthRevokedToken, token_hash)
        return row is not None


class AgentPortOAuthProvider:
    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        with Session(engine) as session:
            row = session.exec(
                select(OAuthClient).where(OAuthClient.client_id == client_id)
            ).first()
            if not row:
                return None
            client_secret = get_secret_value(session, row.client_secret_secret_id)
            return OAuthClientInformationFull(
                client_id=row.client_id,
                client_secret=client_secret,
                client_name=row.client_name,
                redirect_uris=json.loads(row.redirect_uris_json),
                grant_types=json.loads(row.grant_types_json),
                response_types=json.loads(row.response_types_json),
                token_endpoint_auth_method=row.token_endpoint_auth_method,
                client_id_issued_at=row.client_id_issued_at,
                client_secret_expires_at=row.client_secret_expires_at,
            )

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        with Session(engine) as session:
            existing = session.exec(
                select(OAuthClient).where(OAuthClient.client_id == client_info.client_id)
            ).first()
            if existing:
                return

            stored_cs = None
            if client_info.client_secret:
                stored_cs = upsert_secret(
                    session,
                    org_id=None,
                    kind="mcp_oauth_client_secret",
                    ref=f"oauth_clients/{client_info.client_id}/secret",
                    value=client_info.client_secret,
                )
            row = OAuthClient(
                client_id=client_info.client_id,
                client_secret_secret_id=stored_cs.id if stored_cs else None,
                client_name=client_info.client_name,
                redirect_uris_json=json.dumps([str(uri) for uri in client_info.redirect_uris]),
                grant_types_json=json.dumps(client_info.grant_types),
                response_types_json=json.dumps(client_info.response_types),
                token_endpoint_auth_method=client_info.token_endpoint_auth_method,
                client_id_issued_at=client_info.client_id_issued_at or int(time.time()),
                client_secret_expires_at=client_info.client_secret_expires_at,
            )
            session.add(row)
            session.commit()

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        session_token = secrets.token_urlsafe(32)
        session_hash = _hash_token(session_token)

        expires_at = int(time.time()) + 600  # 10 minutes

        with Session(engine) as db:
            row = OAuthAuthRequest(
                session_token_hash=session_hash,
                client_id=client.client_id,
                redirect_uri=str(params.redirect_uri),
                redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
                code_challenge=params.code_challenge,
                scope=" ".join(params.scopes) if params.scopes else None,
                state=params.state,
                resource=str(params.resource) if params.resource else None,
                expires_at=expires_at,
            )
            db.add(row)
            db.commit()

        return f"{settings.ui_base_url}/oauth/authorize?session={session_token}"

    async def complete_authorization(self, session_token: str, user_id: uuid.UUID) -> str:
        session_hash = _hash_token(session_token)

        with Session(engine) as db:
            req = db.get(OAuthAuthRequest, session_hash)
            if not req:
                raise AuthorizeError(
                    error="invalid_request",
                    error_description="Unknown or expired authorization session",
                )
            if req.expires_at < int(time.time()):
                db.delete(req)
                db.commit()
                raise AuthorizeError(
                    error="invalid_request",
                    error_description="Authorization session expired",
                )

            user = db.get(User, user_id)
            if not user or not user.is_active:
                raise AuthorizeError(
                    error="access_denied",
                    error_description="User not found or inactive",
                )

            memberships = db.exec(
                select(OrgMembership).where(OrgMembership.user_id == user.id)
            ).all()
            if len(memberships) != 1:
                raise AuthorizeError(
                    error="server_error",
                    error_description="User must belong to exactly one organization",
                )
            org_id = memberships[0].org_id

            code = secrets.token_urlsafe(32)
            auth_code = OAuthAuthCode(
                code=code,
                client_id=req.client_id,
                org_id=org_id,
                user_id=user.id,
                redirect_uri=req.redirect_uri,
                redirect_uri_provided_explicitly=req.redirect_uri_provided_explicitly,
                code_challenge=req.code_challenge,
                scope=req.scope,
                resource=req.resource,
                expires_at=time.time() + 600,
            )
            db.add(auth_code)
            db.delete(req)
            db.commit()

            redirect_url = construct_redirect_uri(req.redirect_uri, code=code, state=req.state)
            return redirect_url

    async def deny_authorization(self, session_token: str) -> str:
        session_hash = _hash_token(session_token)

        with Session(engine) as db:
            req = db.get(OAuthAuthRequest, session_hash)
            if not req:
                raise AuthorizeError(
                    error="invalid_request",
                    error_description="Unknown or expired authorization session",
                )

            redirect_uri = req.redirect_uri
            state = req.state
            db.delete(req)
            db.commit()

        return construct_redirect_uri(redirect_uri, error="access_denied", state=state)

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AppAuthorizationCode | None:
        with Session(engine) as db:
            row = db.exec(
                select(OAuthAuthCode)
                .where(OAuthAuthCode.code == authorization_code)
                .where(OAuthAuthCode.client_id == client.client_id)
            ).first()
            if not row:
                return None
            return AppAuthorizationCode(
                code=row.code,
                scopes=row.scope.split(" ") if row.scope else [],
                expires_at=row.expires_at,
                client_id=row.client_id,
                code_challenge=row.code_challenge,
                redirect_uri=AnyUrl(row.redirect_uri),
                redirect_uri_provided_explicitly=row.redirect_uri_provided_explicitly,
                resource=row.resource,
                user_id=row.user_id,
                org_id=row.org_id,
            )

    async def exchange_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: AppAuthorizationCode,
    ) -> OAuthToken:
        # Delete the auth code so it's one-time use
        with Session(engine) as db:
            row = db.exec(
                select(OAuthAuthCode).where(OAuthAuthCode.code == authorization_code.code)
            ).first()
            if row:
                db.delete(row)
                db.commit()

        access_token = _issue_access_token(
            user_id=authorization_code.user_id,
            org_id=authorization_code.org_id,
            client_id=client.client_id,
            scopes=authorization_code.scopes,
        )
        refresh_token = _issue_refresh_token(
            user_id=authorization_code.user_id,
            org_id=authorization_code.org_id,
            client_id=client.client_id,
            scopes=authorization_code.scopes,
        )

        return OAuthToken(
            access_token=access_token,
            token_type="Bearer",
            expires_in=settings.jwt_expire_minutes * 60,
            scope=" ".join(authorization_code.scopes) if authorization_code.scopes else None,
            refresh_token=refresh_token,
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
                audience=f"{settings.base_url}/mcp",
            )
        except jwt.PyJWTError:
            return None

        if payload.get("token_use") != "mcp_access":
            return None

        if _is_token_revoked(token):
            return None

        user_id = payload.get("sub")
        org_id = payload.get("org_id")
        if not user_id or not org_id:
            return None

        with Session(engine) as db:
            user = db.get(User, uuid.UUID(user_id))
            if not user or not user.is_active:
                return None
            membership = db.exec(
                select(OrgMembership)
                .where(OrgMembership.user_id == uuid.UUID(user_id))
                .where(OrgMembership.org_id == uuid.UUID(org_id))
            ).first()
            if not membership:
                return None

        scopes = payload.get("scope", "").split() if payload.get("scope") else []
        return AccessToken(
            token=token,
            client_id=payload.get("client_id", ""),
            scopes=scopes,
            expires_at=payload.get("exp"),
            resource=payload.get("aud"),
        )

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        try:
            payload = jwt.decode(
                refresh_token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
        except jwt.PyJWTError:
            return None

        if payload.get("token_use") != "refresh":
            return None

        if payload.get("client_id") != client.client_id:
            return None

        if _is_token_revoked(refresh_token):
            return None

        user_id = payload.get("sub")
        org_id = payload.get("org_id")
        if not user_id or not org_id:
            return None

        with Session(engine) as db:
            user = db.get(User, uuid.UUID(user_id))
            if not user or not user.is_active:
                return None
            membership = db.exec(
                select(OrgMembership)
                .where(OrgMembership.user_id == uuid.UUID(user_id))
                .where(OrgMembership.org_id == uuid.UUID(org_id))
            ).first()
            if not membership:
                return None

        scopes = payload.get("scope", "").split() if payload.get("scope") else []
        return RefreshToken(
            token=refresh_token,
            client_id=client.client_id,
            scopes=scopes,
            expires_at=payload.get("exp"),
        )

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        # Validate requested scopes are a subset of original
        if scopes and not set(scopes).issubset(set(refresh_token.scopes)):
            raise TokenError(
                error="invalid_scope",
                error_description="Requested scopes exceed original grant",
            )

        effective_scopes = scopes if scopes else refresh_token.scopes

        # Decode the refresh token to get user/org info
        try:
            payload = jwt.decode(
                refresh_token.token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
        except jwt.PyJWTError:
            raise TokenError(
                error="invalid_grant",
                error_description="Invalid refresh token",
            )

        user_id = uuid.UUID(payload["sub"])
        org_id = uuid.UUID(payload["org_id"])

        # Revoke old refresh token (rotation)
        with Session(engine) as db:
            revoked = OAuthRevokedToken(
                token_hash=_hash_token(refresh_token.token),
                expires_at=payload.get("exp", int(time.time()) + 86400),
            )
            db.add(revoked)
            db.commit()

        access_token = _issue_access_token(
            user_id=user_id,
            org_id=org_id,
            client_id=client.client_id,
            scopes=effective_scopes,
        )
        new_refresh_token = _issue_refresh_token(
            user_id=user_id,
            org_id=org_id,
            client_id=client.client_id,
            scopes=effective_scopes,
        )

        return OAuthToken(
            access_token=access_token,
            token_type="Bearer",
            expires_in=settings.jwt_expire_minutes * 60,
            scope=" ".join(effective_scopes) if effective_scopes else None,
            refresh_token=new_refresh_token,
        )

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        token_hash = _hash_token(token.token)
        with Session(engine) as db:
            existing = db.get(OAuthRevokedToken, token_hash)
            if existing:
                return
            expires_at = token.expires_at or int(time.time()) + 86400
            revoked = OAuthRevokedToken(token_hash=token_hash, expires_at=expires_at)
            db.add(revoked)
            db.commit()


oauth_provider = AgentPortOAuthProvider()
