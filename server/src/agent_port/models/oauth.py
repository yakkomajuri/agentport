import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class OAuthState(SQLModel, table=True):
    __tablename__ = "oauth_state"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    org_id: uuid.UUID = Field(foreign_key="org.id", index=True)
    integration_id: str
    client_id: str | None = None
    token_endpoint: str | None = None
    state: str | None = None
    scope: str | None = None
    resource: str | None = None
    code_verifier: str | None = None
    client_secret_secret_id: uuid.UUID | None = Field(default=None, foreign_key="secret.id")
    access_token_secret_id: uuid.UUID | None = Field(default=None, foreign_key="secret.id")
    refresh_token_secret_id: uuid.UUID | None = Field(default=None, foreign_key="secret.id")
    token_type: str | None = None
    expires_in: int | None = None
    obtained_at: datetime | None = None
    status: str = Field(default="pending", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
