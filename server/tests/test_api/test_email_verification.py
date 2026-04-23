import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from agent_port.auth_tokens import (
    create_access_token,
    create_email_verification_session_token,
)
from agent_port.db import get_session
from agent_port.main import app
from agent_port.rate_limit import reset_all_rate_limiters


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    reset_all_rate_limiters()
    yield
    reset_all_rate_limiters()


def _seed_code(user, session, code: str = "123456") -> None:
    user.email_verified = False
    user.email_verification_code_hash = hashlib.sha256(code.encode()).hexdigest()
    user.email_verification_code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
    user.email_verification_token_hash = hashlib.sha256(b"link-token").hexdigest()
    user.email_verification_attempts = 0
    session.add(user)
    session.commit()


@pytest.mark.anyio
async def test_verify_email_valid_token(client, test_user, session):
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    test_user.email_verification_token_hash = token_hash
    session.add(test_user)
    session.commit()

    resp = await client.get(f"/api/auth/verify-email?token={token}")
    assert resp.status_code == 200
    assert resp.json()["message"] == "Email verified successfully"
    assert resp.json()["email"] == test_user.email

    session.refresh(test_user)
    assert test_user.email_verified is True
    assert test_user.email_verification_token_hash is None
    assert test_user.email_verification_code_hash is None
    assert test_user.email_verification_code_expires_at is None


@pytest.mark.anyio
async def test_verify_email_invalid_token(client):
    resp = await client.get("/api/auth/verify-email?token=bogus")
    assert resp.status_code == 400
    assert "Invalid" in resp.json()["detail"]


@pytest.mark.anyio
async def test_resend_verification_when_unverified(client, test_user, session, mocker):
    test_user.email_verified = False
    session.add(test_user)
    session.commit()

    mock_send = mocker.patch("agent_port.email.verification.send_email")
    resp = await client.post("/api/auth/resend-verification")
    assert resp.status_code == 200
    assert resp.json()["message"] == "Verification email sent"
    assert resp.json()["resend_available_at"] is not None
    mock_send.assert_called_once()


@pytest.mark.anyio
async def test_resend_verification_when_already_verified(client, test_user, session):
    test_user.email_verified = True
    session.add(test_user)
    session.commit()

    resp = await client.post("/api/auth/resend-verification")
    assert resp.status_code == 200
    assert resp.json()["message"] == "Email is already verified"


