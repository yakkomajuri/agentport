import uuid
from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class CustomMcpIntegration(SQLModel, table=True):
    """User-defined remote MCP integration (org-scoped).

    Bundled integrations live in code (`integrations/bundled/`). This table holds
    user-added remote MCP URLs that the registry surfaces alongside bundled ones.
    """

    __tablename__ = "custom_mcp_integration"
    __table_args__ = (
        UniqueConstraint(
            "org_id", "integration_id", name="uq_custom_mcp_integration_org_integration"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    org_id: uuid.UUID = Field(foreign_key="org.id", index=True)
    integration_id: str = Field(index=True)  # "custom_<slug>", unique per org
    name: str
    url: str
    description: str | None = None
    auth_method: str  # "none" | "token"
    token_header: str = "Authorization"
    token_format: str = "Bearer {token}"
    created_at: datetime = Field(default_factory=datetime.utcnow)
