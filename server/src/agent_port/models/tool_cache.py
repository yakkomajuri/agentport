import uuid
from datetime import datetime, timedelta

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

CACHE_TTL = timedelta(hours=24)


class ToolCache(SQLModel, table=True):
    __tablename__ = "tool_cache"
    __table_args__ = (
        UniqueConstraint("org_id", "integration_id", name="uq_tool_cache_org_integration"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    org_id: uuid.UUID = Field(foreign_key="org.id", index=True)
    integration_id: str
    tools_json: str
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
