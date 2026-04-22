"""add email verification codes and resend tracking

Revision ID: 0010
Revises: 0009
Create Date: 2026-04-17

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op  # noqa: E402

revision: str = "0010"
down_revision: Union[str, Sequence[str], None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("email_verification_code_hash", sa.String(), nullable=True))
        batch_op.add_column(
            sa.Column("email_verification_code_expires_at", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(sa.Column("email_verification_sent_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("email_verification_sent_at")
        batch_op.drop_column("email_verification_code_expires_at")
        batch_op.drop_column("email_verification_code_hash")
