import json
import uuid

from sqlmodel import Session, select

from agent_port.approvals.normalize import hash_normalized_args, normalize_tool_args
from agent_port.approvals.rules import evaluate_rules
from agent_port.models.tool_execution import ToolExecutionSetting
from agent_port.models.tool_execution_rule import (
    ToolExecutionRule,
    ToolExecutionRuleCondition,
)

_EFFECT_TO_DECISION = {
    "allow": (True, "tool_allowed"),
    "deny": (False, "denied"),
    "require_approval": (False, "require_approval"),
}


class PolicyDecision:
    def __init__(
        self,
        allowed: bool,
        reason: str,
        args_hash: str | None = None,
        matched_rule_id: uuid.UUID | None = None,
    ):
        self.allowed = allowed
        self.reason = reason
        self.args_hash = args_hash
        self.matched_rule_id = matched_rule_id


def _load_rules(
    session: Session,
    org_id: uuid.UUID,
    integration_id: str,
    tool_name: str,
) -> list[dict]:
    """Load enabled rules + their conditions into plain dicts for the evaluator."""
    rules = session.exec(
        select(ToolExecutionRule)
        .where(ToolExecutionRule.org_id == org_id)
        .where(ToolExecutionRule.integration_id == integration_id)
        .where(ToolExecutionRule.tool_name == tool_name)
        .where(ToolExecutionRule.enabled)
    ).all()
    if not rules:
        return []

    conditions = session.exec(
        select(ToolExecutionRuleCondition).where(
            ToolExecutionRuleCondition.rule_id.in_([r.id for r in rules])  # type: ignore[attr-defined]
        )
    ).all()
    conds_by_rule: dict[uuid.UUID, list[dict]] = {}
    for c in conditions:
        conds_by_rule.setdefault(c.rule_id, []).append(
            {
                "param_path": c.param_path,
                "operator": c.operator,
                "values": json.loads(c.values_json),
            }
        )
    return [
        {
            "id": r.id,
            "priority": r.priority,
            "effect": r.effect,
            "conditions": conds_by_rule.get(r.id, []),
        }
        for r in rules
    ]


def _fallback_decision(
    session: Session,
    org_id: uuid.UUID,
    integration_id: str,
    tool_name: str,
    args_hash: str,
) -> PolicyDecision:
    setting = session.exec(
        select(ToolExecutionSetting)
        .where(ToolExecutionSetting.org_id == org_id)
        .where(ToolExecutionSetting.integration_id == integration_id)
        .where(ToolExecutionSetting.tool_name == tool_name)
    ).first()
    mode = setting.mode if setting else "require_approval"
    allowed, reason = _EFFECT_TO_DECISION.get(mode, (False, "require_approval"))
    return PolicyDecision(allowed=allowed, reason=reason, args_hash=args_hash)


def evaluate_policy(
    session: Session,
    org_id: uuid.UUID,
    integration_id: str,
    tool_name: str,
    args: dict,
) -> PolicyDecision:
    normalized = normalize_tool_args(args)
    args_hash = hash_normalized_args(normalized)

    rules = _load_rules(session, org_id, integration_id, tool_name)
    winner = evaluate_rules(rules, args)
    if winner is not None:
        allowed, reason = _EFFECT_TO_DECISION[winner["effect"]]
        return PolicyDecision(
            allowed=allowed,
            reason=reason,
            args_hash=args_hash,
            matched_rule_id=winner["id"],
        )

    return _fallback_decision(session, org_id, integration_id, tool_name, args_hash)
