import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import select

from agent_port.approvals import events as approval_events
from agent_port.models.tool_execution import ToolExecutionSetting


@pytest.mark.anyio
async def test_call_tool_blocked_by_default(client):
    await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "token",
            "token": "phx_key",
        },
    )
    resp = await client.post(
        "/api/tools/posthog/call",
        json={"tool_name": "create_annotation", "args": {"content": "test"}},
    )
    assert resp.status_code == 403
    data = resp.json()
    assert data["error"] == "approval_required"
    assert "approval_request_id" in data
    assert "/approve/" in data["approval_url"]
    assert "approval" in data["message"].lower()
    assert data["integration_id"] == "posthog"
    assert data["tool_name"] == "create_annotation"


@pytest.mark.anyio
async def test_call_tool_allowed_mode(client, session, test_org):
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
            tool_name="create_annotation",
            mode="allow",
        )
    )
    session.commit()

    mock_result = {"content": [{"type": "text", "text": "done"}], "isError": False}
    with patch(
        "agent_port.mcp.client.call_tool",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        resp = await client.post(
            "/api/tools/posthog/call",
            json={"tool_name": "create_annotation", "args": {"content": "test"}},
        )
    assert resp.status_code == 200
    assert resp.json()["isError"] is False


@pytest.mark.anyio
async def test_approve_once_flow(client, session, test_org):
    """Full flow: blocked → approve once → retry succeeds"""
    await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "token",
            "token": "phx_key",
        },
    )

    # 1. Call blocked
    resp = await client.post(
        "/api/tools/posthog/call",
        json={"tool_name": "create_annotation", "args": {"content": "test"}},
    )
    assert resp.status_code == 403
    request_id = resp.json()["approval_request_id"]

    # 2. Approve once
    resp = await client.post(f"/api/tool-approvals/requests/{request_id}/approve-once")
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    assert resp.json()["decision_mode"] == "approve_once"

    # 3. Retry - should succeed (consumes the approval)
    mock_result = {"content": [{"type": "text", "text": "done"}], "isError": False}
    with patch(
        "agent_port.mcp.client.call_tool",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        resp = await client.post(
            "/api/tools/posthog/call",
            json={"tool_name": "create_annotation", "args": {"content": "test"}},
        )
    assert resp.status_code == 200

    # 4. Another retry without new approval - blocked again
    resp = await client.post(
        "/api/tools/posthog/call",
        json={"tool_name": "create_annotation", "args": {"content": "test"}},
    )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_allow_tool_flow(client, session, test_org):
    """Full flow: blocked → allow tool → any args succeed"""
    await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "token",
            "token": "phx_key",
        },
    )

    # 1. Call blocked
    resp = await client.post(
        "/api/tools/posthog/call",
        json={"tool_name": "create_annotation", "args": {"content": "test"}},
    )
    assert resp.status_code == 403
    request_id = resp.json()["approval_request_id"]

    # 2. Allow tool (wildcard)
    resp = await client.post(f"/api/tool-approvals/requests/{request_id}/allow-tool")
    assert resp.status_code == 200
    assert resp.json()["decision_mode"] == "allow_tool_forever"

    # Verify tool execution setting was created with mode=allow
    setting = session.exec(
        select(ToolExecutionSetting)
        .where(ToolExecutionSetting.org_id == test_org.id)
        .where(ToolExecutionSetting.integration_id == "posthog")
        .where(ToolExecutionSetting.tool_name == "create_annotation")
    ).first()
    assert setting is not None
    assert setting.mode == "allow"

    # 3. Retry with same args - should succeed
    mock_result = {"content": [{"type": "text", "text": "done"}], "isError": False}
    with patch(
        "agent_port.mcp.client.call_tool",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        resp = await client.post(
            "/api/tools/posthog/call",
            json={"tool_name": "create_annotation", "args": {"content": "test"}},
        )
    assert resp.status_code == 200

    # 4. Different args - should also succeed (wildcard)
    with patch(
        "agent_port.mcp.client.call_tool",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        resp = await client.post(
            "/api/tools/posthog/call",
            json={"tool_name": "create_annotation", "args": {"content": "different"}},
        )
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_deny_flow(client):
    await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "token",
            "token": "phx_key",
        },
    )

    resp = await client.post(
        "/api/tools/posthog/call",
        json={"tool_name": "create_annotation", "args": {"content": "test"}},
    )
    assert resp.status_code == 403
    request_id = resp.json()["approval_request_id"]

    resp = await client.post(f"/api/tool-approvals/requests/{request_id}/deny")
    assert resp.status_code == 200
    assert resp.json()["status"] == "denied"

    # Retry still blocked (new pending request created)
    resp = await client.post(
        "/api/tools/posthog/call",
        json={"tool_name": "create_annotation", "args": {"content": "test"}},
    )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_duplicate_blocked_calls_reuse_request(client):
    await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "token",
            "token": "phx_key",
        },
    )

    resp1 = await client.post(
        "/api/tools/posthog/call",
        json={"tool_name": "create_annotation", "args": {"content": "test"}},
    )
    resp2 = await client.post(
        "/api/tools/posthog/call",
        json={"tool_name": "create_annotation", "args": {"content": "test"}},
    )
    assert resp1.json()["approval_request_id"] == resp2.json()["approval_request_id"]


