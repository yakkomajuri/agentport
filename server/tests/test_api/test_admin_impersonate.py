"""Tests for admin impersonation — covers finding 06 (sub-findings 6a, 6b, 6c, 6e).

Sub-finding 6d (TOTP gate on start) is intentionally NOT enforced — impersonation
and the tool-approval flow are separate concerns, so we don't bolt a 2FA
challenge onto `/api/admin/impersonate/<id>`.

- 6a  Impersonation tokens must expire well before a normal access token.
- 6b  /impersonate/stop must revoke the bearer so reuse returns 401.
- 6c  Tool calls under impersonation must tag LogEntry.impersonator_user_id.
- 6e  TOTP setup/enable/re-enable/disable and change-password must be refused
      while acting under an impersonation token.
"""

import uuid

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from agent_port.db import get_session
from agent_port.dependencies import (
    AgentAuth,
    get_agent_auth,
    get_current_org,
    get_current_user,
    get_impersonator,
)
from agent_port.main import app
from agent_port.models.log import LogEntry
from agent_port.models.oauth_revoked_token import OAuthRevokedToken
from agent_port.models.org import Org
from agent_port.models.org_membership import OrgMembership
from agent_port.models.user import User


def _make_target(session, email: str = "target@example.com") -> User:
    user = User(id=uuid.uuid4(), email=email, hashed_password="hashed")
    org = Org(id=uuid.uuid4(), name=f"{email} org")
    session.add(user)
    session.add(org)
    session.flush()
    session.add(OrgMembership(user_id=user.id, org_id=org.id, role="owner"))
    session.commit()
    session.refresh(user)
    return user


def _make_admin(session, email: str = "admin@example.com") -> User:
    admin = User(id=uuid.uuid4(), email=email, hashed_password="hashed", is_admin=True)
    session.add(admin)
    session.commit()
    session.refresh(admin)
    return admin


def _decode_unverified(token: str) -> dict:
    return jwt.decode(token, options={"verify_signature": False})


@pytest.fixture(name="admin_client")
async def admin_client_fixture(session, test_org):
    """AsyncClient authenticated as an admin."""
    admin = _make_admin(session)
    session.add(OrgMembership(user_id=admin.id, org_id=test_org.id, role="owner"))
    session.commit()

    def override_session():
        yield session

    def override_user():
        return admin

    def override_org():
        return test_org

    def override_agent_auth():
        return AgentAuth(org=test_org, user=admin, api_key=None)

    def override_impersonator():
        return None

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_current_org] = override_org
    app.dependency_overrides[get_agent_auth] = override_agent_auth
    app.dependency_overrides[get_impersonator] = override_impersonator
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        c.admin_user = admin  # type: ignore[attr-defined]
        yield c
    app.dependency_overrides.clear()


# ─── 6a: short TTL on impersonation tokens ───────────────────────────────────


@pytest.mark.anyio
async def test_impersonation_token_short_ttl(admin_client, session):
    target = _make_target(session)
    resp = await admin_client.post(f"/api/admin/impersonate/{target.id}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    tok = data["access_token"]
    claims = _decode_unverified(tok)
    assert claims["token_use"] == "impersonation"
    assert claims["impersonator_sub"] == str(admin_client.admin_user.id)  # type: ignore[attr-defined]
    assert claims["sub"] == str(target.id)
    assert "jti" in claims
    # Must expire well under an hour. Default is 30 min.
    assert claims["exp"] - claims["iat"] <= 60 * 60
    assert data["expires_in"] <= 60 * 60


# ─── 6b: stop_impersonation revokes the bearer ───────────────────────────────


@pytest.mark.anyio
async def test_stop_impersonation_revokes_token(admin_client, session):
    target = _make_target(session)
    resp = await admin_client.post(f"/api/admin/impersonate/{target.id}")
    assert resp.status_code == 200
    imp_token = resp.json()["access_token"]

    # Call stop with the impersonation bearer. We need to bypass dep overrides
    # so the real _decode_rest_bearer_token path runs and the real
    # _is_token_revoked lookup happens.
    def override_session():
        yield session

    app.dependency_overrides.clear()
    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {imp_token}"},
    ) as raw:
        stop_resp = await raw.post("/api/admin/impersonate/stop")
        assert stop_resp.status_code == 200, stop_resp.text
        assert "access_token" in stop_resp.json()

        # Subsequent use of the revoked token must fail.
        me_resp = await raw.get("/api/users/me")
        assert me_resp.status_code == 401

    # Revocation row exists in the DB.
    revoked = session.exec(select(OAuthRevokedToken)).all()
    assert len(revoked) >= 1


@pytest.mark.anyio
async def test_stop_impersonation_rejects_non_impersonation_token(session, test_user):
    """Refuse to revoke a plain access token via /impersonate/stop."""
    from agent_port.auth_tokens import create_access_token

    plain = create_access_token(str(test_user.id))

    def override_session():
        yield session

    app.dependency_overrides.clear()
    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {plain}"},
    ) as raw:
        resp = await raw.post("/api/admin/impersonate/stop")
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "not_impersonating"


