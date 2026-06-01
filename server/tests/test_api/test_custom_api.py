import json
from types import SimpleNamespace

import pytest
from sqlmodel import select

from agent_port.models.custom_api_integration import CustomApiIntegration
from agent_port.models.integration import InstalledIntegration
from agent_port.models.tool_cache import ToolCache


def _safe_url_stub(*args, **kwargs):
    return SimpleNamespace(hostname="api.example.com")


def _tool(name: str = "get_item") -> dict:
    return {
        "name": name,
        "description": "Get an item",
        "method": "GET",
        "path": "/v1/items/{id}",
        "params": [{"name": "id", "required": True}],
    }


@pytest.mark.anyio
async def test_create_list_get_custom_api(client, monkeypatch):
    monkeypatch.setattr("agent_port.api.custom_api.validate_safe_url", _safe_url_stub)

    resp = await client.post(
        "/api/integrations/custom-api",
        json={
            "name": "Example API",
            "description": "Example",
            "base_url": "https://api.example.com",
            "token_header": "X-API-Key",
            "token_format": "{token}",
            "tools": [_tool()],
        },
    )

    assert resp.status_code == 201
    created = resp.json()
    assert created["integration_id"] == "customapi_example_api"
    assert created["token_header"] == "X-API-Key"
    assert created["tools"][0]["method"] == "GET"

    list_resp = await client.get("/api/integrations/custom-api")
    assert list_resp.status_code == 200
    assert [item["id"] for item in list_resp.json()] == [created["id"]]

    get_resp = await client.get(f"/api/integrations/custom-api/{created['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["integration_id"] == created["integration_id"]


@pytest.mark.anyio
async def test_custom_api_validation_rejects_bad_tools(client, monkeypatch):
    monkeypatch.setattr("agent_port.api.custom_api.validate_safe_url", _safe_url_stub)

    resp = await client.post(
        "/api/integrations/custom-api",
        json={
            "name": "Bad API",
            "base_url": "https://api.example.com",
            "tools": [
                {
                    "name": "BadName",
                    "description": "Bad",
                    "method": "GET",
                    "path": "/items/{missing}",
                    "params": [],
                }
            ],
        },
    )

    assert resp.status_code == 400
    assert "Tool name" in resp.json()["detail"]


@pytest.mark.anyio
async def test_custom_api_surfaces_in_catalog(client, monkeypatch):
    monkeypatch.setattr("agent_port.api.custom_api.validate_safe_url", _safe_url_stub)

    create_resp = await client.post(
        "/api/integrations/custom-api",
        json={
            "name": "Catalog API",
            "base_url": "https://api.example.com",
            "tools": [_tool("list_items")],
        },
    )
    assert create_resp.status_code == 201
    integration_id = create_resp.json()["integration_id"]

    catalog_resp = await client.get(f"/api/integrations/{integration_id}")
    assert catalog_resp.status_code == 200
    data = catalog_resp.json()
    assert data["id"] == integration_id
    assert data["type"] == "custom"
    assert data["base_url"] == "https://api.example.com"
    assert data["auth"][0]["header"] == "Authorization"


@pytest.mark.anyio
async def test_custom_api_update_updates_installed_url_and_invalidates_cache(
    client, session, test_org, monkeypatch
):
    monkeypatch.setattr("agent_port.api.custom_api.validate_safe_url", _safe_url_stub)

    async def _refresh_one(*args, **kwargs):
        return None

    monkeypatch.setattr("agent_port.api.custom_api.refresh_one", _refresh_one)

    create_resp = await client.post(
        "/api/integrations/custom-api",
        json={"name": "Installed API", "base_url": "https://api.example.com", "tools": [_tool()]},
    )
    row_id = create_resp.json()["id"]
    integration_id = create_resp.json()["integration_id"]

    installed = InstalledIntegration(
        org_id=test_org.id,
        integration_id=integration_id,
        type="custom",
        url="https://api.example.com",
        auth_method="token",
        connected=True,
    )
    session.add(installed)
    session.add(
        ToolCache(
            org_id=test_org.id,
            integration_id=integration_id,
            tools_json=json.dumps([{"name": "old"}]),
        )
    )
    session.commit()

    resp = await client.patch(
        f"/api/integrations/custom-api/{row_id}",
        json={"base_url": "https://api2.example.com", "tools": [_tool("get_other")]},
    )

    assert resp.status_code == 200
    refreshed_installed = session.exec(
        select(InstalledIntegration).where(InstalledIntegration.integration_id == integration_id)
    ).first()
    assert refreshed_installed.url == "https://api2.example.com"
    cache = session.exec(
        select(ToolCache).where(ToolCache.integration_id == integration_id)
    ).first()
    assert cache is None


@pytest.mark.anyio
async def test_custom_api_delete_requires_uninstall(client, session, test_org, monkeypatch):
    monkeypatch.setattr("agent_port.api.custom_api.validate_safe_url", _safe_url_stub)
    create_resp = await client.post(
        "/api/integrations/custom-api",
        json={"name": "Delete API", "base_url": "https://api.example.com", "tools": []},
    )
    row_id = create_resp.json()["id"]
    integration_id = create_resp.json()["integration_id"]
    session.add(
        InstalledIntegration(
            org_id=test_org.id,
            integration_id=integration_id,
            type="custom",
            url="https://api.example.com",
            auth_method="token",
            connected=True,
        )
    )
    session.commit()

    resp = await client.delete(f"/api/integrations/custom-api/{row_id}")

    assert resp.status_code == 409


@pytest.mark.anyio
async def test_custom_api_test_uses_browser_token_and_redacts_response(
    client, monkeypatch, session
):
    monkeypatch.setattr("agent_port.api.custom_api.validate_safe_url", _safe_url_stub)

    async def _dispatch(**kwargs):
        assert kwargs["headers"] == {"Authorization": "Bearer sk_test_secret"}
        return {
            "content": [{"type": "text", "text": "token=sk_test_secret"}],
            "isError": False,
            "status_code": 200,
            "duration_ms": 12,
        }

    monkeypatch.setattr("agent_port.api.custom_api.api_client.dispatch_api_tool", _dispatch)

    resp = await client.post(
        "/api/integrations/custom-api/test",
        json={
            "base_url": "https://api.example.com",
            "token": "sk_test_secret",
            "tool": _tool(),
            "args": {"id": "123"},
        },
    )

    assert resp.status_code == 200
    assert resp.json()["content"][0]["text"] == "token=[redacted]"
    assert session.exec(select(CustomApiIntegration)).all() == []


@pytest.mark.anyio
async def test_custom_api_test_rejects_localhost(client):
    resp = await client.post(
        "/api/integrations/custom-api/test",
        json={
            "base_url": "http://127.0.0.1:8000",
            "token": "secret",
            "tool": _tool(),
            "args": {"id": "123"},
        },
    )

    assert resp.status_code == 400
    assert "blocked network range" in resp.json()["detail"]


@pytest.mark.anyio
async def test_custom_api_test_does_not_leak_stored_token_to_other_targets(
    client, session, test_org, monkeypatch
):
    """The stored installed token must only be reused when the test request
    targets the same connection that owns it. Otherwise a caller could swap
    base_url to a domain they control and have us send the secret there.
    """
    monkeypatch.setattr("agent_port.api.custom_api.validate_safe_url", _safe_url_stub)

    create_resp = await client.post(
        "/api/integrations/custom-api",
        json={
            "name": "Tokened API",
            "base_url": "https://api.example.com",
            "token_header": "Authorization",
            "token_format": "Bearer {token}",
            "tools": [_tool()],
        },
    )
    assert create_resp.status_code == 201
    row_id = create_resp.json()["id"]
    integration_id = create_resp.json()["integration_id"]

    from agent_port.secrets.records import upsert_secret

    secret = upsert_secret(
        session,
        org_id=test_org.id,
        kind="integration_token",
        ref=f"integrations/{test_org.id}/{integration_id}/token",
        value="sk_live_super_secret",
        secret_id=None,
    )
    installed = InstalledIntegration(
        org_id=test_org.id,
        integration_id=integration_id,
        type="custom",
        url="https://api.example.com",
        auth_method="token",
        connected=True,
        token_secret_id=secret.id,
    )
    session.add(installed)
    session.commit()

    captured_headers: dict = {}

    async def _dispatch(**kwargs):
        captured_headers.update(kwargs["headers"])
        return {
            "content": [{"type": "text", "text": "ok"}],
            "isError": False,
            "status_code": 200,
            "duration_ms": 1,
        }

    monkeypatch.setattr("agent_port.api.custom_api.api_client.dispatch_api_tool", _dispatch)

    # Caller omits token AND swaps base_url to an attacker-controlled host.
    resp = await client.post(
        "/api/integrations/custom-api/test",
        json={
            "base_url": "https://attacker.example.com",
            "token_header": "Authorization",
            "token_format": "Bearer {token}",
            "token": "",
            "integration_db_id": row_id,
            "tool": _tool(),
            "args": {"id": "1"},
        },
    )

    assert resp.status_code == 200
    # The stored token must NOT have been injected — Authorization is either
    # absent or empty, never the real secret.
    assert "sk_live_super_secret" not in captured_headers.get("Authorization", "")


@pytest.mark.anyio
async def test_custom_api_test_uses_stored_token_for_same_target(
    client, session, test_org, monkeypatch
):
    monkeypatch.setattr("agent_port.api.custom_api.validate_safe_url", _safe_url_stub)

    create_resp = await client.post(
        "/api/integrations/custom-api",
        json={
            "name": "Same Target",
            "base_url": "https://api.example.com",
            "token_header": "Authorization",
            "token_format": "Bearer {token}",
            "tools": [_tool()],
        },
    )
    row_id = create_resp.json()["id"]
    integration_id = create_resp.json()["integration_id"]

    from agent_port.secrets.records import upsert_secret

    secret = upsert_secret(
        session,
        org_id=test_org.id,
        kind="integration_token",
        ref=f"integrations/{test_org.id}/{integration_id}/token",
        value="sk_same_target",
        secret_id=None,
    )
    session.add(
        InstalledIntegration(
            org_id=test_org.id,
            integration_id=integration_id,
            type="custom",
            url="https://api.example.com",
            auth_method="token",
            connected=True,
            token_secret_id=secret.id,
        )
    )
    session.commit()

    captured_headers: dict = {}

    async def _dispatch(**kwargs):
        captured_headers.update(kwargs["headers"])
        return {"content": [], "isError": False, "status_code": 200, "duration_ms": 1}

    monkeypatch.setattr("agent_port.api.custom_api.api_client.dispatch_api_tool", _dispatch)

    resp = await client.post(
        "/api/integrations/custom-api/test",
        json={
            "base_url": "https://api.example.com",
            "token_header": "Authorization",
            "token_format": "Bearer {token}",
            "token": "",
            "integration_db_id": row_id,
            "tool": _tool(),
            "args": {"id": "1"},
        },
    )

    assert resp.status_code == 200
    assert captured_headers.get("Authorization") == "Bearer sk_same_target"


@pytest.mark.anyio
async def test_custom_api_patch_can_switch_to_no_auth(client, monkeypatch):
    """Switching token auth → no auth sets both header and format to empty;
    the merged pair must be validated once, not field-by-field against the
    other field's old value.
    """
    monkeypatch.setattr("agent_port.api.custom_api.validate_safe_url", _safe_url_stub)

    async def _refresh_one(*args, **kwargs):
        return None

    monkeypatch.setattr("agent_port.api.custom_api.refresh_one", _refresh_one)

    create_resp = await client.post(
        "/api/integrations/custom-api",
        json={
            "name": "Switch Auth",
            "base_url": "https://api.example.com",
            "token_header": "Authorization",
            "token_format": "Bearer {token}",
            "tools": [],
        },
    )
    assert create_resp.status_code == 201
    row_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/api/integrations/custom-api/{row_id}",
        json={"token_header": "", "token_format": ""},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["token_header"] == ""
    assert body["token_format"] == ""


@pytest.mark.anyio
async def test_dispatch_api_tool_revalidates_url_at_dispatch_time():
    """The api_client must re-check URL safety at dispatch time so a hostname
    whose A records have changed to point at internal IPs is caught before we
    connect.
    """
    from agent_port import api_client
    from agent_port.integrations.types import ApiTool, Param

    tool = ApiTool(
        name="ping",
        description="ping",
        method="GET",
        path="/v1/ping",
        params=[Param(name="id", type="string", required=True)],
    )

    result = await api_client.dispatch_api_tool(
        base_url="http://127.0.0.1:8000",
        tool_def=tool,
        args={"id": "1"},
        headers={},
    )

    assert result["isError"] is True
    assert "Unsafe upstream URL" in result["content"][0]["text"]
