"""Unit tests for the MCP server aggregator."""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from agent_port.approvals import events as approval_events
from agent_port.mcp.server import _current_auth
from agent_port.models.integration import InstalledIntegration
from agent_port.models.org import Org
from agent_port.models.tool_approval_request import ToolApprovalRequest
from agent_port.models.tool_execution import ToolExecutionSetting
from agent_port.models.user import User  # noqa: F401

# ── execute_upstream_tool: additional_info is stripped and recorded ──


@dataclass
class _FakeAuth:
    org: Org
    user: User | None = None
    api_key: object | None = None
    impersonator: User | None = None


@pytest.fixture(name="mcp_env")
def mcp_env_fixture(monkeypatch):
    """Set up an in-memory DB, an installed integration in allow mode, and inject
    the fake auth context expected by the MCP handlers."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    org_id = uuid.uuid4()
    with Session(engine) as session:
        session.add(Org(id=org_id, name="test"))
        session.add(
            InstalledIntegration(
                org_id=org_id,
                integration_id="posthog",
                type="remote_mcp",
                url="https://mcp.posthog.com/mcp",
                auth_method="token",
            )
        )
        session.add(
            ToolExecutionSetting(
                org_id=org_id,
                integration_id="posthog",
                tool_name="create_annotation",
                mode="allow",
            )
        )
        session.commit()

    # Detached org object whose id is cached so attribute access after the
    # fixture's session closes does not trigger a refresh.
    detached_org = Org(id=org_id, name="test")

    monkeypatch.setattr("agent_port.mcp.server.engine", engine)
    token = _current_auth.set(_FakeAuth(org=detached_org))
    try:
        yield engine, detached_org
    finally:
        _current_auth.reset(token)


@pytest.mark.anyio
async def test_execute_upstream_tool_strips_additional_info(mcp_env):
    """additional_info must never leak into the arguments we forward upstream."""
    from agent_port.mcp.server import execute_upstream_tool

    engine, org = mcp_env
    captured: dict = {}

    async def fake_call_tool(installed, tool_name, args, oauth_state):
        captured["args"] = args
        return {"content": [{"type": "text", "text": "ok"}]}

    with patch("agent_port.mcp.server.mcp_client.call_tool", side_effect=fake_call_tool):
        await execute_upstream_tool(
            "posthog",
            "create_annotation",
            {"content": "hello", "additional_info": "why I'm calling"},
        )

    assert captured["args"] == {"content": "hello"}
    assert "additional_info" not in captured["args"]

    # And the rationale landed on the log + approval request
    with Session(engine) as session:
        from agent_port.models.log import LogEntry

        logs = session.exec(select(LogEntry).where(LogEntry.org_id == org.id)).all()
        assert len(logs) == 1
        assert logs[0].additional_info == "why I'm calling"

        requests = session.exec(
            select(ToolApprovalRequest).where(ToolApprovalRequest.org_id == org.id)
        ).all()
        assert len(requests) == 1
        assert requests[0].additional_info == "why I'm calling"


@pytest.mark.anyio
async def test_execute_upstream_tool_without_additional_info(mcp_env):
    """Calls that omit additional_info must still succeed and produce a clean log."""
    from agent_port.mcp.server import execute_upstream_tool

    engine, org = mcp_env

    fake = AsyncMock(return_value={"content": [{"type": "text", "text": "ok"}]})
    with patch("agent_port.mcp.server.mcp_client.call_tool", side_effect=fake):
        await execute_upstream_tool("posthog", "create_annotation", {"content": "hello"})

    with Session(engine) as session:
        from agent_port.models.log import LogEntry

        logs = session.exec(select(LogEntry).where(LogEntry.org_id == org.id)).all()
        assert len(logs) == 1
        assert logs[0].additional_info is None


@pytest.mark.anyio
async def test_execute_upstream_tool_ignores_non_string_additional_info(mcp_env):
    """A non-string value is dropped (stripped from args, not stored)."""
    from agent_port.mcp.server import execute_upstream_tool

    engine, org = mcp_env
    captured: dict = {}

    async def fake_call_tool(installed, tool_name, args, oauth_state):
        captured["args"] = args
        return {"content": [{"type": "text", "text": "ok"}]}

    with patch("agent_port.mcp.server.mcp_client.call_tool", side_effect=fake_call_tool):
        await execute_upstream_tool(
            "posthog",
            "create_annotation",
            {"content": "hello", "additional_info": 123},
        )

    assert "additional_info" not in captured["args"]
    with Session(engine) as session:
        from agent_port.models.log import LogEntry

        logs = session.exec(select(LogEntry).where(LogEntry.org_id == org.id)).all()
        assert logs[0].additional_info is None


# ── await_approval: long-poll for the human's decision ──


@pytest.fixture(name="approval_env")
def approval_env_fixture(monkeypatch):
    """In-memory DB with an installed integration whose tool is in
    require_approval mode (the default, no ToolExecutionSetting row)."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    org_id = uuid.uuid4()
    with Session(engine) as session:
        session.add(Org(id=org_id, name="test"))
        session.add(
            InstalledIntegration(
                org_id=org_id,
                integration_id="posthog",
                type="remote_mcp",
                url="https://mcp.posthog.com/mcp",
                auth_method="token",
            )
        )
        session.commit()

    detached_org = Org(id=org_id, name="test")

    monkeypatch.setattr("agent_port.mcp.server.engine", engine)
    token = _current_auth.set(_FakeAuth(org=detached_org))

    # Isolate events module state so tests don't bleed into one another.
    approval_events._events.clear()
    approval_events._statuses.clear()
    approval_events._refcounts.clear()

    try:
        yield engine, detached_org
    finally:
        _current_auth.reset(token)
        approval_events._events.clear()
        approval_events._statuses.clear()
        approval_events._refcounts.clear()


