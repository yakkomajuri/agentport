from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import select

from agent_port.models.integration import InstalledIntegration
from agent_port.models.tool_execution import ToolExecutionSetting


@pytest.mark.anyio
async def test_list_tools_not_found(client):
    resp = await client.get("/api/tools/nonexistent")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_list_tools_for_integration(client):
    await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "token",
            "token": "phx_key",
        },
    )

    mock_tools = [
        {"name": "create_annotation", "description": "Create annotation", "inputSchema": {}}
    ]
    with patch("agent_port.mcp.client.list_tools", new_callable=AsyncMock, return_value=mock_tools):
        resp = await client.get("/api/tools/posthog")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "create_annotation"


@pytest.mark.anyio
async def test_list_all_tools(client):
    await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "token",
            "token": "phx_key",
        },
    )

    mock_tools = [{"name": "tool1", "description": "Tool 1", "inputSchema": {}}]
    with patch("agent_port.mcp.client.list_tools", new_callable=AsyncMock, return_value=mock_tools):
        resp = await client.get("/api/tools")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["integration_id"] == "posthog"


@pytest.mark.anyio
async def test_list_tools_applies_execution_modes_in_bulk(client, session, test_org):
    await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "token",
            "token": "phx_key",
        },
    )

    session.add(
        ToolExecutionSetting(
            org_id=test_org.id,
            integration_id="posthog",
            tool_name="tool_allow",
            mode="allow",
        )
    )
    session.commit()

    mock_tools = [
        {"name": "tool_allow", "description": "Allowed tool", "inputSchema": {}},
        {"name": "tool_default", "description": "Default tool", "inputSchema": {}},
    ]
    with patch("agent_port.mcp.client.list_tools", new_callable=AsyncMock, return_value=mock_tools):
        resp = await client.get("/api/tools/posthog")

    assert resp.status_code == 200
    data = {tool["name"]: tool for tool in resp.json()}
    assert data["tool_allow"]["execution_mode"] == "allow"
    assert data["tool_default"]["execution_mode"] == "require_approval"


@pytest.mark.anyio
async def test_list_tools_waits_for_in_progress_refresh(client, session, test_org, monkeypatch):
    await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "token",
            "token": "phx_key",
        },
    )

    installed = session.exec(
        select(InstalledIntegration)
        .where(InstalledIntegration.org_id == test_org.id)
        .where(InstalledIntegration.integration_id == "posthog")
    ).first()
    assert installed is not None
    installed.updating_tool_cache = True
    session.add(installed)
    session.commit()

    waited_tools = [
        {"name": "cached_tool", "description": "Loaded from cache warmup", "inputSchema": {}}
    ]

    async def fake_wait_for_in_progress_refresh(_installed, _session):
        return waited_tools

    monkeypatch.setattr(
        "agent_port.api.tools._wait_for_in_progress_refresh",
        fake_wait_for_in_progress_refresh,
    )

    with patch(
        "agent_port.mcp.client.list_tools",
        new_callable=AsyncMock,
        side_effect=AssertionError("should not hit upstream while refresh is in progress"),
    ):
        resp = await client.get("/api/tools/posthog")

    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "cached_tool"


@pytest.mark.anyio
async def test_call_tool(client, session, test_org):
    await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "token",
            "token": "phx_key",
        },
    )

    # Set tool to allow mode so it can be called without approval
    session.add(
        ToolExecutionSetting(
            org_id=test_org.id,
            integration_id="posthog",
            tool_name="create_annotation",
            mode="allow",
        )
    )
    session.commit()

    mock_result = {"content": [{"type": "text", "text": "done"}], "isError": False}
    with patch("agent_port.mcp.client.call_tool", new_callable=AsyncMock, return_value=mock_result):
        resp = await client.post(
            "/api/tools/posthog/call",
            json={"tool_name": "create_annotation", "args": {"content": "test"}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["isError"] is False
        assert data["content"][0]["text"] == "done"


@pytest.mark.anyio
async def test_call_tool_not_found(client):
    resp = await client.post(
        "/api/tools/nonexistent/call",
        json={"tool_name": "test", "args": {}},
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_call_tool_with_additional_info_on_executed_path(client, session, test_org):
    """`additional_info` flows through to the log on the allow-mode path."""
    await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "token",
            "token": "phx_key",
        },
    )

    session.add(
        ToolExecutionSetting(
            org_id=test_org.id,
            integration_id="posthog",
            tool_name="create_annotation",
            mode="allow",
        )
    )
    session.commit()

    mock_result = {"content": [{"type": "text", "text": "done"}], "isError": False}
    with patch("agent_port.mcp.client.call_tool", new_callable=AsyncMock, return_value=mock_result):
        resp = await client.post(
            "/api/tools/posthog/call",
            json={
                "tool_name": "create_annotation",
                "args": {"content": "test"},
                "additional_info": "Verifying the annotation flow before a release.",
            },
        )
        assert resp.status_code == 200

    logs = (await client.get("/api/logs")).json()
    assert len(logs) == 1
    assert logs[0]["additional_info"] == "Verifying the annotation flow before a release."


@pytest.mark.anyio
async def test_call_tool_without_additional_info_still_works(client, session, test_org):
    """Absent `additional_info` must not break existing callers."""
    await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "token",
            "token": "phx_key",
        },
    )
    session.add(
        ToolExecutionSetting(
            org_id=test_org.id,
            integration_id="posthog",
            tool_name="create_annotation",
            mode="allow",
        )
    )
    session.commit()

    mock_result = {"content": [{"type": "text", "text": "done"}], "isError": False}
    with patch("agent_port.mcp.client.call_tool", new_callable=AsyncMock, return_value=mock_result):
        resp = await client.post(
            "/api/tools/posthog/call",
            json={"tool_name": "create_annotation", "args": {"content": "test"}},
        )
        assert resp.status_code == 200

    logs = (await client.get("/api/logs")).json()
    assert len(logs) == 1
    assert logs[0].get("additional_info") is None


@pytest.mark.anyio
async def test_call_tool_logs_entry(client, session, test_org):
    await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "token",
            "token": "phx_key",
        },
    )

    # Set tool to allow mode
    session.add(
        ToolExecutionSetting(
            org_id=test_org.id,
            integration_id="posthog",
            tool_name="my_tool",
            mode="allow",
        )
    )
    session.commit()

    mock_result = {"content": [{"type": "text", "text": "ok"}], "isError": False}
    with patch("agent_port.mcp.client.call_tool", new_callable=AsyncMock, return_value=mock_result):
        await client.post(
            "/api/tools/posthog/call",
            json={"tool_name": "my_tool", "args": {"x": 1}},
        )

    resp = await client.get("/api/logs")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["tool_name"] == "my_tool"
    assert data[0]["integration_id"] == "posthog"
    assert data[0]["outcome"] == "executed"
