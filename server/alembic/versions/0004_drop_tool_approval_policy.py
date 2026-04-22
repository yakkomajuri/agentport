"""drop tool_approval_policy table

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-15

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op  # noqa: E402

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_tool_approval_policy_org_id", table_name="tool_approval_policy")
    op.drop_table("tool_approval_policy")


def downgrade() -> None:
    op.create_table(
        "tool_approval_policy",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("integration_name", sa.String(), nullable=False),
        sa.Column("tool_name", sa.String(), nullable=False),
        sa.Column("match_type", sa.String(), nullable=False),
        sa.Column("args_json", sa.String(), nullable=False),
        sa.Column("args_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["org.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tool_approval_policy_org_id", "tool_approval_policy", ["org_id"], unique=False
    )
