import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from agent_port.approvals.normalize import hash_normalized_args, normalize_tool_args
from agent_port.approvals.requests import (
    get_or_create_approval_request,
    try_consume_approved_request,
)
from agent_port.models.org import Org
from agent_port.models.tool_approval_request import ToolApprovalRequest
from agent_port.models.user import User  # noqa: F401


@pytest.fixture(name="db")
def db_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="org_id")
def org_id_fixture(db):
    org = Org(id=uuid.uuid4(), name="test")
    db.add(org)
    db.commit()
    return org.id


def test_creates_new_request(db, org_id):
    req = get_or_create_approval_request(db, org_id, "github", "create_issue", {"title": "hi"})
    assert req.status == "pending"
    assert req.integration_id == "github"
    assert req.tool_name == "create_issue"
    assert req.expires_at > datetime.utcnow()


def test_uses_org_approval_expiry_override(db, org_id):
    org = db.get(Org, org_id)
    org.approval_expiry_minutes = 90
    db.add(org)
    db.commit()

    before = datetime.utcnow()
    req = get_or_create_approval_request(db, org_id, "github", "create_issue", {"title": "hi"})
    delta = req.expires_at - before
    # Allow a small fudge factor for test execution time.
    assert timedelta(minutes=89) <= delta <= timedelta(minutes=91)


def test_falls_back_to_settings_when_no_org_override(db, org_id):
    from agent_port.config import settings

    before = datetime.utcnow()
    req = get_or_create_approval_request(db, org_id, "github", "create_issue", {"title": "hi"})
    delta = req.expires_at - before
    expected = timedelta(minutes=settings.approval_expiry_minutes)
    assert expected - timedelta(seconds=5) <= delta <= expected + timedelta(seconds=5)


def test_reuses_existing_pending_request(db, org_id):
    args = {"title": "hi"}
    req1 = get_or_create_approval_request(db, org_id, "github", "create_issue", args)
    req2 = get_or_create_approval_request(db, org_id, "github", "create_issue", args)
    assert req1.id == req2.id


def test_does_not_reuse_expired_request(db, org_id):
    args = {"title": "hi"}
    normalized = normalize_tool_args(args)
    args_hash = hash_normalized_args(normalized)

    # Create an expired request directly
    expired = ToolApprovalRequest(
        org_id=org_id,
        integration_id="github",
        tool_name="create_issue",
        args_json=normalized,
        args_hash=args_hash,
        summary_text="test",
        status="pending",
        requested_at=datetime.utcnow() - timedelta(hours=48),
        expires_at=datetime.utcnow() - timedelta(hours=1),
    )
    db.add(expired)
    db.commit()
    db.refresh(expired)

    # Should create a new request, not reuse expired one
    req = get_or_create_approval_request(db, org_id, "github", "create_issue", args)
    assert req.id != expired.id
    assert req.status == "pending"


def test_consume_approved_once_request(db, org_id):
    args = {"title": "hi"}
    normalized = normalize_tool_args(args)
    args_hash = hash_normalized_args(normalized)

    req = ToolApprovalRequest(
        org_id=org_id,
        integration_id="github",
        tool_name="create_issue",
        args_json=normalized,
        args_hash=args_hash,
        summary_text="test",
        status="approved",
        decision_mode="approve_once",
        requested_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    db.add(req)
    db.commit()

    consumed = try_consume_approved_request(db, org_id, "github", "create_issue", args_hash)
    assert consumed is not None

    # Refresh to see updated status
    db.refresh(req)
    assert req.status == "consumed"
    assert req.consumed_at is not None


def test_additional_info_stored_on_new_request(db, org_id):
    req = get_or_create_approval_request(
        db,
        org_id,
        "github",
        "create_issue",
        {"title": "hi"},
        additional_info="checking before merging",
    )
    assert req.additional_info == "checking before merging"


def test_additional_info_defaults_to_none(db, org_id):
    req = get_or_create_approval_request(db, org_id, "github", "create_issue", {"title": "hi"})
    assert req.additional_info is None


def test_additional_info_backfilled_when_reusing_pending_request(db, org_id):
    first = get_or_create_approval_request(db, org_id, "github", "create_issue", {"title": "hi"})
    assert first.additional_info is None
    second = get_or_create_approval_request(
        db,
        org_id,
        "github",
        "create_issue",
        {"title": "hi"},
        additional_info="explaining the retry",
    )
    assert first.id == second.id
    assert second.additional_info == "explaining the retry"


def test_cannot_consume_twice(db, org_id):
    args = {"title": "hi"}
    normalized = normalize_tool_args(args)
    args_hash = hash_normalized_args(normalized)

    req = ToolApprovalRequest(
        org_id=org_id,
        integration_id="github",
        tool_name="create_issue",
        args_json=normalized,
        args_hash=args_hash,
        summary_text="test",
        status="approved",
        decision_mode="approve_once",
        requested_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    db.add(req)
    db.commit()

    assert try_consume_approved_request(db, org_id, "github", "create_issue", args_hash)
    assert not try_consume_approved_request(db, org_id, "github", "create_issue", args_hash)
