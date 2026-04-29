from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from agent_port.config import settings
from agent_port.db import get_session
from agent_port.dependencies import get_current_org
from agent_port.models.org import Org

router = APIRouter(prefix="/api/org-settings", tags=["org-settings"])

# Bounds for the per-org approval expiry window. The lower bound keeps the
# UI usable (giving an approver time to react), the upper bound caps the
# blast radius of a stale pending request.
MIN_APPROVAL_EXPIRY_MINUTES = 1
MAX_APPROVAL_EXPIRY_MINUTES = 1440


class OrgSettingsResponse(BaseModel):
    approval_expiry_minutes: int
    approval_expiry_minutes_default: int
    approval_expiry_minutes_override: int | None


class UpdateOrgSettingsRequest(BaseModel):
    approval_expiry_minutes: int | None = Field(
        default=None,
        description=(
            "How many minutes a pending approval request stays valid. "
            "Pass null to revert to the instance default."
        ),
    )


def _serialize(org: Org) -> OrgSettingsResponse:
    default = settings.approval_expiry_minutes
    return OrgSettingsResponse(
        approval_expiry_minutes=org.approval_expiry_minutes or default,
        approval_expiry_minutes_default=default,
        approval_expiry_minutes_override=org.approval_expiry_minutes,
    )


@router.get("", response_model=OrgSettingsResponse)
def get_settings(
    current_org: Org = Depends(get_current_org),
) -> OrgSettingsResponse:
    return _serialize(current_org)


@router.patch("", response_model=OrgSettingsResponse)
def update_settings(
    body: UpdateOrgSettingsRequest,
    session: Session = Depends(get_session),
    current_org: Org = Depends(get_current_org),
) -> OrgSettingsResponse:
    value = body.approval_expiry_minutes
    if value is not None and not (
        MIN_APPROVAL_EXPIRY_MINUTES <= value <= MAX_APPROVAL_EXPIRY_MINUTES
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                f"approval_expiry_minutes must be between {MIN_APPROVAL_EXPIRY_MINUTES} "
                f"and {MAX_APPROVAL_EXPIRY_MINUTES}"
            ),
        )
    current_org.approval_expiry_minutes = value
    session.add(current_org)
    session.commit()
    session.refresh(current_org)
    return _serialize(current_org)
