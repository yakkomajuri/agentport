"""add custom_api_integration

Revision ID: 0022
Revises: 0021
Create Date: 2026-06-01

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0022"
down_revision: Union[str, Sequence[str], None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "custom_api_integration",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("integration_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("base_url", sa.String(), nullable=False),
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
        sa.Column("tools_json", sa.String(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["org.id"]),
        sa.UniqueConstraint(
            "org_id",
            "integration_id",
            name="uq_custom_api_integration_org_integration",
        ),
    )
    op.create_index(
        "ix_custom_api_integration_org_id",
        "custom_api_integration",
        ["org_id"],
    )
    op.create_index(
        "ix_custom_api_integration_integration_id",
        "custom_api_integration",
        ["integration_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_custom_api_integration_integration_id",
        table_name="custom_api_integration",
    )
    op.drop_index(
        "ix_custom_api_integration_org_id",
        table_name="custom_api_integration",
    )
    op.drop_table("custom_api_integration")
