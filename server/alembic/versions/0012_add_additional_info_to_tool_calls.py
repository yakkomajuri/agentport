"""add additional_info column to tool_approval_request and log_entry

Revision ID: 0012
Revises: 0011
Create Date: 2026-04-20

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op  # noqa: E402

revision: str = "0012"
down_revision: Union[str, Sequence[str], None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("tool_approval_request") as batch_op:
        batch_op.add_column(sa.Column("additional_info", sa.String(), nullable=True))
    with op.batch_alter_table("log_entry") as batch_op:
        batch_op.add_column(sa.Column("additional_info", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("log_entry") as batch_op:
        batch_op.drop_column("additional_info")
    with op.batch_alter_table("tool_approval_request") as batch_op:
        batch_op.drop_column("additional_info")