@pytest.mark.anyio
async def test_execute_upstream_tool_returns_request_id_on_approval_required(approval_env):
    """The approval-required response must include the request_id so the agent
    can hand it to agentport__await_approval without waiting in chat."""
    from agent_port.mcp.server import execute_upstream_tool

    engine, _org = approval_env

    result = await execute_upstream_tool("posthog", "create_annotation", {"content": "hello"})

    assert len(result) == 1
    text = result[0].text
    with Session(engine) as session:
        req = session.exec(select(ToolApprovalRequest)).first()
        assert req is not None
        assert str(req.id) in text
    assert "agentport__await_approval" in text
    assert "do not wait" in text.lower() or "without waiting" in text.lower()


@pytest.mark.anyio
async def test_await_approval_wakes_on_approve_and_executes(approval_env):
    """Full flow: execute_upstream_tool returns approval-required, a concurrent
    approval fires notify_decision, and await_approval returns the upstream result."""
    from agent_port.mcp.server import await_approval, execute_upstream_tool

    engine, _org = approval_env

    # Step 1: surface the approval request.
    first = await execute_upstream_tool("posthog", "create_annotation", {"content": "hi"})
    assert "agentport__await_approval" in first[0].text

    with Session(engine) as session:
        req = session.exec(select(ToolApprovalRequest)).first()
        request_id = req.id

    # Step 2: waiter + approver race. The approver flips the DB to approved
    # then fires notify_decision (mirroring what the /approve-once endpoint does).
    async def approver():
        # Let the waiter park first so we exercise the notify path rather than pre_check.
        await asyncio.sleep(0.05)
        with Session(engine) as session:
            req_live = session.get(ToolApprovalRequest, request_id)
            req_live.status = "approved"
            req_live.decision_mode = "approve_once"
            req_live.decided_at = datetime.utcnow()
            session.add(req_live)
            session.commit()
        approval_events.notify_decision(request_id, "approved")

    async def fake_upstream(installed, tool_name, args, oauth_state):
        return {"content": [{"type": "text", "text": "executed-ok"}]}

    with patch("agent_port.mcp.server.mcp_client.call_tool", side_effect=fake_upstream):
        approver_task = asyncio.create_task(approver())
        result = await await_approval(request_id)
        await approver_task

    assert result[0].text == "executed-ok"

    # The request was consumed (transitioned from approved → consumed).
    with Session(engine) as session:
        req = session.get(ToolApprovalRequest, request_id)
        assert req.status == "consumed"


