import uuid

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from agent_port.approvals.policy import evaluate_policy
from agent_port.models.org import Org  # noqa: F401
from agent_port.models.tool_execution import ToolExecutionSetting
from agent_port.models.user import User  # noqa: F401


@pytest.fixture(name="db")
def db_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="org_id")
def org_id_fixture(db):
    org = Org(id=uuid.uuid4(), name="test")
    db.add(org)
    db.commit()
    return org.id


def test_default_requires_approval(db, org_id):
    decision = evaluate_policy(db, org_id, "github", "create_issue", {"title": "hi"})
    assert not decision.allowed
    assert decision.reason == "require_approval"


def test_tool_set_to_allow(db, org_id):
    db.add(
        ToolExecutionSetting(
            org_id=org_id,
            integration_id="github",
            tool_name="create_issue",
            mode="allow",
        )
    )
    db.commit()

    decision = evaluate_policy(db, org_id, "github", "create_issue", {"title": "hi"})
    assert decision.allowed
    assert decision.reason == "tool_allowed"


def test_tool_set_to_deny(db, org_id):
    db.add(
        ToolExecutionSetting(
            org_id=org_id,
            integration_id="github",
            tool_name="create_issue",
            mode="deny",
        )
    )
    db.commit()

    decision = evaluate_policy(db, org_id, "github", "create_issue", {"title": "hi"})
    assert not decision.allowed
    assert decision.reason == "denied"


def test_tool_set_to_require_approval(db, org_id):
    db.add(
        ToolExecutionSetting(
            org_id=org_id,
            integration_id="github",
            tool_name="create_issue",
            mode="require_approval",
        )
    )
    db.commit()

    decision = evaluate_policy(db, org_id, "github", "create_issue", {"title": "hi"})
    assert not decision.allowed
    assert decision.reason == "require_approval"
