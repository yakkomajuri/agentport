"""Unit tests for MCP management tool handlers — focused on policy surfacing."""

import json
import uuid
from datetime import datetime

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from agent_port.billing.limits import FREE_INTEGRATION_LIMIT
from agent_port.config import settings
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


@pytest.fixture(name="install_env")
def install_env_fixture(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    org_id = uuid.uuid4()
    with Session(engine) as session:
        session.add(Org(id=org_id, name="test"))
        session.commit()

    async def noop_refresh(*_args, **_kwargs):
        return None

    monkeypatch.setattr("agent_port.mcp.management_tools.engine", engine)
    monkeypatch.setattr("agent_port.mcp.management_tools.refresh_one", noop_refresh)
    return engine, org_id


def _seed_installed(session: Session, org_id, integration_id: str, connected: bool = True) -> None:
    session.add(
        InstalledIntegration(
            org_id=org_id,
            integration_id=integration_id,
            type="custom",
            url="https://api.example.test",
            auth_method="token",
            connected=connected,
        )
    )


def _installed_rows(session: Session, org_id) -> list[InstalledIntegration]:
    return session.exec(
        select(InstalledIntegration).where(InstalledIntegration.org_id == org_id)
    ).all()


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


@pytest.mark.anyio
async def test_mcp_install_enforces_free_tier_limit(install_env, monkeypatch):
    engine, org_id = install_env
    monkeypatch.setattr(settings, "is_cloud", True)
    with Session(engine) as session:
        for i in range(FREE_INTEGRATION_LIMIT):
            _seed_installed(session, org_id, f"existing_{i}")
        session.commit()

    result = await management_tools._handle_install(
        {"integration_id": "resend", "auth_method": "token", "token": "re_test"},
        org_id,
    )
    payload = json.loads(result[0].text)

    assert payload["installed"] is False
    assert payload["error"] == "free_tier_limit"
    assert payload["limit"] == FREE_INTEGRATION_LIMIT
    with Session(engine) as session:
        rows = _installed_rows(session, org_id)
        assert len(rows) == FREE_INTEGRATION_LIMIT
        assert all(r.integration_id != "resend" for r in rows)


@pytest.mark.anyio
async def test_mcp_install_limit_ignores_self_hosted(install_env, monkeypatch):
    engine, org_id = install_env
    monkeypatch.setattr(settings, "is_cloud", False)
    with Session(engine) as session:
        for i in range(FREE_INTEGRATION_LIMIT):
            _seed_installed(session, org_id, f"existing_{i}")
        session.commit()

    result = await management_tools._handle_install(
        {"integration_id": "resend", "auth_method": "token", "token": "re_test"},
        org_id,
    )
    payload = json.loads(result[0].text)

    assert payload["installed"] is True
    assert payload["integration_id"] == "resend"
    with Session(engine) as session:
        rows = _installed_rows(session, org_id)
        assert len(rows) == FREE_INTEGRATION_LIMIT + 1


@pytest.mark.anyio
async def test_mcp_install_replacing_stale_unconnected_row_checks_after_delete(
    install_env, monkeypatch
):
    engine, org_id = install_env
    monkeypatch.setattr(settings, "is_cloud", True)
    with Session(engine) as session:
        for i in range(FREE_INTEGRATION_LIMIT - 1):
            _seed_installed(session, org_id, f"existing_{i}")
        _seed_installed(session, org_id, "resend", connected=False)
        session.commit()

    result = await management_tools._handle_install(
        {"integration_id": "resend", "auth_method": "token", "token": "re_test"},
        org_id,
    )
    payload = json.loads(result[0].text)

    assert payload["installed"] is True
    assert payload["integration_id"] == "resend"
    with Session(engine) as session:
        rows = _installed_rows(session, org_id)
        resend_rows = [r for r in rows if r.integration_id == "resend"]
        assert len(rows) == FREE_INTEGRATION_LIMIT
        assert len(resend_rows) == 1
        assert resend_rows[0].connected is True