@pytest.mark.anyio
async def test_await_approval_returns_denied_message(approval_env):
    from agent_port.mcp.server import await_approval, execute_upstream_tool

    engine, _org = approval_env

    await execute_upstream_tool("posthog", "create_annotation", {"content": "hi"})
    with Session(engine) as session:
        request_id = session.exec(select(ToolApprovalRequest)).first().id

    async def denier():
        await asyncio.sleep(0.05)
        with Session(engine) as session:
            req = session.get(ToolApprovalRequest, request_id)
            req.status = "denied"
            req.decision_mode = "deny"
            req.decided_at = datetime.utcnow()
            session.add(req)
            session.commit()
        approval_events.notify_decision(request_id, "denied")

    denier_task = asyncio.create_task(denier())
    result = await await_approval(request_id)
    await denier_task

    assert "denied by the human" in result[0].text.lower()


@pytest.mark.anyio
async def test_await_approval_times_out_with_still_pending_message(approval_env, monkeypatch):
    """When no decision arrives inside the timeout window, return the
    'still pending — call again' text so the agent can loop back in."""
    from agent_port.config import settings
    from agent_port.mcp.server import await_approval, execute_upstream_tool

    # Trim the timeout so the test doesn't have to wait 240s.
    monkeypatch.setattr(settings, "approval_long_poll_timeout_seconds", 0.1)

    engine, _org = approval_env
    await execute_upstream_tool("posthog", "create_annotation", {"content": "hi"})
    with Session(engine) as session:
        request_id = session.exec(select(ToolApprovalRequest)).first().id

    result = await await_approval(request_id)
    text = result[0].text.lower()
    assert "still pending" in text
    assert "agentport__await_approval" in result[0].text
    assert str(request_id) in result[0].text


@pytest.mark.anyio
async def test_await_approval_short_circuits_when_already_approved(approval_env):
    """If the decision committed before await_approval was ever called
    (e.g. after a server restart), the pre_check in events must resolve
    the wait immediately instead of hanging."""
    from agent_port.mcp.server import await_approval, execute_upstream_tool

    engine, _org = approval_env
    await execute_upstream_tool("posthog", "create_annotation", {"content": "hi"})
    with Session(engine) as session:
        req = session.exec(select(ToolApprovalRequest)).first()
        request_id = req.id
        # Flip to approved *without* firing notify — mimicking a server restart
        # where the event dict is empty but the DB already has the decision.
        req.status = "approved"
        req.decision_mode = "approve_once"
        req.decided_at = datetime.utcnow()
        session.add(req)
        session.commit()

    async def fake_upstream(installed, tool_name, args, oauth_state):
        return {"content": [{"type": "text", "text": "recovered-ok"}]}

    with patch("agent_port.mcp.server.mcp_client.call_tool", side_effect=fake_upstream):
        result = await asyncio.wait_for(await_approval(request_id), timeout=2.0)

    assert result[0].text == "recovered-ok"


@pytest.mark.anyio
async def test_await_approval_unknown_request_returns_not_found(approval_env):
    from agent_port.mcp.server import await_approval

    result = await await_approval(uuid.uuid4())
    assert "not found" in result[0].text.lower()


@pytest.mark.anyio
async def test_await_approval_wrong_org_returns_not_found(approval_env, monkeypatch):
    """Ownership enforcement: a request belonging to another org must 404."""
    from agent_port.mcp.server import await_approval

    engine, _org = approval_env
    other_org_id = uuid.uuid4()
    foreign_request_id = uuid.uuid4()
    with Session(engine) as session:
        session.add(Org(id=other_org_id, name="other"))
        session.add(
            ToolApprovalRequest(
                id=foreign_request_id,
                org_id=other_org_id,
                integration_id="posthog",
                tool_name="create_annotation",
                args_json="{}",
                args_hash="abc",
                summary_text="x",
                status="pending",
                expires_at=datetime.utcnow(),
            )
        )
        session.commit()

    result = await await_approval(foreign_request_id)
    assert "not found" in result[0].text.lower()