@pytest.mark.anyio
async def test_cannot_approve_already_approved(client):
    await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "token",
            "token": "phx_key",
        },
    )

    resp = await client.post(
        "/api/tools/posthog/call",
        json={"tool_name": "create_annotation", "args": {"content": "test"}},
    )
    request_id = resp.json()["approval_request_id"]

    await client.post(f"/api/tool-approvals/requests/{request_id}/approve-once")
    resp = await client.post(f"/api/tool-approvals/requests/{request_id}/approve-once")
    assert resp.status_code == 409


@pytest.mark.anyio
async def test_additional_info_is_stored_on_approval_request(client):
    """The agent's rationale must be surfaced on the approval request for humans."""
    await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "token",
            "token": "phx_key",
        },
    )

    resp = await client.post(
        "/api/tools/posthog/call",
        json={
            "tool_name": "create_annotation",
            "args": {"content": "test"},
            "additional_info": "I need to annotate the release marker before proceeding.",
        },
    )
    assert resp.status_code == 403
    request_id = resp.json()["approval_request_id"]

    # Approval object returned by the decision endpoint includes the field
    approve_resp = await client.post(f"/api/tool-approvals/requests/{request_id}/approve-once")
    assert approve_resp.status_code == 200
    assert (
        approve_resp.json()["additional_info"]
        == "I need to annotate the release marker before proceeding."
    )

    # The pending log created alongside the request also carries the note
    logs = (await client.get("/api/logs")).json()
    assert any(
        entry["additional_info"] == "I need to annotate the release marker before proceeding."
        for entry in logs
    )


@pytest.mark.anyio
async def test_duplicate_blocked_calls_fill_in_additional_info(client):
    """Reusing a pending request should pick up a rationale supplied on a later retry."""
    await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "token",
            "token": "phx_key",
        },
    )

    # First call: no rationale
    resp1 = await client.post(
        "/api/tools/posthog/call",
        json={"tool_name": "create_annotation", "args": {"content": "test"}},
    )
    req_id_1 = resp1.json()["approval_request_id"]

    # Second call: same args, now with a rationale — the approval request should
    # be reused and gain the additional_info
    resp2 = await client.post(
        "/api/tools/posthog/call",
        json={
            "tool_name": "create_annotation",
            "args": {"content": "test"},
            "additional_info": "Explaining the second try.",
        },
    )
    assert resp2.status_code == 403
    assert resp2.json()["approval_request_id"] == req_id_1

    fetched = await client.get(f"/api/tool-approvals/requests/{req_id_1}")
    assert fetched.status_code == 200
    assert fetched.json()["additional_info"] == "Explaining the second try."


