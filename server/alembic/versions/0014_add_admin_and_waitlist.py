"""add admin and waitlist

Revision ID: 0014
Revises: 0013
Create Date: 2026-04-21

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op  # noqa: E402

revision: str = "0014"
down_revision: Union[str, Sequence[str], None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_admin",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    op.create_table(
        "waitlist",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("added_at", sa.DateTime(), nullable=False),
        sa.Column("added_by_user_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["added_by_user_id"], ["user.id"]),
    )
    op.create_index("ix_waitlist_email", "waitlist", ["email"], unique=True)

    op.create_table(
        "instance_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "waitlist_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.bulk_insert(
        sa.table(
            "instance_settings",
            sa.column("id", sa.Integer()),
            sa.column("waitlist_enabled", sa.Boolean()),
        ),
        [{"id": 1, "waitlist_enabled": False}],
    )


def downgrade() -> None:
    op.drop_table("instance_settings")

    op.drop_index("ix_waitlist_email", table_name="waitlist")
    op.drop_table("waitlist")

    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("is_admin")
