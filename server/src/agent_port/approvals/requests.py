import uuid
from datetime import datetime, timedelta

from sqlmodel import Session, select

from agent_port.approvals.normalize import hash_normalized_args, normalize_tool_args
from agent_port.approvals.summarize import summarize_tool_call
from agent_port.config import settings
from agent_port.models.tool_approval_request import ToolApprovalRequest


def get_or_create_approval_request(
    session: Session,
    org_id: uuid.UUID,
    integration_id: str,
    tool_name: str,
    args: dict,
    requested_by_agent: str | None = None,
    requester_ip: str | None = None,
    user_agent: str | None = None,
    api_key_label: str | None = None,
    api_key_prefix: str | None = None,
    additional_info: str | None = None,
) -> ToolApprovalRequest:
    normalized = normalize_tool_args(args)
    args_hash = hash_normalized_args(normalized)
    now = datetime.utcnow()

    # Reuse existing pending non-expired request with same signature.
    # If the caller supplied fresh additional_info on a retry, attach it so the
    # human approver sees the latest explanation even when the underlying request
    # is reused.
    existing = session.exec(
        select(ToolApprovalRequest)
        .where(ToolApprovalRequest.org_id == org_id)
        .where(ToolApprovalRequest.integration_id == integration_id)
        .where(ToolApprovalRequest.tool_name == tool_name)
        .where(ToolApprovalRequest.args_hash == args_hash)
        .where(ToolApprovalRequest.status == "pending")
        .where(ToolApprovalRequest.expires_at > now)
    ).first()
    if existing:
        if additional_info and not existing.additional_info:
            existing.additional_info = additional_info
            session.add(existing)
            session.commit()
            session.refresh(existing)
        return existing

    summary = summarize_tool_call(integration_id, tool_name, args)
    request = ToolApprovalRequest(
        org_id=org_id,
        integration_id=integration_id,
        tool_name=tool_name,
        args_json=normalized,
        args_hash=args_hash,
        summary_text=summary,
        status="pending",
        requested_by_agent=requested_by_agent,
        requested_at=now,
        expires_at=now + timedelta(minutes=settings.approval_expiry_minutes),
        requester_ip=requester_ip,
        user_agent=user_agent,
        api_key_label=api_key_label,
        api_key_prefix=api_key_prefix,
        additional_info=additional_info,
    )
    session.add(request)
    session.commit()
    session.refresh(request)
    return request


def create_auto_approved_request(
    session: Session,
    org_id: uuid.UUID,
    integration_id: str,
    tool_name: str,
    args: dict,
    requested_by_agent: str | None = None,
    requester_ip: str | None = None,
    user_agent: str | None = None,
    api_key_label: str | None = None,
    api_key_prefix: str | None = None,
    additional_info: str | None = None,
) -> ToolApprovalRequest:
    """Create an already-decided request record for a policy-matched (auto-approved) call."""
    normalized = normalize_tool_args(args)
    args_hash = hash_normalized_args(normalized)
    summary = summarize_tool_call(integration_id, tool_name, args)
    now = datetime.utcnow()
    request = ToolApprovalRequest(
        org_id=org_id,
        integration_id=integration_id,
        tool_name=tool_name,
        args_json=normalized,
        args_hash=args_hash,
        summary_text=summary,
        status="auto_approved",
        decision_mode="allow_tool_forever",
        decided_at=now,
        requested_by_agent=requested_by_agent,
        requested_at=now,
        expires_at=now,
        requester_ip=requester_ip,
        user_agent=user_agent,
        api_key_label=api_key_label,
        api_key_prefix=api_key_prefix,
        additional_info=additional_info,
    )
    session.add(request)
    session.commit()
    session.refresh(request)
    return request


def try_consume_approved_request(
    session: Session,
    org_id: uuid.UUID,
    integration_id: str,
    tool_name: str,
    args_hash: str,
) -> ToolApprovalRequest | None:
    """Try to consume an approve-once request. Returns the consumed request or None."""
    now = datetime.utcnow()
    request = session.exec(
        select(ToolApprovalRequest)
        .where(ToolApprovalRequest.org_id == org_id)
        .where(ToolApprovalRequest.integration_id == integration_id)
        .where(ToolApprovalRequest.tool_name == tool_name)
        .where(ToolApprovalRequest.args_hash == args_hash)
        .where(ToolApprovalRequest.status == "approved")
        .where(ToolApprovalRequest.decision_mode == "approve_once")
        .where(ToolApprovalRequest.expires_at > now)
    ).first()
    if not request:
        return None

    request.status = "consumed"
    request.consumed_at = now
    session.add(request)
    session.commit()
    return request
