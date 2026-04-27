import hashlib
import secrets
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from agent_port.db import get_session
from agent_port.dependencies import (
    AgentAuth,
    get_agent_auth,
    get_current_org,
    get_current_user,
    get_impersonator,
)
from agent_port.main import app
from agent_port.models.api_key import ApiKey  # noqa: F401
from agent_port.models.google_login_state import GoogleLoginState  # noqa: F401
from agent_port.models.integration import InstalledIntegration  # noqa: F401
from agent_port.models.log import LogEntry  # noqa: F401
from agent_port.models.oauth import OAuthState  # noqa: F401
from agent_port.models.oauth_client import OAuthClient  # noqa: F401
from agent_port.models.oauth_revoked_token import OAuthRevokedToken  # noqa: F401
from agent_port.models.org import Org
from agent_port.models.org_membership import OrgMembership
from agent_port.models.secret import Secret  # noqa: F401
from agent_port.models.subscription import Subscription  # noqa: F401
from agent_port.models.tool_approval_request import ToolApprovalRequest  # noqa: F401
from agent_port.models.tool_cache import ToolCache  # noqa: F401
from agent_port.models.tool_execution import ToolExecutionSetting  # noqa: F401
from agent_port.models.user import User


@pytest.fixture(autouse=True)
def stub_token_validation(monkeypatch):
    async def _validate_token(url: str, token: str) -> None:
        return None

    monkeypatch.setattr("agent_port.api.installed.validate_token", _validate_token)


@pytest.fixture(autouse=True)
def _reset_rate_limit_state():
    from agent_port.rate_limit import reset_all_rate_limiters

    reset_all_rate_limiters()
    yield
    reset_all_rate_limiters()


_ENGINE_CONSUMER_MODULES = (
    "agent_port.db",
    "agent_port.api.tool_approvals",
    "agent_port.api_client",
    "agent_port.mcp.asgi",
    "agent_port.mcp.client",
    "agent_port.mcp.management_tools",
    "agent_port.mcp.oauth",
    "agent_port.mcp.oauth_provider",
    "agent_port.mcp.refresh",
    "agent_port.mcp.server",
)


@pytest.fixture(name="session")
def session_fixture(monkeypatch):
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)
    for module in _ENGINE_CONSUMER_MODULES:
        monkeypatch.setattr(f"{module}.engine", test_engine, raising=False)
    with Session(test_engine) as session:
        yield session


@pytest.fixture(name="test_user")
def test_user_fixture(session):
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        hashed_password="hashed",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture(name="test_org")
def test_org_fixture(session, test_user):
    org = Org(id=uuid.uuid4(), name="Test Org")
    session.add(org)
    session.commit()
    session.refresh(org)
    membership = OrgMembership(user_id=test_user.id, org_id=org.id, role="owner")
    session.add(membership)
    session.commit()
    return org


@pytest.fixture(name="client")
async def client_fixture(session, test_user, test_org):
    def override_session():
        yield session

    def override_user():
        return test_user

    def override_org():
        return test_org

    def override_agent_auth():
        return AgentAuth(org=test_org, user=test_user, api_key=None)

    def override_impersonator():
        return None

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_current_org] = override_org
    app.dependency_overrides[get_agent_auth] = override_agent_auth
    app.dependency_overrides[get_impersonator] = override_impersonator
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(name="api_key_record")
def api_key_record_fixture(session, test_user, test_org):
    """Creates a real ApiKey row. Returns (api_key_row, plain_key)."""
    plain_key = "ap_" + secrets.token_urlsafe(24)
    key_hash = hashlib.sha256(plain_key.encode()).hexdigest()
    api_key = ApiKey(
        org_id=test_org.id,
        created_by_user_id=test_user.id,
        name="test-key",
        key_prefix=plain_key[:12],
        key_hash=key_hash,
    )
    session.add(api_key)
    session.commit()
    session.refresh(api_key)
    return api_key, plain_key


@pytest.fixture(name="agent_key_client")
async def agent_key_client_fixture(session, test_user, test_org, api_key_record):
    """AsyncClient that authenticates via X-API-Key header (real dep, no override)."""
    api_key, plain_key = api_key_record

    def override_session():
        yield session

    def override_user():
        return test_user

    def override_org():
        return test_org

    def override_impersonator():
        return None

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_current_org] = override_org
    app.dependency_overrides[get_impersonator] = override_impersonator
    # get_agent_auth is NOT overridden — uses real implementation
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-API-Key": plain_key},
    ) as c:
        yield c
    app.dependency_overrides.clear()
