"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-14

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Tables with no foreign-key dependencies ─────────────────────────────

    op.create_table(
        "org",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "user",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_email", "user", ["email"], unique=True)

    op.create_table(
        "oauth_client",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.String(), nullable=False),
        sa.Column("client_secret", sa.String(), nullable=True),
        sa.Column("client_info_json", sa.String(), nullable=False),
        sa.Column("client_id_issued_at", sa.Integer(), nullable=False),
        sa.Column("client_secret_expires_at", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_oauth_client_client_id", "oauth_client", ["client_id"], unique=True)

    op.create_table(
        "oauth_auth_request",
        sa.Column("session_token_hash", sa.String(), nullable=False),
        sa.Column("client_id", sa.String(), nullable=False),
        sa.Column("redirect_uri", sa.String(), nullable=False),
        sa.Column("redirect_uri_provided_explicitly", sa.Boolean(), nullable=False),
        sa.Column("code_challenge", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=True),
        sa.Column("state", sa.String(), nullable=True),
        sa.Column("resource", sa.String(), nullable=True),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("session_token_hash"),
    )
    op.create_index(
        "ix_oauth_auth_request_client_id", "oauth_auth_request", ["client_id"], unique=False
    )

    op.create_table(
        "oauth_revoked_token",
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("token_hash"),
    )

    # ── Tables that depend on org / user ────────────────────────────────────

    op.create_table(
        "org_membership",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["org.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("user_id", "org_id"),
    )

    op.create_table(
        "installed_integration",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("integration_id", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("auth_method", sa.String(), nullable=False),
        sa.Column("token", sa.String(), nullable=True),
        sa.Column("connected", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("added_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["org.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "name", name="uq_installed_integration_org_name"),
    )
    op.create_index(
        "ix_installed_integration_org_id", "installed_integration", ["org_id"], unique=False
    )

    op.create_table(
        "oauth_state",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("integration_name", sa.String(), nullable=False),
        sa.Column("client_info_json", sa.String(), nullable=True),
        sa.Column("tokens_json", sa.String(), nullable=True),
        sa.Column("code_verifier", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["org.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_oauth_state_org_id", "oauth_state", ["org_id"], unique=False)

    op.create_table(
        "tool_cache",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("integration_name", sa.String(), nullable=False),
        sa.Column("tools_json", sa.String(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["org.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "integration_name", name="uq_tool_cache_org_integration"),
    )
    op.create_index("ix_tool_cache_org_id", "tool_cache", ["org_id"], unique=False)

    op.create_table(
        "tool_approval_policy",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("integration_name", sa.String(), nullable=False),
        sa.Column("tool_name", sa.String(), nullable=False),
        sa.Column("match_type", sa.String(), nullable=False),
        sa.Column("args_json", sa.String(), nullable=False),
        sa.Column("args_hash", sa.String(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["org.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "org_id",
            "integration_name",
            "tool_name",
            "match_type",
            "args_hash",
            name="uq_approval_policy_exact",
        ),
    )
    op.create_index(
        "ix_tool_approval_policy_org_id", "tool_approval_policy", ["org_id"], unique=False
    )

    op.create_table(
        "tool_execution_setting",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("integration_name", sa.String(), nullable=False),
        sa.Column("tool_name", sa.String(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["org.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "org_id", "integration_name", "tool_name", name="uq_tool_exec_org_int_tool"
        ),
    )
    op.create_index(
        "ix_tool_execution_setting_org_id", "tool_execution_setting", ["org_id"], unique=False
    )

    op.create_table(
        "api_key",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("key_prefix", sa.String(), nullable=False),
        sa.Column("key_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["org.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_key_org_id", "api_key", ["org_id"], unique=False)
    op.create_index("ix_api_key_key_hash", "api_key", ["key_hash"], unique=False)

    op.create_table(
        "tool_approval_request",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("integration_name", sa.String(), nullable=False),
        sa.Column("tool_name", sa.String(), nullable=False),
        sa.Column("args_json", sa.String(), nullable=False),
        sa.Column("args_hash", sa.String(), nullable=False),
        sa.Column("summary_text", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("requested_by_agent", sa.String(), nullable=True),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("decision_mode", sa.String(), nullable=True),
        sa.Column("decided_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("requester_ip", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("api_key_label", sa.String(), nullable=True),
        sa.Column("api_key_prefix", sa.String(), nullable=True),
        sa.Column("approver_ip", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["org.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tool_approval_request_org_id", "tool_approval_request", ["org_id"], unique=False
    )
    op.create_index(
        "ix_approval_req_lookup",
        "tool_approval_request",
        ["org_id", "integration_name", "tool_name", "args_hash", "status"],
        unique=False,
    )

    op.create_table(
        "log_entry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("integration_name", sa.String(), nullable=False),
        sa.Column("tool_name", sa.String(), nullable=False),
        sa.Column("args_json", sa.String(), nullable=True),
        sa.Column("result_json", sa.String(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("outcome", sa.String(), nullable=True),
        sa.Column("approval_request_id", sa.Uuid(), nullable=True),
        sa.Column("args_hash", sa.String(), nullable=True),
        sa.Column("requester_ip", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("api_key_label", sa.String(), nullable=True),
        sa.Column("api_key_prefix", sa.String(), nullable=True),
        sa.Column("access_reason", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["org.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_log_entry_org_id", "log_entry", ["org_id"], unique=False)

    op.create_table(
        "oauth_auth_code",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("client_id", sa.String(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("redirect_uri", sa.String(), nullable=False),
        sa.Column("redirect_uri_provided_explicitly", sa.Boolean(), nullable=False),
        sa.Column("code_challenge", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=True),
        sa.Column("resource", sa.String(), nullable=True),
        sa.Column("expires_at", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["org.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_oauth_auth_code_code", "oauth_auth_code", ["code"], unique=True)
    op.create_index("ix_oauth_auth_code_client_id", "oauth_auth_code", ["client_id"], unique=False)
    op.create_index("ix_oauth_auth_code_org_id", "oauth_auth_code", ["org_id"], unique=False)
    op.create_index("ix_oauth_auth_code_user_id", "oauth_auth_code", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_oauth_auth_code_user_id", table_name="oauth_auth_code")
    op.drop_index("ix_oauth_auth_code_org_id", table_name="oauth_auth_code")
    op.drop_index("ix_oauth_auth_code_client_id", table_name="oauth_auth_code")
    op.drop_index("ix_oauth_auth_code_code", table_name="oauth_auth_code")
    op.drop_table("oauth_auth_code")
    op.drop_index("ix_log_entry_org_id", table_name="log_entry")
    op.drop_table("log_entry")
    op.drop_index("ix_approval_req_lookup", table_name="tool_approval_request")
    op.drop_index("ix_tool_approval_request_org_id", table_name="tool_approval_request")
    op.drop_table("tool_approval_request")
    op.drop_index("ix_api_key_key_hash", table_name="api_key")
    op.drop_index("ix_api_key_org_id", table_name="api_key")
    op.drop_table("api_key")
    op.drop_index("ix_tool_execution_setting_org_id", table_name="tool_execution_setting")
    op.drop_table("tool_execution_setting")
    op.drop_index("ix_tool_approval_policy_org_id", table_name="tool_approval_policy")
    op.drop_table("tool_approval_policy")
    op.drop_index("ix_tool_cache_org_id", table_name="tool_cache")
    op.drop_table("tool_cache")
    op.drop_index("ix_oauth_state_org_id", table_name="oauth_state")
    op.drop_table("oauth_state")
    op.drop_index("ix_installed_integration_org_id", table_name="installed_integration")
    op.drop_table("installed_integration")
    op.drop_table("org_membership")
    op.drop_index("ix_oauth_auth_request_client_id", table_name="oauth_auth_request")
    op.drop_table("oauth_auth_request")
    op.drop_index("ix_oauth_client_client_id", table_name="oauth_client")
    op.drop_table("oauth_client")
    op.drop_table("oauth_revoked_token")
    op.drop_index("ix_user_email", table_name="user")
    op.drop_table("user")
    op.drop_table("org")
