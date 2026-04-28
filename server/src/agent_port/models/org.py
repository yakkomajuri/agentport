import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class Org(SQLModel, table=True):
    __tablename__ = "org"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    # Per-org override for how long a pending approval request stays valid
    # before expiring. None falls back to settings.approval_expiry_minutes.
    approval_expiry_minutes: int | None = Field(default=None)
