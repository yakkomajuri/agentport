from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, col, select

from agent_port.db import get_session
from agent_port.dependencies import get_current_org, get_current_user
from agent_port.models.log import LogEntry
from agent_port.models.org import Org
from agent_port.models.tool_approval_request import ToolApprovalRequest
from agent_port.models.user import User

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("")
def list_logs(
    integration: str | None = None,
    tool: str | None = None,
    outcome: str | None = None,
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    current_org: Org = Depends(get_current_org),
) -> list[dict]:
    stmt = (
        select(LogEntry).where(LogEntry.org_id == current_org.id).order_by(col(LogEntry.id).desc())
    )

    if integration:
        stmt = stmt.where(LogEntry.integration_id == integration)
    if tool:
        stmt = stmt.where(LogEntry.tool_name == tool)
    if outcome:
        stmt = stmt.where(LogEntry.outcome == outcome)

    stmt = stmt.offset(offset).limit(limit)
    logs = session.exec(stmt).all()

    # Attach approval_expires_at for pending entries so the frontend can detect expiry
    pending_ids = [
        log.approval_request_id
        for log in logs
        if log.outcome == "pending" and log.approval_request_id is not None
    ]
    expires_map: dict = {}
    if pending_ids:
        approvals = session.exec(
            select(ToolApprovalRequest).where(col(ToolApprovalRequest.id).in_(pending_ids))
        ).all()
        expires_map = {a.id: a.expires_at.isoformat() for a in approvals}

    result = []
    for log in logs:
        d = log.model_dump()
        if log.approval_request_id in expires_map:
            d["approval_expires_at"] = expires_map[log.approval_request_id]
        result.append(d)
    return result
