import hashlib
import time
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from agent_port.config import settings
from agent_port.db import get_session
from agent_port.main import app
from agent_port.mcp.asgi import _authenticate
from agent_port.mcp.oauth_provider import _issue_access_token, _issue_refresh_token, oauth_provider
from agent_port.models.oauth_revoked_token import OAuthRevokedToken


def _override_session(session):
    def _gen():
        yield session

    return _gen


def _mcp_scope(token: str) -> dict:
    return {"headers": [(b"authorization", f"Bearer {token}".encode())]}


def _issue_mcp_access_token_with_audience(test_user, test_org, audience: str) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(test_user.id),
        "org_id": str(test_org.id),
        "client_id": "mcp-client",
        "scope": "",
        "token_use": "mcp_access",
        "aud": audience,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
        "iat": now,
    }
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


@pytest.mark.asyncio
async def test_mcp_oauth_access_token_rejected_on_human_rest_endpoint(session, test_user, test_org):
    """An MCP OAuth access token must not unlock REST endpoints that expect a
    human bearer — see security audit finding 09."""
    token = _issue_access_token(test_user.id, test_org.id, "mcp-client", [])

    app.dependency_overrides[get_session] = _override_session(session)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        resp = await c.get("/api/api-keys")

    app.dependency_overrides.clear()
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_mcp_oauth_access_token_rejected_on_agent_rest_endpoint(session, test_user, test_org):
    """Same guard applied to the agent-facing endpoints, which accept either a
    human JWT or an API key and previously honoured MCP audience tokens."""
    token = _issue_access_token(test_user.id, test_org.id, "mcp-client", [])

    app.dependency_overrides[get_session] = _override_session(session)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        resp = await c.get("/api/installed")

    app.dependency_overrides.clear()
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_oauth_refresh_token_rejected_on_rest_endpoints(session, test_user, test_org):
    token = _issue_refresh_token(test_user.id, test_org.id, "cli-test", [])

    app.dependency_overrides[get_session] = _override_session(session)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        resp = await c.get("/api/installed")

    app.dependency_overrides.clear()
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_mcp_oauth_access_token_still_authenticates_mcp(session, test_user, test_org):
    """Regression guard: the audience split tightens REST but must leave the
    MCP resource path accepting the same bearer (that is the token's whole
    purpose)."""
    token = _issue_access_token(test_user.id, test_org.id, "mcp-client", [])

    loaded = await oauth_provider.load_access_token(token)

    assert loaded is not None
    assert str(test_user.id) == str(loaded.client_id) or loaded.client_id == "mcp-client"
    assert loaded.resource == f"{settings.base_url}/mcp"


def test_mcp_asgi_rejects_mcp_access_token_with_wrong_audience(session, test_user, test_org):
    token = _issue_mcp_access_token_with_audience(
        test_user,
        test_org,
        f"{settings.base_url}/api",
    )

    assert _authenticate(_mcp_scope(token)) is None


def test_mcp_asgi_accepts_mcp_access_token_with_mcp_audience(session, test_user, test_org):
    token = _issue_access_token(test_user.id, test_org.id, "mcp-client", [])

    auth = _authenticate(_mcp_scope(token))

    assert auth is not None
    assert auth.user is not None
    assert auth.user.id == test_user.id
    assert auth.org.id == test_org.id


@pytest.mark.asyncio
async def test_revoked_mcp_oauth_access_token_rejected(session, test_user, test_org):
    """Revocation still short-circuits MCP validation so we don't regress the
    existing revoke-on-logout behaviour while tightening audience checks."""
    token = _issue_access_token(test_user.id, test_org.id, "mcp-client", [])
    session.add(
        OAuthRevokedToken(
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=int(time.time()) + 3600,
        )
    )
    session.commit()

    loaded = await oauth_provider.load_access_token(token)
    assert loaded is None


@pytest.mark.asyncio
async def test_revoked_oauth_access_token_rejected_on_rest_endpoints(session, test_user, test_org):
    token = _issue_access_token(test_user.id, test_org.id, "cli-test", [])
    session.add(
        OAuthRevokedToken(
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=int(time.time()) + 3600,
        )
    )
    session.commit()

    app.dependency_overrides[get_session] = _override_session(session)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        resp = await c.get("/api/installed")

    app.dependency_overrides.clear()
    assert resp.status_code == 401
