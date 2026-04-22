"""add impersonator_user_id to log_entry

Revision ID: 0019
Revises: 0018
Create Date: 2026-04-22

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op  # noqa: E402

revision: str = "0019"
down_revision: Union[str, Sequence[str], None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("log_entry") as batch_op:
        batch_op.add_column(sa.Column("impersonator_user_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_log_entry_impersonator_user_id_user",
            "user",
            ["impersonator_user_id"],
            ["id"],
        )
    op.create_index(
        "ix_log_entry_impersonator_user_id",
        "log_entry",
        ["impersonator_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_log_entry_impersonator_user_id", table_name="log_entry")
    with op.batch_alter_table("log_entry") as batch_op:
        batch_op.drop_constraint("fk_log_entry_impersonator_user_id_user", type_="foreignkey")
        batch_op.drop_column("impersonator_user_id")
