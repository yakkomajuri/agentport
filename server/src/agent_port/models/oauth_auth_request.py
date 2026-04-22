from datetime import datetime

from sqlmodel import Field, SQLModel


class OAuthAuthRequest(SQLModel, table=True):
    __tablename__ = "oauth_auth_request"

    session_token_hash: str = Field(primary_key=True)
    client_id: str = Field(index=True)
    redirect_uri: str
    redirect_uri_provided_explicitly: bool
    code_challenge: str
    scope: str | None = Field(default=None)
    state: str | None = Field(default=None)
    resource: str | None = Field(default=None)
    expires_at: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
