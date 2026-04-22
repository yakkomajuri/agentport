from sqlmodel import Field, SQLModel


class OAuthRevokedToken(SQLModel, table=True):
    __tablename__ = "oauth_revoked_token"

    token_hash: str = Field(primary_key=True)
    expires_at: int
