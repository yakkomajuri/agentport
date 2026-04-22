"""replace external secret refs with kms fields

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-15

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    secret_columns = _column_names(inspector, "secret")

    with op.batch_alter_table("secret") as batch_op:
        if "encrypted_data_key" not in secret_columns:
            batch_op.add_column(sa.Column("encrypted_data_key", sa.String(), nullable=True))
        if "kms_key_id" not in secret_columns:
            batch_op.add_column(sa.Column("kms_key_id", sa.String(), nullable=True))
        if "external_ref" in secret_columns:
            batch_op.drop_column("external_ref")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    secret_columns = _column_names(inspector, "secret")

    with op.batch_alter_table("secret") as batch_op:
        if "external_ref" not in secret_columns:
            batch_op.add_column(sa.Column("external_ref", sa.String(), nullable=True))
        if "kms_key_id" in secret_columns:
            batch_op.drop_column("kms_key_id")
        if "encrypted_data_key" in secret_columns:
            batch_op.drop_column("encrypted_data_key")
