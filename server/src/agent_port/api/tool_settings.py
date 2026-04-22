from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from agent_port.db import get_session
from agent_port.dependencies import get_current_org, get_current_user
from agent_port.models.org import Org
from agent_port.models.tool_execution import ToolExecutionSetting
from agent_port.models.user import User

router = APIRouter(prefix="/api/tool-settings", tags=["tool-settings"])

VALID_MODES = {"allow", "require_approval", "deny"}


class UpdateSettingRequest(BaseModel):
    mode: str


@router.get("/{integration_id}")
def list_settings(
    integration_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    current_org: Org = Depends(get_current_org),
) -> list[dict]:
    settings = session.exec(
        select(ToolExecutionSetting)
        .where(ToolExecutionSetting.org_id == current_org.id)
        .where(ToolExecutionSetting.integration_id == integration_id)
    ).all()
    return [s.model_dump() for s in settings]


@router.put("/{integration_id}/{tool_name}")
def update_setting(
    integration_id: str,
    tool_name: str,
    body: UpdateSettingRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    current_org: Org = Depends(get_current_org),
) -> dict:
    if body.mode not in VALID_MODES:
        raise HTTPException(
            status_code=400, detail=f"Invalid mode '{body.mode}'. Must be one of: {VALID_MODES}"
        )

    setting = session.exec(
        select(ToolExecutionSetting)
        .where(ToolExecutionSetting.org_id == current_org.id)
        .where(ToolExecutionSetting.integration_id == integration_id)
        .where(ToolExecutionSetting.tool_name == tool_name)
    ).first()

    if setting:
        setting.mode = body.mode
        setting.updated_by_user_id = current_user.id
        setting.updated_at = datetime.utcnow()
    else:
        setting = ToolExecutionSetting(
            org_id=current_org.id,
            integration_id=integration_id,
            tool_name=tool_name,
            mode=body.mode,
            updated_by_user_id=current_user.id,
            updated_at=datetime.utcnow(),
        )

    session.add(setting)
    session.commit()
    session.refresh(setting)
    return setting.model_dump()
