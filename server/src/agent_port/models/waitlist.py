import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Waitlist(SQLModel, table=True):
    __tablename__ = "waitlist"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(unique=True, index=True)
    added_at: datetime = Field(default_factory=_utcnow)
    added_by_user_id: uuid.UUID | None = Field(default=None, foreign_key="user.id")
