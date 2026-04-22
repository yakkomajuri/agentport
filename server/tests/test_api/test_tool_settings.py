import pytest


@pytest.mark.anyio
async def test_list_settings_empty(client):
    resp = await client.get("/api/tool-settings/github")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_set_and_list_settings(client):
    resp = await client.put(
        "/api/tool-settings/github/create_issue",
        json={"mode": "allow"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "allow"
    assert data["integration_id"] == "github"
    assert data["tool_name"] == "create_issue"

    resp = await client.get("/api/tool-settings/github")
    assert resp.status_code == 200
    settings = resp.json()
    assert len(settings) == 1
    assert settings[0]["mode"] == "allow"


@pytest.mark.anyio
async def test_update_existing_setting(client):
    await client.put(
        "/api/tool-settings/github/create_issue",
        json={"mode": "allow"},
    )
    resp = await client.put(
        "/api/tool-settings/github/create_issue",
        json={"mode": "require_approval"},
    )
    assert resp.status_code == 200
    assert resp.json()["mode"] == "require_approval"


@pytest.mark.anyio
async def test_invalid_mode_rejected(client):
    resp = await client.put(
        "/api/tool-settings/github/create_issue",
        json={"mode": "invalid"},
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_list_approval_requests(client):
    resp = await client.get("/api/tool-approvals/requests")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_get_nonexistent_request(client):
    import uuid

    resp = await client.get(f"/api/tool-approvals/requests/{uuid.uuid4()}")
    assert resp.status_code == 404
