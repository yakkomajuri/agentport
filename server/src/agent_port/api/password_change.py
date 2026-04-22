from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from agent_port.api.schemas import MessageResponse
from agent_port.db import get_session
from agent_port.dependencies import get_current_user, get_impersonator
from agent_port.models.user import User
from agent_port.security import hash_password, verify_password

router = APIRouter(prefix="/api/users/me", tags=["password"])


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    impersonator: User | None = Depends(get_impersonator),
    session: Session = Depends(get_session),
) -> MessageResponse:
    # Block explicitly during impersonation. The current_password check
    # below would already stop an admin who doesn't know the target's
    # password, but making the refusal explicit gives a clearer error and
    # prevents future refactors (e.g. admin password reset) from leaving
    # this path open unintentionally.
    if impersonator is not None:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "impersonation_not_allowed",
                "message": "Passwords cannot be changed while impersonating.",
            },
        )

    if not current_user.hashed_password or not verify_password(
        body.current_password, current_user.hashed_password
    ):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")

    current_user.hashed_password = hash_password(body.new_password)
    session.add(current_user)
    session.commit()
    return MessageResponse(message="Password changed successfully")
