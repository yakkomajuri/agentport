"""split secrets into dedicated table

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-15

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _foreign_key_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {fk["name"] for fk in inspector.get_foreign_keys(table_name) if fk.get("name")}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "secret"):
        op.create_table(
            "secret",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("org_id", sa.Uuid(), nullable=True),
            sa.Column("kind", sa.String(), nullable=False),
            sa.Column("storage_backend", sa.String(), nullable=False),
            sa.Column("value", sa.String(), nullable=True),
            sa.Column("value_hash", sa.String(), nullable=False),
            sa.Column("prefix", sa.String(), nullable=True),
            sa.Column("external_ref", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["org_id"], ["org.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        inspector = sa.inspect(bind)

    secret_indexes = _index_names(inspector, "secret")
    if "ix_secret_org_id" not in secret_indexes:
        op.create_index("ix_secret_org_id", "secret", ["org_id"], unique=False)
    if "ix_secret_kind" not in secret_indexes:
        op.create_index("ix_secret_kind", "secret", ["kind"], unique=False)
    if "ix_secret_storage_backend" not in secret_indexes:
        op.create_index("ix_secret_storage_backend", "secret", ["storage_backend"], unique=False)
    if "ix_secret_value_hash" not in secret_indexes:
        op.create_index("ix_secret_value_hash", "secret", ["value_hash"], unique=False)

    installed_columns = _column_names(inspector, "installed_integration")
    installed_fks = _foreign_key_names(inspector, "installed_integration")
    with op.batch_alter_table("installed_integration") as batch_op:
        if "token_secret_id" not in installed_columns:
            batch_op.add_column(sa.Column("token_secret_id", sa.Uuid(), nullable=True))
        if "fk_installed_integration_token_secret_id_secret" not in installed_fks:
            batch_op.create_foreign_key(
                "fk_installed_integration_token_secret_id_secret",
                "secret",
                ["token_secret_id"],
                ["id"],
            )
        if "token" in installed_columns:
            batch_op.drop_column("token")

    inspector = sa.inspect(bind)
    oauth_state_columns = _column_names(inspector, "oauth_state")
    oauth_state_indexes = _index_names(inspector, "oauth_state")
    oauth_state_fks = _foreign_key_names(inspector, "oauth_state")
    with op.batch_alter_table("oauth_state") as batch_op:
        for column in (
            sa.Column("client_id", sa.String(), nullable=True),
            sa.Column("token_endpoint", sa.String(), nullable=True),
            sa.Column("state", sa.String(), nullable=True),
            sa.Column("scope", sa.String(), nullable=True),
            sa.Column("resource", sa.String(), nullable=True),
            sa.Column("client_secret_secret_id", sa.Uuid(), nullable=True),
            sa.Column("access_token_secret_id", sa.Uuid(), nullable=True),
            sa.Column("refresh_token_secret_id", sa.Uuid(), nullable=True),
            sa.Column("token_type", sa.String(), nullable=True),
            sa.Column("expires_in", sa.Integer(), nullable=True),
            sa.Column("obtained_at", sa.DateTime(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        ):
            if column.name not in oauth_state_columns:
                batch_op.add_column(column)
        if "ix_oauth_state_status" not in oauth_state_indexes:
            batch_op.create_index("ix_oauth_state_status", ["status"], unique=False)
        if "fk_oauth_state_client_secret_secret_id_secret" not in oauth_state_fks:
            batch_op.create_foreign_key(
                "fk_oauth_state_client_secret_secret_id_secret",
                "secret",
                ["client_secret_secret_id"],
                ["id"],
            )
        if "fk_oauth_state_access_token_secret_id_secret" not in oauth_state_fks:
            batch_op.create_foreign_key(
                "fk_oauth_state_access_token_secret_id_secret",
                "secret",
                ["access_token_secret_id"],
                ["id"],
            )
        if "fk_oauth_state_refresh_token_secret_id_secret" not in oauth_state_fks:
            batch_op.create_foreign_key(
                "fk_oauth_state_refresh_token_secret_id_secret",
                "secret",
                ["refresh_token_secret_id"],
                ["id"],
            )
        if "client_info_json" in oauth_state_columns:
            batch_op.drop_column("client_info_json")
        if "tokens_json" in oauth_state_columns:
            batch_op.drop_column("tokens_json")

    inspector = sa.inspect(bind)
    oauth_client_columns = _column_names(inspector, "oauth_client")
    oauth_client_fks = _foreign_key_names(inspector, "oauth_client")
    with op.batch_alter_table("oauth_client") as batch_op:
        for column in (
            sa.Column("client_secret_secret_id", sa.Uuid(), nullable=True),
            sa.Column("client_name", sa.String(), nullable=True),
            sa.Column("redirect_uris_json", sa.String(), nullable=False, server_default="[]"),
            sa.Column("grant_types_json", sa.String(), nullable=False, server_default="[]"),
            sa.Column("response_types_json", sa.String(), nullable=False, server_default="[]"),
            sa.Column("token_endpoint_auth_method", sa.String(), nullable=True),
        ):
            if column.name not in oauth_client_columns:
                batch_op.add_column(column)
        if "fk_oauth_client_client_secret_secret_id_secret" not in oauth_client_fks:
            batch_op.create_foreign_key(
                "fk_oauth_client_client_secret_secret_id_secret",
                "secret",
                ["client_secret_secret_id"],
                ["id"],
            )
        if "client_secret" in oauth_client_columns:
            batch_op.drop_column("client_secret")
        if "client_info_json" in oauth_client_columns:
            batch_op.drop_column("client_info_json")


def downgrade() -> None:
    op.add_column("oauth_client", sa.Column("client_info_json", sa.String(), nullable=False))
    op.add_column("oauth_client", sa.Column("client_secret", sa.String(), nullable=True))
    op.drop_constraint(
        "fk_oauth_client_client_secret_secret_id_secret", "oauth_client", type_="foreignkey"
    )
    op.drop_column("oauth_client", "token_endpoint_auth_method")
    op.drop_column("oauth_client", "response_types_json")
    op.drop_column("oauth_client", "grant_types_json")
    op.drop_column("oauth_client", "redirect_uris_json")
    op.drop_column("oauth_client", "client_name")
    op.drop_column("oauth_client", "client_secret_secret_id")

    op.add_column("oauth_state", sa.Column("tokens_json", sa.String(), nullable=True))
    op.add_column("oauth_state", sa.Column("client_info_json", sa.String(), nullable=True))
    op.drop_constraint(
        "fk_oauth_state_refresh_token_secret_id_secret", "oauth_state", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_oauth_state_access_token_secret_id_secret", "oauth_state", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_oauth_state_client_secret_secret_id_secret", "oauth_state", type_="foreignkey"
    )
    op.drop_index("ix_oauth_state_status", table_name="oauth_state")
    op.drop_column("oauth_state", "updated_at")
    op.drop_column("oauth_state", "created_at")
    op.drop_column("oauth_state", "status")
    op.drop_column("oauth_state", "obtained_at")
    op.drop_column("oauth_state", "expires_in")
    op.drop_column("oauth_state", "token_type")
    op.drop_column("oauth_state", "refresh_token_secret_id")
    op.drop_column("oauth_state", "access_token_secret_id")
    op.drop_column("oauth_state", "client_secret_secret_id")
    op.drop_column("oauth_state", "resource")
    op.drop_column("oauth_state", "scope")
    op.drop_column("oauth_state", "state")
    op.drop_column("oauth_state", "token_endpoint")
    op.drop_column("oauth_state", "client_id")

    op.add_column("installed_integration", sa.Column("token", sa.String(), nullable=True))
    op.drop_constraint(
        "fk_installed_integration_token_secret_id_secret",
        "installed_integration",
        type_="foreignkey",
    )
    op.drop_column("installed_integration", "token_secret_id")

    op.drop_index("ix_secret_value_hash", table_name="secret")
    op.drop_index("ix_secret_storage_backend", table_name="secret")
    op.drop_index("ix_secret_kind", table_name="secret")
    op.drop_index("ix_secret_org_id", table_name="secret")
    op.drop_table("secret")
