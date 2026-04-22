"""add google login

Revision ID: 0013
Revises: 0012
Create Date: 2026-04-20

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op  # noqa: E402

revision: str = "0013"
down_revision: Union[str, Sequence[str], None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.alter_column("hashed_password", existing_type=sa.String(), nullable=True)
        batch_op.add_column(sa.Column("google_sub", sa.String(), nullable=True))
        batch_op.create_unique_constraint("uq_user_google_sub", ["google_sub"])
        batch_op.create_index("ix_user_google_sub", ["google_sub"], unique=False)

    op.create_table(
        "google_login_state",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("code_verifier", sa.String(), nullable=False),
        sa.Column("redirect_after", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_google_login_state_state", "google_login_state", ["state"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_google_login_state_state", table_name="google_login_state")
    op.drop_table("google_login_state")

    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_index("ix_user_google_sub")
        batch_op.drop_constraint("uq_user_google_sub", type_="unique")
        batch_op.drop_column("google_sub")
        batch_op.alter_column("hashed_password", existing_type=sa.String(), nullable=False)
