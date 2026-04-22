"""remove integration name, use integration_id everywhere

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

from alembic import op  # noqa: E402

revision: str = "0009"
down_revision: Union[str, Sequence[str], None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(conn, table: str, col: str) -> bool:
    return col in [c["name"] for c in sa_inspect(conn).get_columns(table)]


def _has_index(conn, table: str, idx: str) -> bool:
    return idx in [i["name"] for i in sa_inspect(conn).get_indexes(table)]


def _delete_duplicate_rows(table_name: str, partition_cols: list[str], order_by: str) -> None:
    partition_sql = ", ".join(partition_cols)
    op.execute(
        f"""
        DELETE FROM {table_name}
        WHERE id IN (
            SELECT id
            FROM (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY {partition_sql}
                        ORDER BY {order_by}
                    ) AS row_num
                FROM {table_name}
            ) ranked
            WHERE row_num > 1
        )
        """
    )


def upgrade() -> None:
    conn = op.get_bind()

    # ── oauth_state ────────────────────────────────────────────────────────────
    if _has_column(conn, "oauth_state", "integration_name"):
        op.execute("DROP TABLE IF EXISTS _alembic_tmp_oauth_state")
        op.execute(
            """
            UPDATE oauth_state
            SET integration_name = COALESCE(
                (SELECT integration_id FROM installed_integration
                 WHERE installed_integration.org_id = oauth_state.org_id
                   AND installed_integration.name = oauth_state.integration_name),
                oauth_state.integration_name
            )
            """
        )
        _delete_duplicate_rows(
            "oauth_state",
            ["org_id", "integration_name"],
            (
                "CASE WHEN status = 'connected' THEN 0 "
                "WHEN status = 'pending' THEN 1 ELSE 2 END ASC, "
                "updated_at DESC, created_at DESC, id DESC"
            ),
        )
        with op.batch_alter_table("oauth_state") as batch_op:
            batch_op.alter_column("integration_name", new_column_name="integration_id")

    # ── log_entry ──────────────────────────────────────────────────────────────
    if _has_column(conn, "log_entry", "integration_name"):
        op.execute("DROP TABLE IF EXISTS _alembic_tmp_log_entry")
        op.execute(
            """
            UPDATE log_entry
            SET integration_name = COALESCE(
                (SELECT integration_id FROM installed_integration
                 WHERE installed_integration.org_id = log_entry.org_id
                   AND installed_integration.name = log_entry.integration_name),
                log_entry.integration_name
            )
            """
        )
        with op.batch_alter_table("log_entry") as batch_op:
            batch_op.alter_column("integration_name", new_column_name="integration_id")

    # ── tool_cache ─────────────────────────────────────────────────────────────
    if _has_column(conn, "tool_cache", "integration_name"):
        op.execute("DROP TABLE IF EXISTS _alembic_tmp_tool_cache")
        with op.batch_alter_table("tool_cache") as batch_op:
            batch_op.drop_constraint("uq_tool_cache_org_integration", type_="unique")
        op.execute("DROP TABLE IF EXISTS _alembic_tmp_tool_cache")
        op.execute(
            """
            UPDATE tool_cache
            SET integration_name = COALESCE(
                (SELECT integration_id FROM installed_integration
                 WHERE installed_integration.org_id = tool_cache.org_id
                   AND installed_integration.name = tool_cache.integration_name),
                tool_cache.integration_name
            )
            """
        )
        _delete_duplicate_rows(
            "tool_cache",
            ["org_id", "integration_name"],
            "fetched_at DESC, id DESC",
        )
        with op.batch_alter_table("tool_cache") as batch_op:
            batch_op.alter_column("integration_name", new_column_name="integration_id")
            batch_op.create_unique_constraint(
                "uq_tool_cache_org_integration", ["org_id", "integration_id"]
            )

    # ── tool_execution_setting ─────────────────────────────────────────────────
    if _has_column(conn, "tool_execution_setting", "integration_name"):
        op.execute("DROP TABLE IF EXISTS _alembic_tmp_tool_execution_setting")
        with op.batch_alter_table("tool_execution_setting") as batch_op:
            batch_op.drop_constraint("uq_tool_exec_org_int_tool", type_="unique")
        op.execute("DROP TABLE IF EXISTS _alembic_tmp_tool_execution_setting")
        op.execute(
            """
            UPDATE tool_execution_setting
            SET integration_name = COALESCE(
                (SELECT integration_id FROM installed_integration
                 WHERE installed_integration.org_id = tool_execution_setting.org_id
                   AND installed_integration.name = tool_execution_setting.integration_name),
                tool_execution_setting.integration_name
            )
            """
        )
        _delete_duplicate_rows(
            "tool_execution_setting",
            ["org_id", "integration_name", "tool_name"],
            "updated_at DESC, id DESC",
        )
        with op.batch_alter_table("tool_execution_setting") as batch_op:
            batch_op.alter_column("integration_name", new_column_name="integration_id")
            batch_op.create_unique_constraint(
                "uq_tool_exec_org_int_tool", ["org_id", "integration_id", "tool_name"]
            )

    # ── tool_approval_request ──────────────────────────────────────────────────
    # Move drop_index / create_index OUTSIDE batch_alter_table to avoid an
    # Alembic bug where _gather_indexes_from_both_tables raises KeyError when
    # a column rename and an index rename happen in the same batch operation.
    if _has_column(conn, "tool_approval_request", "integration_name"):
        op.execute(
            """
            UPDATE tool_approval_request
            SET integration_name = COALESCE(
                (SELECT integration_id FROM installed_integration
                 WHERE installed_integration.org_id = tool_approval_request.org_id
                   AND installed_integration.name = tool_approval_request.integration_name),
                tool_approval_request.integration_name
            )
            """
        )
        if _has_index(conn, "tool_approval_request", "ix_approval_req_lookup"):
            op.drop_index("ix_approval_req_lookup", table_name="tool_approval_request")
        op.execute("DROP TABLE IF EXISTS _alembic_tmp_tool_approval_request")
        with op.batch_alter_table("tool_approval_request") as batch_op:
            batch_op.alter_column("integration_name", new_column_name="integration_id")
        op.create_index(
            "ix_approval_req_lookup",
            "tool_approval_request",
            ["org_id", "integration_id", "tool_name", "args_hash", "status"],
        )

    # ── installed_integration (last, after all data migrations) ───────────────
    if _has_column(conn, "installed_integration", "name"):
        op.execute("DROP TABLE IF EXISTS _alembic_tmp_installed_integration")
        _delete_duplicate_rows(
            "installed_integration",
            ["org_id", "integration_id"],
            "connected DESC, added_at DESC, id DESC",
        )
        with op.batch_alter_table("installed_integration") as batch_op:
            batch_op.drop_constraint("uq_installed_integration_org_name", type_="unique")
            batch_op.drop_column("name")
            batch_op.create_unique_constraint(
                "uq_installed_integration_org_integration", ["org_id", "integration_id"]
            )


def downgrade() -> None:
    # Re-add name column to installed_integration (data is lost)
    with op.batch_alter_table("installed_integration") as batch_op:
        batch_op.drop_constraint("uq_installed_integration_org_integration", type_="unique")
        batch_op.add_column(sa.Column("name", sa.String(), nullable=False, server_default=""))
        batch_op.create_unique_constraint("uq_installed_integration_org_name", ["org_id", "name"])

    # Rename integration_id back to integration_name in all tables
    with op.batch_alter_table("oauth_state") as batch_op:
        batch_op.alter_column("integration_id", new_column_name="integration_name")

    with op.batch_alter_table("log_entry") as batch_op:
        batch_op.alter_column("integration_id", new_column_name="integration_name")

    with op.batch_alter_table("tool_cache") as batch_op:
        batch_op.drop_constraint("uq_tool_cache_org_integration", type_="unique")
        batch_op.alter_column("integration_id", new_column_name="integration_name")
        batch_op.create_unique_constraint(
            "uq_tool_cache_org_integration", ["org_id", "integration_name"]
        )

    with op.batch_alter_table("tool_execution_setting") as batch_op:
        batch_op.drop_constraint("uq_tool_exec_org_int_tool", type_="unique")
        batch_op.alter_column("integration_id", new_column_name="integration_name")
        batch_op.create_unique_constraint(
            "uq_tool_exec_org_int_tool", ["org_id", "integration_name", "tool_name"]
        )

    op.drop_index("ix_approval_req_lookup", table_name="tool_approval_request")
    with op.batch_alter_table("tool_approval_request") as batch_op:
        batch_op.alter_column("integration_id", new_column_name="integration_name")
    op.create_index(
        "ix_approval_req_lookup",
        "tool_approval_request",
        ["org_id", "integration_name", "tool_name", "args_hash", "status"],
    )
