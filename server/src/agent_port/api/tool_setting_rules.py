"""CRUD + test endpoints for conditional tool-execution rules.

Rules are a sub-resource of tool-settings: they refine the fallback
ToolExecutionSetting.mode with parameter-aware conditions. The matching
semantics live in agent_port.approvals.rules; this module only persists rows
and enforces write-time validation and the allow-escalation TOTP gate.
"""

import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from agent_port.api.second_factor import require_second_factor
from agent_port.approvals.policy import evaluate_policy
from agent_port.approvals.rules import (
    RuleValidationError,
    validate_rule_fields,
)
from agent_port.db import get_session
from agent_port.dependencies import get_current_org, get_current_user
from agent_port.models.org import Org
from agent_port.models.tool_execution_rule import (
    ToolExecutionRule,
    ToolExecutionRuleCondition,
)
from agent_port.models.user import User

router = APIRouter(prefix="/api/tool-settings", tags=["tool-settings"])

_REASON_TO_EFFECT = {
    "tool_allowed": "allow",
    "denied": "deny",
    "require_approval": "require_approval",
}


class ConditionPayload(BaseModel):
    param_path: str
    operator: str
    values: list[str]
    position: int = 0


class CreateRuleRequest(BaseModel):
    name: str
    effect: str
    priority: int = 100
    enabled: bool = True
    conditions: list[ConditionPayload] = []
    totp_code: str | None = None


class UpdateRuleRequest(BaseModel):
    name: str | None = None
    effect: str | None = None
    priority: int | None = None
    enabled: bool | None = None
    conditions: list[ConditionPayload] | None = None
    totp_code: str | None = None


class TestRulesRequest(BaseModel):
    args: dict = {}


def _serialize_rule(session: Session, rule: ToolExecutionRule) -> dict:
    conditions = session.exec(
        select(ToolExecutionRuleCondition)
        .where(ToolExecutionRuleCondition.rule_id == rule.id)
        .order_by(ToolExecutionRuleCondition.position)
    ).all()
    return {
        "id": str(rule.id),
        "integration_id": rule.integration_id,
        "tool_name": rule.tool_name,
        "name": rule.name,
        "priority": rule.priority,
        "effect": rule.effect,
        "enabled": rule.enabled,
        "created_at": rule.created_at.isoformat(),
        "updated_at": rule.updated_at.isoformat(),
        "conditions": [
            {
                "id": str(c.id),
                "param_path": c.param_path,
                "operator": c.operator,
                "values": json.loads(c.values_json),
                "position": c.position,
            }
            for c in conditions
        ],
    }


