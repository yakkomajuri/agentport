import json
from datetime import datetime, timedelta

import pyotp
import pytest

from agent_port.models.tool_approval_request import ToolApprovalRequest
from agent_port.totp import generate_recovery_codes, hash_recovery_codes


def _make_pending(session, test_org) -> ToolApprovalRequest:
    """Create a ToolApprovalRequest without going through the tool-call path
    (that path depends on the full migration stack which tests don't run)."""
    req = ToolApprovalRequest(
        org_id=test_org.id,
        integration_id="posthog",
        tool_name="create_annotation",
        args_json="{}",
        args_hash="h",
        summary_text="test",
        status="pending",
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    session.add(req)
    session.commit()
    session.refresh(req)
    return req


def _enable_totp(test_user, session) -> str:
    secret = pyotp.random_base32()
    test_user.totp_secret = secret
    test_user.totp_enabled = True
    test_user.totp_confirmed_at = datetime.utcnow()
    session.add(test_user)
    session.commit()
    return secret


@pytest.mark.anyio
async def test_approve_rejected_without_totp_when_required(client, session, test_user, test_org):
    req = _make_pending(session, test_org)
    _enable_totp(test_user, session)

    resp = await client.post(
        f"/api/tool-approvals/requests/{req.id}/approve-once",
        json={},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "totp_required"


@pytest.mark.anyio
async def test_approve_rejected_with_wrong_totp(client, session, test_user, test_org):
    req = _make_pending(session, test_org)
    _enable_totp(test_user, session)

    resp = await client.post(
        f"/api/tool-approvals/requests/{req.id}/approve-once",
        json={"totp_code": "000000"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "totp_invalid"


@pytest.mark.anyio
async def test_approve_passes_with_valid_totp(client, session, test_user, test_org):
    req = _make_pending(session, test_org)
    secret = _enable_totp(test_user, session)

    resp = await client.post(
        f"/api/tool-approvals/requests/{req.id}/approve-once",
        json={"totp_code": pyotp.TOTP(secret).now()},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


@pytest.mark.anyio
async def test_recovery_code_burns_after_use(client, session, test_user, test_org):
    req1 = _make_pending(session, test_org)
    _enable_totp(test_user, session)

    codes = generate_recovery_codes()
    test_user.totp_recovery_codes_hash_json = hash_recovery_codes(codes)
    session.add(test_user)
    session.commit()

    recovery = codes[0]
    resp = await client.post(
        f"/api/tool-approvals/requests/{req1.id}/approve-once",
        json={"totp_code": recovery},
    )
    assert resp.status_code == 200

    session.refresh(test_user)
    remaining = json.loads(test_user.totp_recovery_codes_hash_json)
    assert len(remaining) == len(codes) - 1

    # A different pending request should not accept the same burned code.
    req2 = _make_pending(session, test_org)
    resp = await client.post(
        f"/api/tool-approvals/requests/{req2.id}/approve-once",
        json={"totp_code": recovery},
    )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_approve_when_totp_disabled_does_not_require_code(
    client, session, test_user, test_org
):
    req = _make_pending(session, test_org)
    resp = await client.post(
        f"/api/tool-approvals/requests/{req.id}/approve-once",
        json={},
    )
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_allow_tool_and_deny_gated_on_totp(client, session, test_user, test_org):
    secret = _enable_totp(test_user, session)

    r1 = _make_pending(session, test_org)
    resp = await client.post(
        f"/api/tool-approvals/requests/{r1.id}/allow-tool",
        json={},
    )
    assert resp.status_code == 403
    resp = await client.post(
        f"/api/tool-approvals/requests/{r1.id}/allow-tool",
        json={"totp_code": pyotp.TOTP(secret).now()},
    )
    assert resp.status_code == 200

    r2 = _make_pending(session, test_org)
    resp = await client.post(
        f"/api/tool-approvals/requests/{r2.id}/deny",
        json={},
    )
    assert resp.status_code == 403
    resp = await client.post(
        f"/api/tool-approvals/requests/{r2.id}/deny",
        json={"totp_code": pyotp.TOTP(secret).now()},
    )
    assert resp.status_code == 200
