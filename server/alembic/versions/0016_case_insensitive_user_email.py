"""case-insensitive user email uniqueness

Revision ID: 0016
Revises: 0015
Create Date: 2026-04-21

Background
----------
Historically ``user.email`` was stored verbatim and most auth-path lookups
compared it case-sensitively, while the waitlist lookup normalized to
``email.lower()``. That asymmetry let attackers register case-variant
duplicates (e.g. ``ALICE@example.com`` alongside ``alice@example.com``)
and would misroute password-reset / Google-login by case. This migration
fixes the data and the index.

What this migration does
------------------------
1. Lowercases every existing ``user.email`` and ``waitlist.email``.

2. Resolves case-collisions on ``user.email`` using an **earliest-wins**
   strategy: the row with the oldest ``created_at`` is kept (with its email
   lowercased in place); each later duplicate and its directly-owned
   account scaffolding (``org_membership`` rows and the orgs that *only*
   that user belonged to) is deleted.

   If any duplicate looks non-trivial — i.e. the losing user owns real
   state (api keys, installed integrations, oauth auth codes, tool
   approvals, logs) — the migration aborts with a clear message so an
   operator can reconcile by hand. This protects against silently
   destroying production data on a multi-tenant DB the author hasn't seen.

3. Replaces the plain unique index ``ix_user_email`` with a
   case-insensitive one:
   - SQLite: ``user_email_lower_uq`` on ``LOWER(email)``.
   - PostgreSQL: ``user_email_lower_uq`` on ``LOWER(email)``.

   We chose the functional ``LOWER(email)`` form (portable across both
   dialects) over ``COLLATE NOCASE`` so that behaviour stays identical
   between self-hosted SQLite and the SaaS Postgres deployment without
   any schema-specific column attributes.

This migration is idempotent-safe for already-normalized data: if every
row is already lowercase and unique, step 1 is a no-op and step 2 has
nothing to resolve.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op  # noqa: E402

revision: str = "0016"
down_revision: Union[str, Sequence[str], None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables that reference ``user.id`` and represent "non-trivial owned state".
# If any of these reference a duplicate user row, refuse to auto-delete and
# force the operator to reconcile manually.
_USER_STATE_REFS: tuple[tuple[str, str], ...] = (
    ("api_key", "created_by_user_id"),
    ("tool_execution_setting", "updated_by_user_id"),
    ("tool_approval_request", "requested_by_user_id"),
    ("tool_approval_request", "decided_by_user_id"),
    ("oauth_auth_code", "user_id"),
)

# Tables that reference ``org.id`` — used to decide whether an org that a
# losing duplicate owned can be safely cleaned up (true only if totally
# empty of state).
_ORG_STATE_REFS: tuple[tuple[str, str], ...] = (
    ("installed_integration", "org_id"),
    ("oauth_state", "org_id"),
    ("tool_cache", "org_id"),
    ("tool_execution_setting", "org_id"),
    ("api_key", "org_id"),
    ("tool_approval_request", "org_id"),
    ("log_entry", "org_id"),
    ("oauth_auth_code", "org_id"),
    ("subscription", "org_id"),
)


def _row_count(conn, table: str, column: str, value) -> int:
    result = conn.execute(
        sa.text(f'SELECT COUNT(*) FROM "{table}" WHERE "{column}" = :val'),
        {"val": value},
    ).scalar_one()
    return int(result or 0)


def _resolve_user_email_collisions(conn) -> None:
    """Earliest-wins dedup. See module docstring for full strategy."""
    # Group by lowercased email, count rows, surface groups with >1.
    collisions = conn.execute(
        sa.text(
            "SELECT LOWER(email) AS lowered, COUNT(*) AS n "
            'FROM "user" '
            "GROUP BY LOWER(email) "
            "HAVING COUNT(*) > 1"
        )
    ).all()

    for row in collisions:
        lowered = row.lowered
        # Oldest row wins. Ties broken by id to keep the decision deterministic.
        rows = conn.execute(
            sa.text(
                'SELECT id, email, created_at FROM "user" '
                "WHERE LOWER(email) = :lowered "
                "ORDER BY created_at ASC, id ASC"
            ),
            {"lowered": lowered},
        ).all()

        keeper = rows[0]
        losers = rows[1:]

        # Refuse to auto-delete any loser that owns real state.
        for loser in losers:
            for table, column in _USER_STATE_REFS:
                n = _row_count(conn, table, column, loser.id)
                if n:
                    raise RuntimeError(
                        "Email case-collision resolution aborted: "
                        f"duplicate user {loser.id} (email={loser.email!r}, "
                        f"collides with {keeper.id} email={keeper.email!r}) "
                        f"owns {n} row(s) in {table}.{column}. "
                        "Reconcile these accounts manually, then re-run "
                        "`alembic upgrade head`."
                    )

        # Delete each loser and any single-tenant orgs they owned.
        for loser in losers:
            # Find orgs where this user is a member and check safety.
            memberships = conn.execute(
                sa.text('SELECT org_id FROM "org_membership" WHERE "user_id" = :uid'),
                {"uid": loser.id},
            ).all()
            for m in memberships:
                org_id = m.org_id
                # Is the loser the sole member?
                other_members = conn.execute(
                    sa.text(
                        'SELECT COUNT(*) FROM "org_membership" '
                        'WHERE "org_id" = :oid AND "user_id" <> :uid'
                    ),
                    {"oid": org_id, "uid": loser.id},
                ).scalar_one()
                if int(other_members or 0) > 0:
                    # Multi-member org — only drop the membership; keep the org.
                    conn.execute(
                        sa.text(
                            'DELETE FROM "org_membership" '
                            'WHERE "user_id" = :uid AND "org_id" = :oid'
                        ),
                        {"uid": loser.id, "oid": org_id},
                    )
                    continue

                # Single-member org — ensure it's totally empty of state.
                for table, column in _ORG_STATE_REFS:
                    n = _row_count(conn, table, column, org_id)
                    if n:
                        raise RuntimeError(
                            "Email case-collision resolution aborted: "
                            f"org {org_id} owned solely by duplicate user "
                            f"{loser.id} (email={loser.email!r}) has "
                            f"{n} row(s) in {table}.{column}. "
                            "Reconcile manually."
                        )

                # Safe to drop the membership and the org.
                conn.execute(
                    sa.text(
                        'DELETE FROM "org_membership" WHERE "user_id" = :uid AND "org_id" = :oid'
                    ),
                    {"uid": loser.id, "oid": org_id},
                )
                conn.execute(
                    sa.text('DELETE FROM "org" WHERE "id" = :oid'),
                    {"oid": org_id},
                )

            # Finally, drop the duplicate user row itself.
            conn.execute(
                sa.text('DELETE FROM "user" WHERE "id" = :uid'),
                {"uid": loser.id},
            )


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Resolve collisions BEFORE lowercasing (we need both variants to
    #    identify the loser row on SQLite's case-sensitive compare).
    _resolve_user_email_collisions(conn)

    # 2. Normalize all remaining rows to lowercase + trimmed.
    conn.execute(sa.text('UPDATE "user" SET email = LOWER(TRIM(email))'))
    conn.execute(sa.text('UPDATE "waitlist" SET email = LOWER(TRIM(email))'))

    # 3. Swap the plain unique index for a functional LOWER(email) one.
    #    Works on both SQLite and PostgreSQL. We use raw SQL because
    #    op.create_index() does not portably accept expression indexes.
    op.drop_index("ix_user_email", table_name="user")
    conn.execute(sa.text('CREATE UNIQUE INDEX "user_email_lower_uq" ON "user" (LOWER(email))'))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text('DROP INDEX "user_email_lower_uq"'))
    op.create_index("ix_user_email", "user", ["email"], unique=True)
