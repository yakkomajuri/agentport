"""add updating_tool_cache to installed_integration

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-16

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op  # noqa: E402

revision: str = "0008"
down_revision: Union[str, Sequence[str], None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("installed_integration") as batch_op:
        batch_op.add_column(
            sa.Column(
                "updating_tool_cache",
                sa.Boolean(),
                nullable=False,
                server_default="false",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("installed_integration") as batch_op:
        batch_op.drop_column("updating_tool_cache")
