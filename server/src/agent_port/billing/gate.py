import uuid

from fastapi import Depends, HTTPException, status
from sqlmodel import Session

from agent_port.db import get_session
from agent_port.dependencies import get_current_org
from agent_port.models.org import Org
from agent_port.models.subscription import Subscription

ACTIVE_STATUSES = {"active", "trialing"}


def _is_plus(org_id: uuid.UUID, session: Session) -> bool:
    sub = session.get(Subscription, org_id)
    if sub is None:
        return False
    return sub.tier == "plus" and sub.status in ACTIVE_STATUSES


def require_plus(
    org: Org = Depends(get_current_org),
    session: Session = Depends(get_session),
) -> None:
    if not _is_plus(org.id, session):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="plus_required",
        )
