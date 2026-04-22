import uuid

from sqlmodel import Field, SQLModel


class OAuthAuthCode(SQLModel, table=True):
    __tablename__ = "oauth_auth_code"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    code: str = Field(unique=True, index=True)
    client_id: str = Field(index=True)
    org_id: uuid.UUID = Field(foreign_key="org.id", index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    redirect_uri: str
    redirect_uri_provided_explicitly: bool
    code_challenge: str
    scope: str | None = Field(default=None)
    resource: str | None = Field(default=None)
    expires_at: float
