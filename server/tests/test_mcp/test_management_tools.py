"""Unit tests for MCP management tool handlers — focused on policy surfacing."""

import json
import uuid
from datetime import datetime

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from agent_port.mcp import management_tools
from agent_port.models.integration import InstalledIntegration
from agent_port.models.org import Org
from agent_port.models.tool_cache import ToolCache
from agent_port.models.tool_execution import ToolExecutionSetting
from agent_port.models.user import User  # noqa: F401


@pytest.fixture(name="policy_env")
def policy_env_fixture(monkeypatch):
    """In-memory DB with one installed integration and a cached tool list.

    Fixture caller adds ToolExecutionSetting rows to vary policy state.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    org_id = uuid.uuid4()
    tools_payload = [
        {"name": "send_email", "description": "Send an email", "inputSchema": {}},
        {"name": "read_inbox", "description": "Read inbox messages", "inputSchema": {}},
    ]

    with Session(engine) as session:
        session.add(Org(id=org_id, name="test"))
        session.add(
            InstalledIntegration(
                org_id=org_id,
                integration_id="gmail",
                type="remote_mcp",
                url="https://mcp.gmail/mcp",
                auth_method="token",
                connected=True,
            )
        )
        session.add(
            ToolCache(
                org_id=org_id,
                integration_id="gmail",
                tools_json=json.dumps(tools_payload),
                fetched_at=datetime.utcnow(),
            )
        )
        session.commit()

    monkeypatch.setattr("agent_port.mcp.management_tools.engine", engine)
    return engine, org_id


@pytest.mark.anyio
async def test_describe_tool_returns_default_approval_when_unconfigured(policy_env):
    engine, org_id = policy_env

    result = await management_tools._handle_describe_tool(
        {"integration_id": "gmail", "tool_name": "send_email"}, org_id
    )
    payload = json.loads(result[0].text)

    assert payload["integration_id"] == "gmail"
    assert payload["tool"]["name"] == "send_email"
    assert payload["approval"]["mode"] == "require_approval"
    assert payload["approval"]["source"] == "default"
    assert "policy can change" in payload["approval"]["note"].lower()


@pytest.mark.anyio
async def test_describe_tool_returns_configured_approval(policy_env):
    engine, org_id = policy_env
    with Session(engine) as session:
        session.add(
            ToolExecutionSetting(
                org_id=org_id,
                integration_id="gmail",
                tool_name="send_email",
                mode="allow",
            )
        )
        session.commit()

    result = await management_tools._handle_describe_tool(
        {"integration_id": "gmail", "tool_name": "send_email"}, org_id
    )
    payload = json.loads(result[0].text)

    assert payload["approval"]["mode"] == "allow"
    assert payload["approval"]["source"] == "configured"


@pytest.mark.anyio
async def test_list_integration_tools_single_attaches_approval_mode(policy_env):
    engine, org_id = policy_env
    with Session(engine) as session:
        session.add(
            ToolExecutionSetting(
                org_id=org_id,
                integration_id="gmail",
                tool_name="send_email",
                mode="allow",
            )
        )
        session.commit()

    result = await management_tools._handle_list_integration_tools(
        {"integration_id": "gmail"}, org_id
    )
    payload = json.loads(result[0].text)

    modes = {t["name"]: t["approval_mode"] for t in payload["tools"]}
    assert modes == {"send_email": "allow", "read_inbox": "require_approval"}


@pytest.mark.anyio
async def test_list_integration_tools_cross_attaches_approval_mode(policy_env):
    engine, org_id = policy_env
    with Session(engine) as session:
        session.add(
            ToolExecutionSetting(
                org_id=org_id,
                integration_id="gmail",
                tool_name="read_inbox",
                mode="deny",
            )
        )
        session.commit()

    result = await management_tools._handle_list_integration_tools({}, org_id)
    payload = json.loads(result[0].text)

    modes = {t["name"]: t["approval_mode"] for t in payload["tools"]}
    assert modes == {"send_email": "require_approval", "read_inbox": "deny"}
