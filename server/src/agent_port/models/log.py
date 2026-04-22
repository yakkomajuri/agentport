import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class LogEntry(SQLModel, table=True):
    __tablename__ = "log_entry"

    id: int | None = Field(default=None, primary_key=True)
    org_id: uuid.UUID = Field(foreign_key="org.id", index=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    integration_id: str
    tool_name: str
    args_json: str | None = None
    result_json: str | None = None
    error: str | None = None
    duration_ms: int | None = None
    outcome: str | None = None  # pending | approved | executed | denied | error
    approval_request_id: uuid.UUID | None = None
    args_hash: str | None = None
    requester_ip: str | None = None
    user_agent: str | None = None
    api_key_label: str | None = None
    api_key_prefix: str | None = None
    access_reason: str | None = (
        None  # approved_once | approved_exact | approved_any | None (auto-allowed)
    )
    # Set when the call was made via admin impersonation — records the admin
    # who initiated the session so attribution can be separated from the
    # target user in the logs UI and downstream analytics.
    impersonator_user_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True)
    additional_info: str | None = None
