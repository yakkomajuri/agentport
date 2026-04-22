import uuid
from datetime import datetime, timezone

from sqlalchemy import Index, text
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    __tablename__ = "user"
    # Case-insensitive uniqueness on email. Portable across SQLite and
    # PostgreSQL via a functional index on LOWER(email). See Alembic
    # migration 0016 for the matching production DDL.
    __table_args__ = (Index("user_email_lower_uq", text("lower(email)"), unique=True),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(index=True)
    hashed_password: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)
    is_active: bool = Field(default=True)
    is_admin: bool = Field(default=False)

    # Google sign-in. Populated the first time a user logs in with Google
    # (identified by Google's stable `sub` claim). Independent of the Google
    # integration — this is purely for authenticating into agent-port.
    google_sub: str | None = Field(default=None, unique=True, index=True)

    # Email verification
    email_verified: bool = Field(default=False)
    email_verification_token_hash: str | None = Field(default=None)
    email_verification_code_hash: str | None = Field(default=None)
    email_verification_code_expires_at: datetime | None = Field(default=None)
    email_verification_sent_at: datetime | None = Field(default=None)
    email_verification_attempts: int = Field(default=0)

    # Password reset
    password_reset_token_hash: str | None = Field(default=None)
    password_reset_expires_at: datetime | None = Field(default=None)

    # TOTP (authenticator app) secondary factor. Secret persists across disable so
    # re-enabling does not require a fresh setup flow.
    totp_secret: str | None = Field(default=None)
    totp_enabled: bool = Field(default=False)
    totp_confirmed_at: datetime | None = Field(default=None)
    totp_recovery_codes_hash_json: str | None = Field(default=None)

    # Brute-force protection on /api/auth/token. Incremented on every failed
    # password check, reset on success. When the count crosses the lockout
    # threshold, locked_until pins the earliest time the account can try again.
    failed_login_attempts: int = Field(default=0)
    locked_until: datetime | None = Field(default=None)
