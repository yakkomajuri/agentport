import uuid

from sqlmodel import Session, select

from agent_port.approvals.normalize import hash_normalized_args, normalize_tool_args
from agent_port.models.tool_execution import ToolExecutionSetting


class PolicyDecision:
    def __init__(self, allowed: bool, reason: str, args_hash: str | None = None):
        self.allowed = allowed
        self.reason = reason
        self.args_hash = args_hash


def evaluate_policy(
    session: Session,
    org_id: uuid.UUID,
    integration_id: str,
    tool_name: str,
    args: dict,
) -> PolicyDecision:
    normalized = normalize_tool_args(args)
    args_hash = hash_normalized_args(normalized)

    setting = session.exec(
        select(ToolExecutionSetting)
        .where(ToolExecutionSetting.org_id == org_id)
        .where(ToolExecutionSetting.integration_id == integration_id)
        .where(ToolExecutionSetting.tool_name == tool_name)
    ).first()
    if setting:
        if setting.mode == "allow":
            return PolicyDecision(allowed=True, reason="tool_allowed", args_hash=args_hash)
        if setting.mode == "deny":
            return PolicyDecision(allowed=False, reason="denied", args_hash=args_hash)
        return PolicyDecision(allowed=False, reason="require_approval", args_hash=args_hash)

    return PolicyDecision(allowed=False, reason="require_approval", args_hash=args_hash)
