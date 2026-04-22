import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GoogleLoginState(SQLModel, table=True):
    """Pending Google sign-in flow.

    One row per /api/auth/google/login call. Cleared by the callback on success
    or by TTL cleanup on abandon. Unrelated to the Google integration OAuth.
    """

    __tablename__ = "google_login_state"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    state: str = Field(unique=True, index=True)
    code_verifier: str
    redirect_after: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)
