import hashlib

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from agent_port.main import app
from agent_port.models.api_key import ApiKey


@pytest.mark.asyncio
async def test_create_api_key(client):
    resp = await client.post("/api/api-keys", json={"name": "my-key"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "my-key"
    assert data["plain_key"].startswith("ap_")
    assert len(data["plain_key"]) > 20
    assert "key_prefix" in data
    assert data["key_prefix"] == data["plain_key"][:12]


@pytest.mark.asyncio
async def test_create_api_key_requires_auth(session, test_org):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post("/api/api-keys", json={"name": "x"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_api_keys_no_plain_key(client):
    await client.post("/api/api-keys", json={"name": "k1"})
    await client.post("/api/api-keys", json={"name": "k2"})
    resp = await client.get("/api/api-keys")
    assert resp.status_code == 200
    keys = resp.json()
    assert len(keys) == 2
    for k in keys:
        assert "plain_key" not in k
        assert "key_prefix" in k
        assert "is_active" in k
        assert "last_used_at" in k


@pytest.mark.asyncio
async def test_revoke_api_key(client, session):
    create_resp = await client.post("/api/api-keys", json={"name": "to-revoke"})
    key_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/api-keys/{key_id}")
    assert resp.status_code == 204

    resp = await client.get("/api/api-keys")
    matching = [k for k in resp.json() if k["id"] == key_id]
    assert matching[0]["is_active"] is False


@pytest.mark.asyncio
async def test_revoke_wrong_org_returns_404(client):
    import uuid

    fake_id = str(uuid.uuid4())
    resp = await client.delete(f"/api/api-keys/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_key_authenticates_list_tools(agent_key_client):
    resp = await agent_key_client.get("/api/tools")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_api_key_authenticates_list_installed(agent_key_client):
    resp = await agent_key_client.get("/api/installed")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_api_key_updates_last_used_at(agent_key_client, api_key_record, session):
    api_key, _ = api_key_record
    assert api_key.last_used_at is None

    await agent_key_client.get("/api/tools")

    session.refresh(api_key)
    assert api_key.last_used_at is not None


@pytest.mark.asyncio
async def test_invalid_api_key_returns_401(session, test_user, test_org):
    from agent_port.db import get_session
    from agent_port.dependencies import get_current_org, get_current_user

    def override_session():
        yield session

    def override_user():
        return test_user

    def override_org():
        return test_org

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_current_org] = override_org

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-API-Key": "ap_thisisnotavalidkey"},
    ) as c:
        resp = await c.get("/api/tools")

    app.dependency_overrides.clear()
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_api_key_cannot_reach_approvals(session, api_key_record):
    """Approval endpoints use get_current_user (JWT-only). API key must be rejected."""
    from agent_port.db import get_session

    _, plain_key = api_key_record

    def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    # No user/org/agent_auth overrides — real JWT check runs
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-API-Key": plain_key},
    ) as c:
        resp = await c.get("/api/tool-approvals/requests")
    app.dependency_overrides.clear()
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_api_key_cannot_change_tool_settings(session, test_org, api_key_record):
    """Tool-settings endpoints use get_current_user (JWT-only). API key must be rejected."""
    from agent_port.db import get_session
    from agent_port.models.integration import InstalledIntegration

    _, plain_key = api_key_record

    installed = InstalledIntegration(
        org_id=test_org.id,
        integration_id="posthog",
        type="remote_mcp",
        url="https://mcp.posthog.com/mcp",
        auth_method="token",
    )
    session.add(installed)
    session.commit()

    def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-API-Key": plain_key},
    ) as c:
        resp = await c.put(
            "/api/tool-settings/posthog/some_tool",
            json={"mode": "allow"},
        )
    app.dependency_overrides.clear()
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_revoked_key_returns_401(session, test_user, test_org, api_key_record):
    from agent_port.db import get_session
    from agent_port.dependencies import get_current_org, get_current_user

    api_key, plain_key = api_key_record
    api_key.is_active = False
    session.add(api_key)
    session.commit()

    def override_session():
        yield session

    def override_user():
        return test_user

    def override_org():
        return test_org

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_current_org] = override_org

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-API-Key": plain_key},
    ) as c:
        resp = await c.get("/api/tools")

    app.dependency_overrides.clear()
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_key_hash_stored_not_plain(client, session):
    resp = await client.post("/api/api-keys", json={"name": "hash-check"})
    plain_key = resp.json()["plain_key"]

    stored = session.exec(select(ApiKey).where(ApiKey.name == "hash-check")).first()
    assert stored is not None
    expected_hash = hashlib.sha256(plain_key.encode()).hexdigest()
    assert stored.key_hash == expected_hash
    assert plain_key not in (stored.key_prefix, stored.key_hash)
