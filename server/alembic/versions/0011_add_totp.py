"""add TOTP fields to user

Revision ID: 0011
Revises: 0010
Create Date: 2026-04-18

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op  # noqa: E402

revision: str = "0011"
down_revision: Union[str, Sequence[str], None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("totp_secret", sa.String(), nullable=True))
        batch_op.add_column(
            sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("totp_confirmed_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("totp_recovery_codes_hash_json", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("totp_recovery_codes_hash_json")
        batch_op.drop_column("totp_confirmed_at")
        batch_op.drop_column("totp_enabled")
        batch_op.drop_column("totp_secret")
