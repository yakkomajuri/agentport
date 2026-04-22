from sqlmodel import Field, SQLModel


class InstanceSettings(SQLModel, table=True):
    """Singleton row (id=1) holding instance-wide runtime toggles.

    Seeded by migration; always read via `get_instance_settings(session)`.
    """

    __tablename__ = "instance_settings"

    id: int = Field(default=1, primary_key=True)
    waitlist_enabled: bool = Field(default=False)
