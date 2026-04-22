import uuid
from datetime import datetime

from sqlalchemy import Index
from sqlmodel import Field, SQLModel


class ToolApprovalRequest(SQLModel, table=True):
    __tablename__ = "tool_approval_request"
    __table_args__ = (
        Index(
            "ix_approval_req_lookup",
            "org_id",
            "integration_id",
            "tool_name",
            "args_hash",
            "status",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    org_id: uuid.UUID = Field(foreign_key="org.id", index=True)
    integration_id: str
    tool_name: str
    args_json: str
    args_hash: str
    summary_text: str
    # pending | approved | denied | expired | consumed | auto_approved
    status: str = Field(default="pending")
    requested_by_user_id: uuid.UUID | None = Field(default=None, foreign_key="user.id")
    requested_by_agent: str | None = None
    requested_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    decision_mode: str | None = None  # approve_once | allow_tool_forever | deny
    decided_by_user_id: uuid.UUID | None = Field(default=None, foreign_key="user.id")
    decided_at: datetime | None = None
    consumed_at: datetime | None = None
    requester_ip: str | None = None
    user_agent: str | None = None
    api_key_label: str | None = None
    api_key_prefix: str | None = None
    approver_ip: str | None = None
    policy_created: bool = Field(default=False)
    # Optional free-text explanation supplied by the caller at request time
    # (e.g. "I need this to decide between A and B"). Helps humans judge the call.
    additional_info: str | None = None
