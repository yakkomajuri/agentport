"""add subscription

Revision ID: 0015
Revises: 0014
Create Date: 2026-04-21

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op  # noqa: E402

revision: str = "0015"
down_revision: Union[str, Sequence[str], None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscription",
        sa.Column("org_id", sa.Uuid(), primary_key=True),
        sa.Column("stripe_customer_id", sa.String(), nullable=False),
        sa.Column("stripe_subscription_id", sa.String(), nullable=True),
        sa.Column("tier", sa.String(), nullable=False, server_default="free"),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("current_period_end", sa.DateTime(), nullable=True),
        sa.Column(
            "cancel_at_period_end",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["org.id"]),
    )
    op.create_index(
        "ix_subscription_stripe_customer_id",
        "subscription",
        ["stripe_customer_id"],
        unique=False,
    )
    op.create_index(
        "ix_subscription_stripe_subscription_id",
        "subscription",
        ["stripe_subscription_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_subscription_stripe_subscription_id", table_name="subscription")
    op.drop_index("ix_subscription_stripe_customer_id", table_name="subscription")
    op.drop_table("subscription")
