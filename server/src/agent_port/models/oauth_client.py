import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class OAuthClient(SQLModel, table=True):
    __tablename__ = "oauth_client"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    client_id: str = Field(unique=True, index=True)
    client_secret_secret_id: uuid.UUID | None = Field(default=None, foreign_key="secret.id")
    client_name: str | None = None
    redirect_uris_json: str = "[]"
    grant_types_json: str = "[]"
    response_types_json: str = "[]"
    token_endpoint_auth_method: str | None = None
    client_id_issued_at: int
    client_secret_expires_at: int | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
