import hashlib
import time

import pytest
from httpx import ASGITransport, AsyncClient

from agent_port.db import get_session
from agent_port.main import app
from agent_port.mcp.oauth_provider import _issue_access_token, _issue_refresh_token
from agent_port.models.oauth_revoked_token import OAuthRevokedToken


@pytest.mark.asyncio
async def test_oauth_access_token_authenticates_human_endpoint(session, test_user, test_org):
    token = _issue_access_token(test_user.id, test_org.id, "cli-test", [])

    def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        resp = await c.get("/api/api-keys")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_oauth_access_token_authenticates_agent_endpoint(session, test_user, test_org):
    token = _issue_access_token(test_user.id, test_org.id, "cli-test", [])

    def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        resp = await c.get("/api/installed")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_oauth_refresh_token_rejected_on_rest_endpoints(session, test_user, test_org):
    token = _issue_refresh_token(test_user.id, test_org.id, "cli-test", [])

    def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
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
async def test_revoked_oauth_access_token_rejected_on_rest_endpoints(session, test_user, test_org):
    token = _issue_access_token(test_user.id, test_org.id, "cli-test", [])
    session.add(
        OAuthRevokedToken(
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=int(time.time()) + 3600,
        )
    )
    session.commit()

    def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        resp = await c.get("/api/installed")

    app.dependency_overrides.clear()
    assert resp.status_code == 401
