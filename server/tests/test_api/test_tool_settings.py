import json
from datetime import datetime

import pyotp
import pytest

from agent_port.models.tool_execution import ToolExecutionSetting
from agent_port.totp import generate_recovery_codes, hash_recovery_codes


def _enable_totp(test_user, session) -> str:
    secret = pyotp.random_base32()
    test_user.totp_secret = secret
    test_user.totp_enabled = True
    test_user.totp_confirmed_at = datetime.utcnow()
    session.add(test_user)
    session.commit()
    return secret


def _seed_setting(session, test_org, tool_name: str, mode: str) -> None:
    session.add(
        ToolExecutionSetting(
            org_id=test_org.id,
            integration_id="github",
            tool_name=tool_name,
            mode=mode,
            updated_at=datetime.utcnow(),
        )
    )
    session.commit()


@pytest.mark.anyio
async def test_list_settings_empty(client):
    resp = await client.get("/api/tool-settings/github")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_set_and_list_settings(client):
    resp = await client.put(
        "/api/tool-settings/github/create_issue",
        json={"mode": "allow"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "allow"
    assert data["integration_id"] == "github"
    assert data["tool_name"] == "create_issue"

    resp = await client.get("/api/tool-settings/github")
    assert resp.status_code == 200
    settings = resp.json()
    assert len(settings) == 1
    assert settings[0]["mode"] == "allow"


@pytest.mark.anyio
async def test_update_existing_setting(client):
    await client.put(
        "/api/tool-settings/github/create_issue",
        json={"mode": "allow"},
    )
    resp = await client.put(
        "/api/tool-settings/github/create_issue",
        json={"mode": "require_approval"},
    )
    assert resp.status_code == 200
    assert resp.json()["mode"] == "require_approval"


@pytest.mark.anyio
async def test_invalid_mode_rejected(client):
    resp = await client.put(
        "/api/tool-settings/github/create_issue",
        json={"mode": "invalid"},
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_list_approval_requests(client):
    resp = await client.get("/api/tool-approvals/requests")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_get_nonexistent_request(client):
    import uuid

    resp = await client.get(f"/api/tool-approvals/requests/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_allow_from_default_requires_totp_when_enabled(client, session, test_user):
    _enable_totp(test_user, session)
    resp = await client.put(
        "/api/tool-settings/github/create_issue",
        json={"mode": "allow"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "totp_required"


@pytest.mark.anyio
async def test_allow_from_deny_requires_totp_when_enabled(client, session, test_user, test_org):
    _enable_totp(test_user, session)
    _seed_setting(session, test_org, "create_issue", "deny")
    resp = await client.put(
        "/api/tool-settings/github/create_issue",
        json={"mode": "allow"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "totp_required"


@pytest.mark.anyio
async def test_allow_with_invalid_totp_rejected(client, session, test_user):
    _enable_totp(test_user, session)
    resp = await client.put(
        "/api/tool-settings/github/create_issue",
        json={"mode": "allow", "totp_code": "000000"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "totp_invalid"


@pytest.mark.anyio
async def test_allow_with_valid_totp_succeeds(client, session, test_user):
    secret = _enable_totp(test_user, session)
    resp = await client.put(
        "/api/tool-settings/github/create_issue",
        json={"mode": "allow", "totp_code": pyotp.TOTP(secret).now()},
    )
    assert resp.status_code == 200
    assert resp.json()["mode"] == "allow"


@pytest.mark.anyio
async def test_allow_to_deny_does_not_require_totp(client, session, test_user, test_org):
    _enable_totp(test_user, session)
    _seed_setting(session, test_org, "create_issue", "allow")
    resp = await client.put(
        "/api/tool-settings/github/create_issue",
        json={"mode": "deny"},
    )
    assert resp.status_code == 200
    assert resp.json()["mode"] == "deny"


@pytest.mark.anyio
async def test_deny_to_require_approval_does_not_require_totp(client, session, test_user, test_org):
    _enable_totp(test_user, session)
    _seed_setting(session, test_org, "create_issue", "deny")
    resp = await client.put(
        "/api/tool-settings/github/create_issue",
        json={"mode": "require_approval"},
    )
    assert resp.status_code == 200
    assert resp.json()["mode"] == "require_approval"


@pytest.mark.anyio
async def test_allow_to_allow_does_not_require_totp(client, session, test_user, test_org):
    _enable_totp(test_user, session)
    _seed_setting(session, test_org, "create_issue", "allow")
    resp = await client.put(
        "/api/tool-settings/github/create_issue",
        json={"mode": "allow"},
    )
    assert resp.status_code == 200
    assert resp.json()["mode"] == "allow"


@pytest.mark.anyio
async def test_user_without_totp_can_allow_without_code(client, session, test_user):
    # test_user starts with totp_enabled=False
    resp = await client.put(
        "/api/tool-settings/github/create_issue",
        json={"mode": "allow"},
    )
    assert resp.status_code == 200
    assert resp.json()["mode"] == "allow"


@pytest.mark.anyio
async def test_allow_with_recovery_code_burns_code(client, session, test_user):
    _enable_totp(test_user, session)
    codes = generate_recovery_codes()
    test_user.totp_recovery_codes_hash_json = hash_recovery_codes(codes)
    session.add(test_user)
    session.commit()

    resp = await client.put(
        "/api/tool-settings/github/create_issue",
        json={"mode": "allow", "totp_code": codes[0]},
    )
    assert resp.status_code == 200

    session.refresh(test_user)
    remaining = json.loads(test_user.totp_recovery_codes_hash_json)
    assert len(remaining) == len(codes) - 1

    # Reusing the burned code on another tool must fail.
    resp = await client.put(
        "/api/tool-settings/github/another_tool",
        json={"mode": "allow", "totp_code": codes[0]},
    )
    assert resp.status_code == 403
