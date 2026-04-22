import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class Subscription(SQLModel, table=True):
    __tablename__ = "subscription"

    org_id: uuid.UUID = Field(foreign_key="org.id", primary_key=True)
    stripe_customer_id: str = Field(index=True)
    stripe_subscription_id: str | None = Field(default=None, index=True)
    tier: str = Field(default="free")  # "free" | "plus"
    status: str = Field(default="active")  # active | trialing | past_due | canceled | incomplete
    current_period_end: datetime | None = Field(default=None)
    cancel_at_period_end: bool = Field(default=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
