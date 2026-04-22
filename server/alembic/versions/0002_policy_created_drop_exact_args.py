"""add policy_created, drop exact_args policies

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-14

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op  # noqa: E402

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tool_approval_request",
        sa.Column("policy_created", sa.Boolean(), nullable=False, server_default="0"),
    )
    # exact_args policies are no longer evaluated; remove any that exist
    op.execute("DELETE FROM tool_approval_policy WHERE match_type = 'exact_args'")


def downgrade() -> None:
    op.drop_column("tool_approval_request", "policy_created")
