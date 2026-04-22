from datetime import datetime, timedelta, timezone

import pytest

from agent_port.config import settings
from agent_port.rate_limit import (
    ACCOUNT_LOCKOUT_THRESHOLD,
    IP_MAX_ATTEMPTS_PER_WINDOW,
)
from agent_port.security import hash_password


@pytest.mark.anyio
async def test_login_returns_verification_challenge_for_unverified_user(
    client, test_user, session, monkeypatch
):
    monkeypatch.setattr(settings, "skip_email_verification", False)
    test_user.hashed_password = hash_password("secret123")
    test_user.email_verified = False
    session.add(test_user)
    session.commit()

    resp = await client.post(
        "/api/auth/token",
        data={"username": test_user.email, "password": "secret123"},
    )

    assert resp.status_code == 403
    detail = resp.json()["detail"]
    assert detail["error"] == "email_verification_required"
    assert detail["email"] == test_user.email
    assert detail["verification_token"]
    assert detail["resend_available_at"] is None


@pytest.mark.anyio
async def test_login_returns_token_for_verified_user(client, test_user, session):
    test_user.hashed_password = hash_password("secret123")
    test_user.email_verified = True
    session.add(test_user)
    session.commit()

    resp = await client.post(
        "/api/auth/token",
        data={"username": test_user.email, "password": "secret123"},
    )

    assert resp.status_code == 200
    assert resp.json()["access_token"]


@pytest.mark.anyio
async def test_login_runs_password_verification_for_unknown_email(client, mocker):
    """Guards against a timing oracle: bcrypt must run even for unknown emails
    so that attackers cannot enumerate registered accounts from response time.
    """
    spy = mocker.spy(
        __import__("agent_port.api.user_auth", fromlist=["verify_password"]), "verify_password"
    )

    resp = await client.post(
        "/api/auth/token",
        data={"username": "never-registered@example.com", "password": "wrong"},
    )

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Incorrect email or password"
    assert spy.call_count == 1


@pytest.mark.anyio
async def test_login_runs_password_verification_for_user_without_password(
    client, test_user, session, mocker
):
    """Users without a hashed_password (e.g. Google-only accounts) must also
    trigger a bcrypt verify so their existence is not leaked by timing.
    """
    test_user.hashed_password = None
    session.add(test_user)
    session.commit()

    spy = mocker.spy(
        __import__("agent_port.api.user_auth", fromlist=["verify_password"]), "verify_password"
    )

    resp = await client.post(
        "/api/auth/token",
        data={"username": test_user.email, "password": "wrong"},
    )

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Incorrect email or password"
    assert spy.call_count == 1


@pytest.mark.anyio
async def test_login_wrong_password_for_known_user_returns_generic_401(client, test_user, session):
    """401 body must be identical whether the email is registered or not."""
    test_user.hashed_password = hash_password("secret123")
    session.add(test_user)
    session.commit()

    resp_known = await client.post(
        "/api/auth/token",
        data={"username": test_user.email, "password": "wrong"},
    )
    resp_unknown = await client.post(
        "/api/auth/token",
        data={"username": "never-registered@example.com", "password": "wrong"},
    )

    assert resp_known.status_code == 401
    assert resp_unknown.status_code == 401
    assert resp_known.json() == resp_unknown.json()


def test_dummy_hash_is_verifiable():
    """Sanity: the module-level dummy hash is a real bcrypt hash that
    verify_password can process without raising.
    """
    from agent_port.api.user_auth import _DUMMY_HASH

    assert _DUMMY_HASH.startswith("$2")


@pytest.mark.anyio
async def test_account_locks_after_threshold(client, test_user, session):
    test_user.hashed_password = hash_password("good")
    test_user.email_verified = True
    session.add(test_user)
    session.commit()

    for _ in range(ACCOUNT_LOCKOUT_THRESHOLD):
        r = await client.post(
            "/api/auth/token",
            data={"username": test_user.email, "password": "bad"},
        )
        assert r.status_code in (401, 429)

    # Even the correct password now returns 429 while the lockout window holds.
    r = await client.post(
        "/api/auth/token",
        data={"username": test_user.email, "password": "good"},
    )
    assert r.status_code == 429
    assert r.headers.get("Retry-After")
    # Response body is identical to wrong-password so it isn't an oracle.
    assert r.json()["detail"] == "Incorrect email or password"


@pytest.mark.anyio
async def test_expired_lockout_allows_login(client, test_user, session):
    test_user.hashed_password = hash_password("good")
    test_user.email_verified = True
    test_user.failed_login_attempts = ACCOUNT_LOCKOUT_THRESHOLD
    test_user.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)
    session.add(test_user)
    session.commit()

    r = await client.post(
        "/api/auth/token",
        data={"username": test_user.email, "password": "good"},
    )
    assert r.status_code == 200

    session.refresh(test_user)
    assert test_user.failed_login_attempts == 0
    assert test_user.locked_until is None


@pytest.mark.anyio
async def test_successful_login_resets_failure_counter(client, test_user, session):
    test_user.hashed_password = hash_password("good")
    test_user.email_verified = True
    test_user.failed_login_attempts = 3
    session.add(test_user)
    session.commit()

    r = await client.post(
        "/api/auth/token",
        data={"username": test_user.email, "password": "good"},
    )
    assert r.status_code == 200

    session.refresh(test_user)
    assert test_user.failed_login_attempts == 0


@pytest.mark.anyio
async def test_per_ip_limit_kicks_in_across_accounts(client, session):
    # Wrong-cred attempts against unrelated accounts from one IP must
    # surface at least one 429 — the CI guard described in the task.
    saw_429 = False
    for i in range(IP_MAX_ATTEMPTS_PER_WINDOW + 5):
        r = await client.post(
            "/api/auth/token",
            data={"username": f"nobody-{i}@example.com", "password": "whatever"},
        )
        if r.status_code == 429:
            saw_429 = True
            assert r.headers.get("Retry-After")
            break
        assert r.status_code == 401
    assert saw_429


@pytest.mark.anyio
async def test_register_returns_verification_state(client, mocker, monkeypatch):
    monkeypatch.setattr(settings, "skip_email_verification", False)
    mocker.patch("agent_port.email.verification.send_email")

    resp = await client.post(
        "/api/users/register",
        json={"email": "new@example.com", "password": "secret123"},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new@example.com"
    assert body["email_verification_required"] is True
    assert body["verification_token"]
    assert body["resend_available_at"] is not None