@pytest.mark.anyio
async def test_verify_email_code_returns_access_token(client, test_user, session):
    code = "123456"
    test_user.email_verified = False
    test_user.email_verification_code_hash = hashlib.sha256(code.encode()).hexdigest()
    test_user.email_verification_code_expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=30
    )
    test_user.email_verification_token_hash = hashlib.sha256(b"link-token").hexdigest()
    session.add(test_user)
    session.commit()

    verification_token = create_email_verification_session_token(str(test_user.id))
    resp = await client.post(
        "/api/auth/verify-email-code",
        json={"code": code, "verification_token": verification_token},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["message"] == "Email verified successfully"
    assert body["access_token"]
    assert body["token_type"] == "bearer"

    session.refresh(test_user)
    assert test_user.email_verified is True
    assert test_user.email_verification_code_hash is None
    assert test_user.email_verification_token_hash is None


@pytest.mark.anyio
async def test_verify_email_code_accepts_already_verified_user(client, test_user, session):
    test_user.email_verified = True
    session.add(test_user)
    session.commit()

    verification_token = create_email_verification_session_token(str(test_user.id))
    resp = await client.post(
        "/api/auth/verify-email-code",
        json={"code": "", "verification_token": verification_token},
    )

    assert resp.status_code == 200
    assert resp.json()["access_token"]


@pytest.mark.anyio
async def test_resend_verification_is_rate_limited(client, test_user, session, mocker):
    test_user.email_verified = False
    session.add(test_user)
    session.commit()

    mock_send = mocker.patch("agent_port.email.verification.send_email")
    first = await client.post("/api/auth/resend-verification")
    second = await client.post("/api/auth/resend-verification")

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["detail"]["error"] == "verification_email_rate_limited"
    assert second.json()["detail"]["resend_available_at"] is not None
    mock_send.assert_called_once()


@pytest.mark.anyio
async def test_resend_verification_code_uses_verification_session(
    client, test_user, session, mocker
):
    test_user.email_verified = False
    session.add(test_user)
    session.commit()

    mock_send = mocker.patch("agent_port.email.verification.send_email")
    verification_token = create_email_verification_session_token(str(test_user.id))
    resp = await client.post(
        "/api/auth/resend-verification-code",
        json={"verification_token": verification_token},
    )

    assert resp.status_code == 200
    assert resp.json()["message"] == "Verification email sent"
    assert resp.json()["resend_available_at"] is not None
    mock_send.assert_called_once()


@pytest.mark.anyio
async def test_verify_email_code_wrong_code_increments_attempts(client, test_user, session):
    _seed_code(test_user, session, code="123456")
    verification_token = create_email_verification_session_token(str(test_user.id))

    resp = await client.post(
        "/api/auth/verify-email-code",
        json={"code": "000000", "verification_token": verification_token},
    )
    assert resp.status_code == 400
    session.refresh(test_user)
    assert test_user.email_verification_attempts == 1
    assert test_user.email_verification_code_hash is not None


@pytest.mark.anyio
async def test_verify_email_code_burns_after_five_wrong_attempts(client, test_user, session):
    real_code = "123456"
    _seed_code(test_user, session, code=real_code)
    verification_token = create_email_verification_session_token(str(test_user.id))

    for _ in range(5):
        resp = await client.post(
            "/api/auth/verify-email-code",
            json={"code": "000000", "verification_token": verification_token},
        )
        assert resp.status_code == 400

    session.refresh(test_user)
    assert test_user.email_verification_code_hash is None

    # Even the correct code must now fail — the code has been burned.
    resp = await client.post(
        "/api/auth/verify-email-code",
        json={"code": real_code, "verification_token": verification_token},
    )
    assert resp.status_code == 400
    session.refresh(test_user)
    assert test_user.email_verified is False


@pytest.mark.anyio
async def test_verify_email_code_resets_attempts_on_success(client, test_user, session):
    real_code = "123456"
    _seed_code(test_user, session, code=real_code)
    verification_token = create_email_verification_session_token(str(test_user.id))

    # Two wrong attempts → 2
    for _ in range(2):
        await client.post(
            "/api/auth/verify-email-code",
            json={"code": "000000", "verification_token": verification_token},
        )
    session.refresh(test_user)
    assert test_user.email_verification_attempts == 2

    # Correct code → verified, counter reset
    resp = await client.post(
        "/api/auth/verify-email-code",
        json={"code": real_code, "verification_token": verification_token},
    )
    assert resp.status_code == 200
    session.refresh(test_user)
    assert test_user.email_verified is True
    assert test_user.email_verification_attempts == 0


@pytest.mark.anyio
async def test_verify_email_code_returns_generic_error_message(client, test_user, session):
    _seed_code(test_user, session, code="123456")
    verification_token = create_email_verification_session_token(str(test_user.id))

    # Wrong code
    r1 = await client.post(
        "/api/auth/verify-email-code",
        json={"code": "000000", "verification_token": verification_token},
    )
    # Expired code
    test_user.email_verification_code_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    session.add(test_user)
    session.commit()
    r2 = await client.post(
        "/api/auth/verify-email-code",
        json={"code": "000000", "verification_token": verification_token},
    )
    # Burned code (no hash)
    test_user.email_verification_code_hash = None
    test_user.email_verification_code_expires_at = None
    session.add(test_user)
    session.commit()
    r3 = await client.post(
        "/api/auth/verify-email-code",
        json={"code": "000000", "verification_token": verification_token},
    )

    for r in (r1, r2, r3):
        assert r.status_code == 400
        assert r.json()["detail"] == "Invalid or expired verification code"


@pytest.mark.anyio
async def test_send_verification_email_resets_attempts(client, test_user, session, mocker):
    _seed_code(test_user, session, code="123456")
    test_user.email_verification_attempts = 3
    # Clear sent_at so cooldown does not block the resend.
    test_user.email_verification_sent_at = None
    session.add(test_user)
    session.commit()

    mocker.patch("agent_port.email.verification.send_email")
    resp = await client.post("/api/auth/resend-verification")
    assert resp.status_code == 200

    session.refresh(test_user)
    assert test_user.email_verification_attempts == 0


@pytest.mark.anyio
async def test_resend_after_burn_bypasses_cooldown(client, test_user, session, mocker):
    # Burned state: unverified, no code hash, but sent_at is within the cooldown window.
    test_user.email_verified = False
    test_user.email_verification_code_hash = None
    test_user.email_verification_code_expires_at = None
    test_user.email_verification_sent_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    test_user.email_verification_attempts = 5
    session.add(test_user)
    session.commit()

    mock_send = mocker.patch("agent_port.email.verification.send_email")
    verification_token = create_email_verification_session_token(str(test_user.id))
    resp = await client.post(
        "/api/auth/resend-verification-code",
        json={"verification_token": verification_token},
    )
    assert resp.status_code == 200
    mock_send.assert_called_once()
    session.refresh(test_user)
    assert test_user.email_verification_code_hash is not None
    assert test_user.email_verification_attempts == 0


@pytest.mark.anyio
async def test_verify_email_code_is_rate_limited_per_ip(client, test_user, session):
    _seed_code(test_user, session, code="123456")
    verification_token = create_email_verification_session_token(str(test_user.id))

    seen_429 = False
    for _ in range(30):
        resp = await client.post(
            "/api/auth/verify-email-code",
            json={"code": "111111", "verification_token": verification_token},
        )
        if resp.status_code == 429:
            seen_429 = True
            break
    assert seen_429, "expected /verify-email-code to return 429 once the per-IP cap trips"


@pytest.mark.anyio
async def test_verify_email_token_is_rate_limited_per_ip(client):
    seen_429 = False
    for _ in range(30):
        resp = await client.get("/api/auth/verify-email?token=does-not-exist")
        if resp.status_code == 429:
            seen_429 = True
            break
    assert seen_429, "expected /verify-email to return 429 once the per-IP cap trips"


@pytest.mark.anyio
async def test_thousand_wrong_guesses_are_blocked(client, test_user, session):
    """Regression guard: an attacker cannot submit many wrong codes per token —
    either the code gets burned or the IP gets rate-limited long before 1,000."""
    _seed_code(test_user, session, code="123456")
    verification_token = create_email_verification_session_token(str(test_user.id))

    accepted_attempts = 0
    for _ in range(1000):
        resp = await client.post(
            "/api/auth/verify-email-code",
            json={"code": "000000", "verification_token": verification_token},
        )
        if resp.status_code == 400:
            accepted_attempts += 1
        else:
            break

    # Either the code burned (counter cap) or rate-limiter fired — in both cases
    # we should never have accepted anywhere near 1,000 wrong codes.
    assert accepted_attempts < 50


# ─── 07: verification-session tokens must not authenticate REST ──────────────


@pytest.mark.anyio
async def test_email_verification_token_rejected_as_rest_bearer(session, test_user, test_org):
    """The short-lived handle returned from /register must not unlock
    generic authenticated endpoints — its only purpose is submitting the
    6-digit code on /verify-email-code."""
    token = create_email_verification_session_token(str(test_user.id))

    def override_session():
        yield session

    app.dependency_overrides.clear()
    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as raw:
        resp = await raw.get("/api/users/me")
        assert resp.status_code == 401


@pytest.mark.anyio
async def test_normal_access_token_still_authenticates_rest(session, test_user, test_org):
    """Compatibility guard: tightening the REST decoder must not break the
    login-issued access token."""
    token = create_access_token(str(test_user.id))

    def override_session():
        yield session

    app.dependency_overrides.clear()
    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as raw:
        resp = await raw.get("/api/users/me")
        assert resp.status_code == 200
        assert resp.json()["email"] == test_user.email