@pytest.mark.anyio
async def test_list_tool_includes_execution_mode(client):
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
    with patch(
        "agent_port.mcp.client.list_tools",
        new_callable=AsyncMock,
        return_value=mock_tools,
    ):
        resp = await client.get("/api/tools/posthog")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["execution_mode"] == "require_approval"


@pytest.mark.anyio
async def test_list_all_tools_includes_execution_mode(client, session, test_org):
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
            tool_name="tool1",
            mode="allow",
        )
    )
    session.commit()

    mock_tools = [{"name": "tool1", "description": "Tool 1", "inputSchema": {}}]
    with patch(
        "agent_port.mcp.client.list_tools",
        new_callable=AsyncMock,
        return_value=mock_tools,
    ):
        resp = await client.get("/api/tools")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["execution_mode"] == "allow"


# ── approve endpoints must fire notify_decision to wake await_approval waiters ──


@pytest.fixture
def _clean_events():
    """Snapshot + reset the in-process events dicts around a test."""
    approval_events._events.clear()
    approval_events._statuses.clear()
    approval_events._refcounts.clear()
    yield
    approval_events._events.clear()
    approval_events._statuses.clear()
    approval_events._refcounts.clear()


def _seed_pending_request(session, test_org):
    """Insert a pending ToolApprovalRequest directly — sidesteps the /api/installed
    + /api/tools/.../call setup path to keep these tests focused on the notify wiring."""
    from datetime import datetime, timedelta

    from agent_port.models.tool_approval_request import ToolApprovalRequest

    req = ToolApprovalRequest(
        org_id=test_org.id,
        integration_id="posthog",
        tool_name="create_annotation",
        args_json="{}",
        args_hash="deadbeef",
        summary_text="test call",
        status="pending",
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    session.add(req)
    session.commit()
    session.refresh(req)
    return req


@pytest.mark.anyio
async def test_approve_once_endpoint_notifies_waiters(client, session, test_org, _clean_events):
    """A waiter parked on wait_for_decision should wake up when /approve-once commits."""
    req = _seed_pending_request(session, test_org)

    async def waiter():
        return await approval_events.wait_for_decision(req.id, timeout=2.0)

    waiter_task = asyncio.create_task(waiter())
    # Let the waiter park before firing the HTTP call.
    await asyncio.sleep(0.05)

    approve_resp = await client.post(f"/api/tool-approvals/requests/{req.id}/approve-once")
    assert approve_resp.status_code == 200

    status = await asyncio.wait_for(waiter_task, timeout=1.0)
    assert status == "approved"


@pytest.mark.anyio
async def test_deny_endpoint_notifies_waiters(client, session, test_org, _clean_events):
    req = _seed_pending_request(session, test_org)

    async def waiter():
        return await approval_events.wait_for_decision(req.id, timeout=2.0)

    waiter_task = asyncio.create_task(waiter())
    await asyncio.sleep(0.05)

    deny_resp = await client.post(f"/api/tool-approvals/requests/{req.id}/deny")
    assert deny_resp.status_code == 200

    status = await asyncio.wait_for(waiter_task, timeout=1.0)
    assert status == "denied"


@pytest.mark.anyio
async def test_allow_tool_endpoint_notifies_waiters(client, session, test_org, _clean_events):
    req = _seed_pending_request(session, test_org)

    async def waiter():
        return await approval_events.wait_for_decision(req.id, timeout=2.0)

    waiter_task = asyncio.create_task(waiter())
    await asyncio.sleep(0.05)

    allow_resp = await client.post(f"/api/tool-approvals/requests/{req.id}/allow-tool")
    assert allow_resp.status_code == 200

    status = await asyncio.wait_for(waiter_task, timeout=1.0)
    assert status == "approved"
