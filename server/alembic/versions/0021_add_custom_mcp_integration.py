"""add custom_mcp_integration

Revision ID: 0021
Revises: 0020
Create Date: 2026-05-25

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op  # noqa: E402

revision: str = "0021"
down_revision: Union[str, Sequence[str], None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "custom_mcp_integration",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("integration_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("auth_method", sa.String(), nullable=False),
        sa.Column(
            "token_header",
            sa.String(),
            nullable=False,
            server_default="Authorization",
        ),
        sa.Column(
            "token_format",
            sa.String(),
            nullable=False,
            server_default="Bearer {token}",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["org.id"]),
        sa.UniqueConstraint(
            "org_id",
            "integration_id",
            name="uq_custom_mcp_integration_org_integration",
        ),
    )
    op.create_index(
        "ix_custom_mcp_integration_org_id",
        "custom_mcp_integration",
        ["org_id"],
    )
    op.create_index(
        "ix_custom_mcp_integration_integration_id",
        "custom_mcp_integration",
        ["integration_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_custom_mcp_integration_integration_id",
        table_name="custom_mcp_integration",
    )
    op.drop_index(
        "ix_custom_mcp_integration_org_id",
        table_name="custom_mcp_integration",
    )
    op.drop_table("custom_mcp_integration")
