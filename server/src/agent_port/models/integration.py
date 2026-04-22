import uuid
from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class InstalledIntegration(SQLModel, table=True):
    __tablename__ = "installed_integration"
    __table_args__ = (
        UniqueConstraint(
            "org_id", "integration_id", name="uq_installed_integration_org_integration"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    org_id: uuid.UUID = Field(foreign_key="org.id", index=True)
    integration_id: str
    type: str
    url: str
    auth_method: str  # oauth | token
    token_secret_id: uuid.UUID | None = Field(default=None, foreign_key="secret.id")
    connected: bool = Field(default=False)
    updating_tool_cache: bool = Field(default=False)
    added_at: datetime = Field(default_factory=datetime.utcnow)