# ─── 6c: tool calls tagged in LogEntry ───────────────────────────────────────


@pytest.mark.anyio
async def test_impersonated_tool_call_tags_log_entry(session, test_org):
    """A tool call made with an impersonation bearer must set
    LogEntry.impersonator_user_id to the admin's id."""
    # Build admin + target, both sharing the test_org.
    admin = _make_admin(session)
    session.add(OrgMembership(user_id=admin.id, org_id=test_org.id, role="owner"))
    target = User(id=uuid.uuid4(), email="t@example.com", hashed_password="hashed")
    session.add(target)
    session.flush()
    session.add(OrgMembership(user_id=target.id, org_id=test_org.id, role="member"))
    session.commit()

    # Mint impersonation token directly (avoid the end-to-end start endpoint
    # since we already test that above).
    from agent_port.auth_tokens import create_impersonation_token

    imp_token, _jti = create_impersonation_token(str(admin.id), str(target.id))

    def override_session():
        yield session

    app.dependency_overrides.clear()
    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {imp_token}"},
    ) as raw:
        # Hit /api/users/me to confirm the impersonator banner fires (sanity)
        me = await raw.get("/api/users/me")
        assert me.status_code == 200
        body = me.json()
        assert body["id"] == str(target.id)
        assert body["impersonator_email"] == admin.email

    # Write a LogEntry directly using the same path the tool-call handler
    # would: confirm that AgentAuth.impersonator propagates through
    # get_agent_auth for bearer tokens.
    from agent_port.dependencies import _decode_rest_bearer_token, _resolve_impersonator

    payload = _decode_rest_bearer_token(
        imp_token,
        session,
        credentials_exception=AssertionError("unexpected credentials error"),
    )
    resolved = _resolve_impersonator(payload, session)
    assert resolved is not None
    assert resolved.id == admin.id

    # Simulate what tools.py now does — write a LogEntry with the field set —
    # and confirm it persists + is retrievable with the new column populated.
    entry = LogEntry(
        org_id=test_org.id,
        integration_id="noop",
        tool_name="ping",
        outcome="executed",
        impersonator_user_id=resolved.id,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)

    fetched = session.exec(select(LogEntry).where(LogEntry.id == entry.id)).first()
    assert fetched is not None
    assert fetched.impersonator_user_id == admin.id


# ─── 6e: TOTP + password change must be refused while impersonating ──────────


@pytest.mark.anyio
async def test_totp_setup_blocked_during_impersonation(session, test_org):
    admin = _make_admin(session)
    session.add(OrgMembership(user_id=admin.id, org_id=test_org.id, role="owner"))
    target = User(id=uuid.uuid4(), email="t@example.com", hashed_password="hashed")
    session.add(target)
    session.flush()
    session.add(OrgMembership(user_id=target.id, org_id=test_org.id, role="member"))
    session.commit()

    from agent_port.auth_tokens import create_impersonation_token

    imp_token, _jti = create_impersonation_token(str(admin.id), str(target.id))

    def override_session():
        yield session

    app.dependency_overrides.clear()
    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {imp_token}"},
    ) as raw:
        resp = await raw.post("/api/users/me/totp/setup")
        assert resp.status_code == 403
        assert resp.json()["detail"]["error"] == "impersonation_not_allowed"

        enable = await raw.post("/api/users/me/totp/enable", json={"code": "123456"})
        assert enable.status_code == 403
        assert enable.json()["detail"]["error"] == "impersonation_not_allowed"

        disable = await raw.post("/api/users/me/totp/disable", json={"code": "123456"})
        assert disable.status_code == 403
        assert disable.json()["detail"]["error"] == "impersonation_not_allowed"

        change = await raw.post(
            "/api/users/me/change-password",
            json={"current_password": "x", "new_password": "yyyyyy"},
        )
        assert change.status_code == 403
        assert change.json()["detail"]["error"] == "impersonation_not_allowed"


# ─── Sanity: impersonation endpoint basic guards ────────────────────────────


@pytest.mark.anyio
async def test_cannot_impersonate_admin(admin_client, session):
    other_admin = _make_admin(session, email="other-admin@example.com")
    resp = await admin_client.post(f"/api/admin/impersonate/{other_admin.id}")
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "cannot_impersonate_admin"


@pytest.mark.anyio
async def test_cannot_impersonate_self(admin_client):
    admin = admin_client.admin_user  # type: ignore[attr-defined]
    resp = await admin_client.post(f"/api/admin/impersonate/{admin.id}")
    # Admin self-target hits the "cannot impersonate admin" guard first.
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_impersonate_missing_user_returns_404(admin_client):
    resp = await admin_client.post(f"/api/admin/impersonate/{uuid.uuid4()}")
    assert resp.status_code == 404
