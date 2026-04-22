import uuid

from sqlmodel import Field, SQLModel


class OrgMembership(SQLModel, table=True):
    __tablename__ = "org_membership"

    user_id: uuid.UUID = Field(foreign_key="user.id", primary_key=True)
    org_id: uuid.UUID = Field(foreign_key="org.id", primary_key=True)
    role: str = Field(default="owner")  # "owner" | "member"
