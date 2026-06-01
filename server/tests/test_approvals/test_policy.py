import json
import uuid

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from agent_port.approvals.policy import evaluate_policy
from agent_port.models.org import Org  # noqa: F401
from agent_port.models.tool_execution import ToolExecutionSetting
from agent_port.models.tool_execution_rule import (
    ToolExecutionRule,
    ToolExecutionRuleCondition,
)
from agent_port.models.user import User  # noqa: F401


def _add_rule(db, org_id, *, effect, priority=100, conditions=None, enabled=True, name="r"):
    rule = ToolExecutionRule(
        org_id=org_id,
        integration_id="resend",
        tool_name="send_email",
        name=name,
        priority=priority,
        effect=effect,
        enabled=enabled,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    for i, (param, op, values) in enumerate(conditions or []):
        db.add(
            ToolExecutionRuleCondition(
                rule_id=rule.id,
                param_path=param,
                operator=op,
                values_json=json.dumps(values),
                position=i,
            )
        )
    db.commit()
    return rule


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


# ── rule-based evaluation ──


def test_allow_rule_matches(db, org_id):
    rule = _add_rule(
        db,
        org_id,
        effect="allow",
        conditions=[("to", "ends_with", ["@useskald.com"])],
    )
    decision = evaluate_policy(db, org_id, "resend", "send_email", {"to": "a@useskald.com"})
    assert decision.allowed
    assert decision.reason == "tool_allowed"
    assert decision.matched_rule_id == rule.id


def test_deny_rule_matches(db, org_id):
    _add_rule(
        db,
        org_id,
        effect="deny",
        conditions=[("subject", "contains", ["password"])],
    )
    decision = evaluate_policy(
        db, org_id, "resend", "send_email", {"subject": "your password reset"}
    )
    assert not decision.allowed
    assert decision.reason == "denied"


def test_rule_falls_through_to_fallback_when_no_match(db, org_id):
    _add_rule(db, org_id, effect="allow", conditions=[("to", "ends_with", ["@useskald.com"])])
    db.add(
        ToolExecutionSetting(
            org_id=org_id, integration_id="resend", tool_name="send_email", mode="deny"
        )
    )
    db.commit()
    decision = evaluate_policy(db, org_id, "resend", "send_email", {"to": "x@gmail.com"})
    assert not decision.allowed
    assert decision.reason == "denied"
    assert decision.matched_rule_id is None


def test_same_priority_precedence_deny_wins(db, org_id):
    _add_rule(
        db,
        org_id,
        name="allow",
        effect="allow",
        priority=100,
        conditions=[("to", "contains", ["@"])],
    )
    deny = _add_rule(
        db,
        org_id,
        name="deny",
        effect="deny",
        priority=100,
        conditions=[("to", "contains", ["@"])],
    )
    decision = evaluate_policy(db, org_id, "resend", "send_email", {"to": "a@b.com"})
    assert not decision.allowed
    assert decision.reason == "denied"
    assert decision.matched_rule_id == deny.id


def test_lower_priority_number_wins(db, org_id):
    deny = _add_rule(
        db,
        org_id,
        name="deny",
        effect="deny",
        priority=10,
        conditions=[("to", "contains", ["@"])],
    )
    _add_rule(
        db,
        org_id,
        name="allow",
        effect="allow",
        priority=100,
        conditions=[("to", "contains", ["@"])],
    )
    decision = evaluate_policy(db, org_id, "resend", "send_email", {"to": "a@b.com"})
    assert decision.reason == "denied"
    assert decision.matched_rule_id == deny.id


def test_disabled_rule_is_ignored(db, org_id):
    _add_rule(
        db,
        org_id,
        effect="allow",
        enabled=False,
        conditions=[("to", "ends_with", ["@useskald.com"])],
    )
    decision = evaluate_policy(db, org_id, "resend", "send_email", {"to": "a@useskald.com"})
    assert not decision.allowed
    assert decision.reason == "require_approval"
    assert decision.matched_rule_id is None


def test_multiple_conditions_are_and(db, org_id):
    _add_rule(
        db,
        org_id,
        effect="allow",
        conditions=[
            ("to", "ends_with", ["@useskald.com"]),
            ("subject", "contains", ["invoice"]),
        ],
    )
    assert evaluate_policy(
        db, org_id, "resend", "send_email", {"to": "a@useskald.com", "subject": "invoice"}
    ).allowed
    assert not evaluate_policy(
        db, org_id, "resend", "send_email", {"to": "a@useskald.com", "subject": "hi"}
    ).allowed


def test_array_param_values_are_or(db, org_id):
    _add_rule(db, org_id, effect="deny", conditions=[("to", "ends_with", ["@blocked.com"])])
    decision = evaluate_policy(
        db, org_id, "resend", "send_email", {"to": ["ok@useskald.com", "bad@blocked.com"]}
    )
    assert decision.reason == "denied"


def test_missing_param_does_not_match(db, org_id):
    _add_rule(db, org_id, effect="allow", conditions=[("to", "ends_with", ["@useskald.com"])])
    decision = evaluate_policy(db, org_id, "resend", "send_email", {"subject": "no to field"})
    assert not decision.allowed
    assert decision.reason == "require_approval"
    assert decision.matched_rule_id is None