def _get_rule_or_404(
    session: Session,
    org_id: uuid.UUID,
    integration_id: str,
    tool_name: str,
    rule_id: uuid.UUID,
) -> ToolExecutionRule:
    rule = session.exec(
        select(ToolExecutionRule)
        .where(ToolExecutionRule.id == rule_id)
        .where(ToolExecutionRule.org_id == org_id)
        .where(ToolExecutionRule.integration_id == integration_id)
        .where(ToolExecutionRule.tool_name == tool_name)
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


def _replace_conditions(
    session: Session, rule_id: uuid.UUID, conditions: list[ConditionPayload]
) -> None:
    existing = session.exec(
        select(ToolExecutionRuleCondition).where(ToolExecutionRuleCondition.rule_id == rule_id)
    ).all()
    for c in existing:
        session.delete(c)
    for i, cond in enumerate(conditions):
        session.add(
            ToolExecutionRuleCondition(
                rule_id=rule_id,
                param_path=cond.param_path,
                operator=cond.operator,
                values_json=json.dumps(cond.values),
                position=cond.position if cond.position else i,
            )
        )


@router.get("/{integration_id}/{tool_name}/rules")
def list_rules(
    integration_id: str,
    tool_name: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    current_org: Org = Depends(get_current_org),
) -> list[dict]:
    rules = session.exec(
        select(ToolExecutionRule)
        .where(ToolExecutionRule.org_id == current_org.id)
        .where(ToolExecutionRule.integration_id == integration_id)
        .where(ToolExecutionRule.tool_name == tool_name)
        .order_by(ToolExecutionRule.priority, ToolExecutionRule.created_at)
    ).all()
    return [_serialize_rule(session, r) for r in rules]


@router.post("/{integration_id}/{tool_name}/rules")
def create_rule(
    integration_id: str,
    tool_name: str,
    body: CreateRuleRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    current_org: Org = Depends(get_current_org),
) -> dict:
    existing_count = len(
        session.exec(
            select(ToolExecutionRule)
            .where(ToolExecutionRule.org_id == current_org.id)
            .where(ToolExecutionRule.integration_id == integration_id)
            .where(ToolExecutionRule.tool_name == tool_name)
        ).all()
    )
    conditions = [c.model_dump() for c in body.conditions]
    try:
        validate_rule_fields(
            effect=body.effect,
            conditions=conditions,
            existing_rule_count=existing_count + 1,
        )
    except RuleValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Creating an enabled allow rule re-opens auto-execution and must clear the
    # same second-factor challenge as escalating the fallback mode to allow.
    if body.effect == "allow" and body.enabled:
        require_second_factor(current_user, body.totp_code)
        session.add(current_user)

    now = datetime.utcnow()
    rule = ToolExecutionRule(
        org_id=current_org.id,
        integration_id=integration_id,
        tool_name=tool_name,
        name=body.name,
        priority=body.priority,
        effect=body.effect,
        enabled=body.enabled,
        created_by_user_id=current_user.id,
        created_at=now,
        updated_at=now,
    )
    session.add(rule)
    session.commit()
    session.refresh(rule)
    _replace_conditions(session, rule.id, body.conditions)
    session.commit()
    return _serialize_rule(session, rule)


@router.patch("/{integration_id}/{tool_name}/rules/{rule_id}")
def update_rule(
    integration_id: str,
    tool_name: str,
    rule_id: uuid.UUID,
    body: UpdateRuleRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    current_org: Org = Depends(get_current_org),
) -> dict:
    rule = _get_rule_or_404(session, current_org.id, integration_id, tool_name, rule_id)

    effect_after = body.effect if body.effect is not None else rule.effect
    enabled_after = body.enabled if body.enabled is not None else rule.enabled
    conditions_after = (
        [c.model_dump() for c in body.conditions]
        if body.conditions is not None
        else [
            {
                "param_path": c.param_path,
                "operator": c.operator,
                "values": json.loads(c.values_json),
            }
            for c in session.exec(
                select(ToolExecutionRuleCondition).where(
                    ToolExecutionRuleCondition.rule_id == rule.id
                )
            ).all()
        ]
    )

    try:
        validate_rule_fields(
            effect=effect_after,
            conditions=conditions_after,
            existing_rule_count=1,  # not changing the count on update
        )
    except RuleValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Require a second factor whenever this write transitions the rule *into* an
    # active allow state (newly allow, newly enabled, or an allow rule's
    # conditions being broadened). A rule that is already an active allow rule
    # and stays one without changes does not re-challenge.
    was_active_allow = rule.effect == "allow" and rule.enabled
    now_active_allow = effect_after == "allow" and enabled_after
    if now_active_allow and not was_active_allow:
        require_second_factor(current_user, body.totp_code)
        session.add(current_user)

    if body.name is not None:
        rule.name = body.name
    if body.effect is not None:
        rule.effect = body.effect
    if body.priority is not None:
        rule.priority = body.priority
    if body.enabled is not None:
        rule.enabled = body.enabled
    rule.updated_at = datetime.utcnow()
    session.add(rule)

    if body.conditions is not None:
        _replace_conditions(session, rule.id, body.conditions)

    session.commit()
    session.refresh(rule)
    return _serialize_rule(session, rule)


@router.delete("/{integration_id}/{tool_name}/rules/{rule_id}", status_code=204)
def delete_rule(
    integration_id: str,
    tool_name: str,
    rule_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    current_org: Org = Depends(get_current_org),
) -> None:
    rule = _get_rule_or_404(session, current_org.id, integration_id, tool_name, rule_id)
    conditions = session.exec(
        select(ToolExecutionRuleCondition).where(ToolExecutionRuleCondition.rule_id == rule.id)
    ).all()
    for c in conditions:
        session.delete(c)
    session.delete(rule)
    session.commit()


@router.post("/{integration_id}/{tool_name}/rules/test")
def test_rules(
    integration_id: str,
    tool_name: str,
    body: TestRulesRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    current_org: Org = Depends(get_current_org),
) -> dict:
    decision = evaluate_policy(session, current_org.id, integration_id, tool_name, body.args)
    effect = _REASON_TO_EFFECT.get(decision.reason, "require_approval")
    return {
        "effect": effect,
        "allowed": decision.allowed,
        "matched_rule_id": str(decision.matched_rule_id) if decision.matched_rule_id else None,
        "source": "rule" if decision.matched_rule_id else "fallback",
    }
