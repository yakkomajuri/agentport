import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    message: str


class VerifyEmailResponse(MessageResponse):
    email: str


class VerifyEmailCodeResponse(MessageResponse):
    access_token: str | None = None
    token_type: str | None = None


class ResendVerificationResponse(MessageResponse):
    resend_available_at: datetime | None = None


class AwaitApprovalRequest(BaseModel):
    timeout_seconds: int | None = Field(default=None, gt=0)


class AwaitApprovalResponse(BaseModel):
    approval_request_id: uuid.UUID
    integration_id: str
    tool_name: str
    status: str
    message: str
    expires_at: datetime
    decision_mode: str | None = None
