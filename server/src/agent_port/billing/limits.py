import uuid

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, select

from agent_port.billing.gate import _is_plus
from agent_port.config import settings
from agent_port.models.integration import InstalledIntegration

FREE_INTEGRATION_LIMIT = 5


def enforce_integration_limit(org_id: uuid.UUID, session: Session) -> None:
    """Block free-tier cloud orgs once they have 5 installed integrations.

    Self-hosted installs are unlimited. On cloud, Plus subscribers are
    unlimited; everyone else is capped at FREE_INTEGRATION_LIMIT.
    """
    if not settings.is_cloud:
        return
    if _is_plus(org_id, session):
        return
    count = session.exec(
        select(func.count())
        .select_from(InstalledIntegration)
        .where(InstalledIntegration.org_id == org_id)
    ).one()
    if count >= FREE_INTEGRATION_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "free_tier_limit",
                "message": (
                    f"Free plan is limited to {FREE_INTEGRATION_LIMIT} integrations. "
                    "Upgrade to Plus for unlimited integrations."
                ),
                "limit": FREE_INTEGRATION_LIMIT,
            },
        )
