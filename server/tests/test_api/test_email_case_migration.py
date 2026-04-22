"""Migration regression for finding 01.

Exercises ``0016_case_insensitive_user_email`` against a freshly-created
SQLite database seeded with case-collision fixtures, and asserts the
earliest-wins resolution + lowercasing + uniqueness index swap behaves as
documented in the migration's module docstring.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command

REPO_SERVER = Path(__file__).resolve().parents[2]
ALEMBIC_INI = REPO_SERVER / "alembic.ini"


def _alembic_config(db_url: str) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.fixture(name="migrated_engine")
def migrated_engine_fixture(tmp_path, monkeypatch):
    """Engine whose schema is upgraded to just BEFORE the 0016 migration."""
    from agent_port.config import settings as app_settings

    db_path = tmp_path / "mig.db"
    db_url = f"sqlite:///{db_path}"

    # alembic/env.py reads settings.database_url at migration time, so the
    # app settings singleton needs to point at the test DB for the run.
    monkeypatch.setattr(app_settings, "database_url", db_url)

    # Upgrade to one revision before our change so we can seed raw data
    # that still has mixed-case emails (the 0016 migration is what
    # normalizes them).
    cfg = _alembic_config(db_url)
    command.upgrade(cfg, "0015")

    engine = sa.create_engine(db_url)
    yield engine, cfg, db_url
    engine.dispose()


def _new_id() -> bytes:
    """UUIDs are stored as BLOB in SQLite's sa.Uuid() type."""
    return uuid.uuid4().bytes


def _ts(offset_hours: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=offset_hours)).isoformat(" ")


def _insert_user(conn, *, email: str, created_at: str) -> bytes:
    uid = _new_id()
    conn.execute(
        sa.text(
            'INSERT INTO "user" '
            "(id, email, hashed_password, created_at, is_active, is_admin, "
            "email_verified) "
            "VALUES (:id, :email, :pw, :created, :active, :admin, :verified)"
        ),
        {
            "id": uid,
            "email": email,
            "pw": "hashed",
            "created": created_at,
            "active": True,
            "admin": False,
            "verified": True,
        },
    )
    return uid


def _insert_org(conn, name: str) -> bytes:
    oid = _new_id()
    conn.execute(
        sa.text('INSERT INTO "org" (id, name, created_at) VALUES (:id, :name, :c)'),
        {"id": oid, "name": name, "c": _ts()},
    )
    return oid


def _insert_membership(conn, uid: bytes, oid: bytes, role: str = "owner") -> None:
    conn.execute(
        sa.text('INSERT INTO "org_membership" (user_id, org_id, role) VALUES (:u, :o, :r)'),
        {"u": uid, "o": oid, "r": role},
    )


def test_migration_lowercases_single_rows(migrated_engine):
    engine, cfg, _ = migrated_engine

    with engine.begin() as conn:
        _insert_user(conn, email="FOO4@bar.com", created_at=_ts())
        _insert_user(conn, email="foo3@bar.com", created_at=_ts())

    command.upgrade(cfg, "0016")

    with engine.connect() as conn:
        rows = conn.execute(sa.text('SELECT email FROM "user" ORDER BY email')).all()
    assert [r.email for r in rows] == ["foo3@bar.com", "foo4@bar.com"]


def test_migration_resolves_case_collision_earliest_wins(migrated_engine):
    engine, cfg, _ = migrated_engine

    # Two rows that collide under case-insensitive compare. The lowercase
    # variant was registered first; the uppercase one is the audit-time
    # duplicate that should be deleted.
    with engine.begin() as conn:
        keeper = _insert_user(conn, email="alice@example.com", created_at=_ts(offset_hours=-2))
        loser = _insert_user(conn, email="ALICE@example.com", created_at=_ts(offset_hours=-1))
        keeper_org = _insert_org(conn, "Keeper Org")
        loser_org = _insert_org(conn, "Loser Org")
        _insert_membership(conn, keeper, keeper_org)
        _insert_membership(conn, loser, loser_org)

    command.upgrade(cfg, "0016")

    with engine.connect() as conn:
        users = conn.execute(sa.text('SELECT id, email FROM "user" ORDER BY email')).all()
        assert len(users) == 1
        assert users[0].email == "alice@example.com"
        assert users[0].id == keeper

        # Loser org + membership cleaned up (single-member empty org).
        orgs = conn.execute(sa.text('SELECT id FROM "org"')).all()
        assert {o.id for o in orgs} == {keeper_org}

        memberships = conn.execute(sa.text('SELECT user_id FROM "org_membership"')).all()
        assert [m.user_id for m in memberships] == [keeper]


def test_migration_aborts_when_duplicate_owns_api_key(migrated_engine):
    """The 'fail loudly' branch: if a losing duplicate owns real state, the
    migration must refuse to delete it."""
    engine, cfg, _ = migrated_engine

    with engine.begin() as conn:
        keeper = _insert_user(conn, email="keep@example.com", created_at=_ts(offset_hours=-2))
        loser = _insert_user(conn, email="KEEP@example.com", created_at=_ts(offset_hours=-1))
        keeper_org = _insert_org(conn, "Keeper Org")
        loser_org = _insert_org(conn, "Loser Org")
        _insert_membership(conn, keeper, keeper_org)
        _insert_membership(conn, loser, loser_org)
        # Loser owns an api key -> should trip the safety gate.
        conn.execute(
            sa.text(
                'INSERT INTO "api_key" '
                "(id, org_id, created_by_user_id, name, key_prefix, key_hash, "
                "created_at, is_active) "
                "VALUES (:id, :oid, :uid, :name, :p, :h, :c, :active)"
            ),
            {
                "id": _new_id(),
                "oid": loser_org,
                "uid": loser,
                "name": "dup",
                "p": "ap_xxxxx",
                "h": "h",
                "c": _ts(),
                "active": True,
            },
        )

    with pytest.raises(Exception) as excinfo:
        command.upgrade(cfg, "0016")
    assert "api_key" in str(excinfo.value)


def test_migration_installs_case_insensitive_unique_index(migrated_engine):
    engine, cfg, _ = migrated_engine

    command.upgrade(cfg, "0016")

    # Inserting a case-variant of an existing email must now fail at the
    # DB layer regardless of application logic.
    with engine.begin() as conn:
        _insert_user(conn, email="idx@example.com", created_at=_ts())

    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as conn:
            _insert_user(conn, email="IDX@example.com", created_at=_ts())
