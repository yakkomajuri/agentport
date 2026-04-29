"""add approval_expiry_minutes to org

Revision ID: 0020
Revises: 0019
Create Date: 2026-04-28

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op  # noqa: E402

revision: str = "0020"
down_revision: Union[str, Sequence[str], None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("org") as batch_op:
        batch_op.add_column(sa.Column("approval_expiry_minutes", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("org") as batch_op:
        batch_op.drop_column("approval_expiry_minutes")
