"""migrate any_args policies to tool_execution_settings

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-14

"""

import uuid
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op  # noqa: E402

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Convert any remaining wildcard (any_args) ToolApprovalPolicy rows into
    # ToolExecutionSetting rows so that ToolExecutionSetting is now the single
    # source of truth for auto-approval.
    conn = op.get_bind()
    now = datetime.utcnow()

    rows = conn.execute(
        sa.text(
            "SELECT org_id, integration_name, tool_name FROM tool_approval_policy"
            " WHERE match_type = 'any_args'"
        )
    ).fetchall()

    for row in rows:
        org_id, integration_name, tool_name = row
        # Skip if a setting already exists for this tool (don't overwrite intentional settings).
        existing = conn.execute(
            sa.text(
                "SELECT 1 FROM tool_execution_setting"
                " WHERE org_id = :org_id"
                " AND integration_name = :integration_name"
                " AND tool_name = :tool_name"
            ),
            {"org_id": org_id, "integration_name": integration_name, "tool_name": tool_name},
        ).first()
        if existing:
            continue
        conn.execute(
            sa.text(
                "INSERT INTO tool_execution_setting"
                " (id, org_id, integration_name, tool_name, mode, updated_at)"
                " VALUES (:id, :org_id, :integration_name, :tool_name, 'allow', :updated_at)"
            ),
            {
                "id": str(uuid.uuid4()),
                "org_id": org_id,
                "integration_name": integration_name,
                "tool_name": tool_name,
                "updated_at": now,
            },
        )

    # Remove the now-superseded wildcard policies.
    conn.execute(sa.text("DELETE FROM tool_approval_policy WHERE match_type = 'any_args'"))


def downgrade() -> None:
    # Downgrade is a no-op: we can't safely reconstruct which settings came from
    # policies vs. were set explicitly by users.
    pass
