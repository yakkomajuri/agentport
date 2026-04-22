from datetime import datetime

from pydantic import BaseModel


class MessageResponse(BaseModel):
    message: str


class VerifyEmailResponse(MessageResponse):
    email: str


class VerifyEmailCodeResponse(MessageResponse):
    access_token: str | None = None
    token_type: str | None = None


class ResendVerificationResponse(MessageResponse):
    resend_available_at: datetime | None = None
