import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class ApiKey(SQLModel, table=True):
    __tablename__ = "api_key"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    org_id: uuid.UUID = Field(foreign_key="org.id", index=True)
    created_by_user_id: uuid.UUID = Field(foreign_key="user.id")
    name: str
    key_prefix: str  # first 12 chars of plain key, for display only
    key_hash: str = Field(index=True)  # SHA-256 hex of full plain key
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: datetime | None = Field(default=None)
    is_active: bool = Field(default=True)
