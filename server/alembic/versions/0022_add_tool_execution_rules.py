"""add tool execution rules

Revision ID: 0022
Revises: 0021
Create Date: 2026-06-01

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op  # noqa: E402

revision: str = "0022"
down_revision: Union[str, Sequence[str], None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tool_execution_rule",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("integration_id", sa.String(), nullable=False),
        sa.Column("tool_name", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("effect", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["org.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
    )
    op.create_index(
        "ix_tool_execution_rule_org_id",
        "tool_execution_rule",
        ["org_id"],
    )
    op.create_index(
        "ix_tool_exec_rule_lookup",
        "tool_execution_rule",
        ["org_id", "integration_id", "tool_name", "enabled"],
    )

    op.create_table(
        "tool_execution_rule_condition",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("rule_id", sa.Uuid(), nullable=False),
        sa.Column("param_path", sa.String(), nullable=False),
        sa.Column("operator", sa.String(), nullable=False),
        sa.Column("values_json", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["rule_id"], ["tool_execution_rule.id"]),
    )
    op.create_index(
        "ix_tool_execution_rule_condition_rule_id",
        "tool_execution_rule_condition",
        ["rule_id"],
    )
    op.create_index(
        "ix_tool_exec_rule_cond_rule",
        "tool_execution_rule_condition",
        ["rule_id"],
    )

    op.add_column("log_entry", sa.Column("matched_rule_id", sa.Uuid(), nullable=True))
    op.create_index("ix_log_entry_matched_rule_id", "log_entry", ["matched_rule_id"])
    op.add_column("tool_approval_request", sa.Column("matched_rule_id", sa.Uuid(), nullable=True))


def downgrade() -> None:
    op.drop_column("tool_approval_request", "matched_rule_id")
    op.drop_index("ix_log_entry_matched_rule_id", table_name="log_entry")
    op.drop_column("log_entry", "matched_rule_id")
    op.drop_index(
        "ix_tool_exec_rule_cond_rule",
        table_name="tool_execution_rule_condition",
    )
    op.drop_index(
        "ix_tool_execution_rule_condition_rule_id",
        table_name="tool_execution_rule_condition",
    )
    op.drop_table("tool_execution_rule_condition")
    op.drop_index("ix_tool_exec_rule_lookup", table_name="tool_execution_rule")
    op.drop_index("ix_tool_execution_rule_org_id", table_name="tool_execution_rule")
    op.drop_table("tool_execution_rule")
