import pytest


@pytest.mark.anyio
async def test_list_integrations(client):
    resp = await client.get("/api/integrations")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    ids = {i["id"] for i in data}
    # Sanity-check a known integration rather than enumerating all
    assert "github" in ids


@pytest.mark.anyio
async def test_list_integrations_filter_type(client):
    resp = await client.get("/api/integrations?type=remote_mcp")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1

    resp = await client.get("/api/integrations?type=custom")
    assert resp.status_code == 200
    api_data = resp.json()
    assert len(api_data) >= 2  # gmail and google_calendar
    api_ids = {i["id"] for i in api_data}
    assert "gmail" in api_ids
    assert "google_calendar" in api_ids


@pytest.mark.anyio
async def test_get_integration(client):
    resp = await client.get("/api/integrations/github")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "github"
    assert data["type"] == "remote_mcp"


@pytest.mark.anyio
async def test_get_integration_not_found(client):
    resp = await client.get("/api/integrations/nonexistent")
    assert resp.status_code == 404
