import uuid
from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class ToolExecutionSetting(SQLModel, table=True):
    __tablename__ = "tool_execution_setting"
    __table_args__ = (
        UniqueConstraint("org_id", "integration_id", "tool_name", name="uq_tool_exec_org_int_tool"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    org_id: uuid.UUID = Field(foreign_key="org.id", index=True)
    integration_id: str
    tool_name: str
    mode: str = Field(default="require_approval")  # "allow" | "require_approval"
    updated_by_user_id: uuid.UUID | None = Field(default=None, foreign_key="user.id")
    updated_at: datetime = Field(default_factory=datetime.utcnow)
