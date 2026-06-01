import uuid
from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class CustomApiIntegration(SQLModel, table=True):
    """User-defined REST API integration (org-scoped)."""

    __tablename__ = "custom_api_integration"
    __table_args__ = (
        UniqueConstraint(
            "org_id",
            "integration_id",
            name="uq_custom_api_integration_org_integration",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    org_id: uuid.UUID = Field(foreign_key="org.id", index=True)
    integration_id: str = Field(index=True)  # "customapi_<slug>", unique per org
    name: str
    description: str | None = None
    base_url: str
    token_header: str = "Authorization"
    token_format: str = "Bearer {token}"
    tools_json: str = Field(default="[]")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
