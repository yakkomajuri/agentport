"""add email verification and password reset fields to user

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-15

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op  # noqa: E402

revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # New users default to unverified. Existing users are backfilled as verified
    # below, since they were never asked to verify and should not be locked out.
    op.add_column(
        "user",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("user", sa.Column("email_verification_token_hash", sa.String(), nullable=True))
    op.add_column("user", sa.Column("password_reset_token_hash", sa.String(), nullable=True))
    op.add_column("user", sa.Column("password_reset_expires_at", sa.DateTime(), nullable=True))

    # Backfill: mark all pre-existing users as verified
    op.execute(sa.text('UPDATE "user" SET email_verified = true'))


def downgrade() -> None:
    op.drop_column("user", "password_reset_expires_at")
    op.drop_column("user", "password_reset_token_hash")
    op.drop_column("user", "email_verification_token_hash")
    op.drop_column("user", "email_verified")
