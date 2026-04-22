import pytest


@pytest.mark.anyio
async def test_list_installed_empty(client):
    resp = await client.get("/api/installed")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_install_with_token(client):
    resp = await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "token",
            "token": "phx_test_key",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["integration_id"] == "posthog"
    assert data["type"] == "remote_mcp"
    assert data["has_token"] is True
    assert data["connected"] is True
    assert "token" not in data


@pytest.mark.anyio
async def test_install_with_oauth(client):
    resp = await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "oauth",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["auth_method"] == "oauth"
    assert data["has_token"] is False
    assert data["connected"] is False
    assert "token" not in data


@pytest.mark.anyio
async def test_update_token_marks_token_integration_connected(client):
    await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "token",
            "token": "old_token",
        },
    )

    resp = await client.patch(
        "/api/installed/posthog",
        json={
            "token": "new_token",
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["has_token"] is True
    assert data["connected"] is True
    assert "token" not in data


@pytest.mark.anyio
async def test_update_token_rejected_for_oauth_integration(client):
    await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "oauth",
        },
    )

    resp = await client.patch(
        "/api/installed/posthog",
        json={
            "token": "should_not_apply",
        },
    )

    assert resp.status_code == 400

    resp = await client.get("/api/installed")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["integration_id"] == "posthog"
    assert data[0]["has_token"] is False
    assert data[0]["connected"] is False
    assert "token" not in data[0]


@pytest.mark.anyio
async def test_install_unknown_integration(client):
    resp = await client.post(
        "/api/installed",
        json={
            "integration_id": "unknown",
            "auth_method": "token",
            "token": "abc",
        },
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_install_duplicate_integration(client):
    payload = {
        "integration_id": "posthog",
        "auth_method": "token",
        "token": "phx_key",
    }
    resp = await client.post("/api/installed", json=payload)
    assert resp.status_code == 201

    resp = await client.post("/api/installed", json=payload)
    assert resp.status_code == 409


@pytest.mark.anyio
async def test_install_token_required(client):
    resp = await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "token",
        },
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_install_invalid_auth_method(client):
    resp = await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "api_key",
            "token": "test",
        },
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_remove_installed(client):
    await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "token",
            "token": "phx_key",
        },
    )

    resp = await client.delete("/api/installed/posthog")
    assert resp.status_code == 204

    resp = await client.get("/api/installed")
    assert resp.json() == []


@pytest.mark.anyio
async def test_remove_not_found(client):
    resp = await client.delete("/api/installed/nonexistent")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_list_installed_does_not_expose_secrets(client):
    """Verify that GET /api/installed never returns token values."""
    await client.post(
        "/api/installed",
        json={
            "integration_id": "github",
            "auth_method": "token",
            "token": "super_secret_token_value",
        },
    )
    await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "oauth",
        },
    )

    resp = await client.get("/api/installed")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    raw = resp.text
    assert "super_secret_token_value" not in raw
    for item in items:
        assert "token" not in item
        assert "token_secret_id" not in item


@pytest.mark.anyio
async def test_create_installed_does_not_expose_secrets(client):
    """Verify that POST /api/installed never returns the submitted token."""
    resp = await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "token",
            "token": "my_secret_key_12345",
        },
    )
    assert resp.status_code == 201
    assert "my_secret_key_12345" not in resp.text
    data = resp.json()
    assert "token" not in data
    assert "token_secret_id" not in data
    assert data["has_token"] is True


@pytest.mark.anyio
async def test_update_installed_does_not_expose_secrets(client):
    """Verify that PATCH /api/installed/{integration_id} never returns the new token."""
    await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "token",
            "token": "initial_secret",
        },
    )

    resp = await client.patch(
        "/api/installed/posthog",
        json={"token": "updated_secret_value"},
    )
    assert resp.status_code == 200
    assert "updated_secret_value" not in resp.text
    assert "initial_secret" not in resp.text
    data = resp.json()
    assert "token" not in data
    assert "token_secret_id" not in data
    assert data["has_token"] is True
