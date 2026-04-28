import pytest

from agent_port.config import settings


@pytest.mark.asyncio
async def test_get_returns_default_when_no_override(client):
    res = await client.get("/api/org-settings")
    assert res.status_code == 200
    body = res.json()
    assert body["approval_expiry_minutes_default"] == settings.approval_expiry_minutes
    assert body["approval_expiry_minutes_override"] is None
    assert body["approval_expiry_minutes"] == settings.approval_expiry_minutes


@pytest.mark.asyncio
async def test_patch_sets_override_and_get_reflects_it(client):
    res = await client.patch(
        "/api/org-settings",
        json={"approval_expiry_minutes": 45},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["approval_expiry_minutes_override"] == 45
    assert body["approval_expiry_minutes"] == 45

    res = await client.get("/api/org-settings")
    assert res.json()["approval_expiry_minutes"] == 45


@pytest.mark.asyncio
async def test_patch_with_null_clears_override(client):
    await client.patch("/api/org-settings", json={"approval_expiry_minutes": 60})
    res = await client.patch("/api/org-settings", json={"approval_expiry_minutes": None})
    body = res.json()
    assert body["approval_expiry_minutes_override"] is None
    assert body["approval_expiry_minutes"] == settings.approval_expiry_minutes


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [0, -1, 1441, 100000])
async def test_patch_rejects_out_of_range_values(client, value):
    res = await client.patch(
        "/api/org-settings",
        json={"approval_expiry_minutes": value},
    )
    assert res.status_code == 400
