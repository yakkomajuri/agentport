import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import pytest

from agent_port.security import hash_password, verify_password


@pytest.mark.anyio
async def test_forgot_password_sends_email(client, test_user, session, mocker):
    test_user.hashed_password = hash_password("mypassword")
    session.add(test_user)
    session.commit()

    mock_send = mocker.patch("agent_port.api.password_reset.send_email")
    resp = await client.post(
        "/api/auth/forgot-password",
        json={"email": test_user.email},
    )
    assert resp.status_code == 200
    mock_send.assert_called_once()

    session.refresh(test_user)
    assert test_user.password_reset_token_hash is not None
    assert test_user.password_reset_expires_at is not None


@pytest.mark.anyio
async def test_forgot_password_unknown_email_still_200(client, mocker):
    mock_send = mocker.patch("agent_port.api.password_reset.send_email")
    resp = await client.post(
        "/api/auth/forgot-password",
        json={"email": "nonexistent@example.com"},
    )
    assert resp.status_code == 200
    mock_send.assert_not_called()


@pytest.mark.anyio
async def test_reset_password_valid_token(client, test_user, session):
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    test_user.hashed_password = hash_password("oldpassword")
    test_user.password_reset_token_hash = token_hash
    test_user.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    session.add(test_user)
    session.commit()

    resp = await client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "brandnew123"},
    )
    assert resp.status_code == 200

    session.refresh(test_user)
    assert verify_password("brandnew123", test_user.hashed_password)
    assert test_user.password_reset_token_hash is None
    assert test_user.password_reset_expires_at is None


@pytest.mark.anyio
async def test_reset_password_invalid_token(client):
    resp = await client.post(
        "/api/auth/reset-password",
        json={"token": "bogus", "new_password": "newpass123"},
    )
    assert resp.status_code == 400
    assert "Invalid" in resp.json()["detail"]


@pytest.mark.anyio
async def test_reset_password_expired_token(client, test_user, session):
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    test_user.password_reset_token_hash = token_hash
    test_user.password_reset_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    session.add(test_user)
    session.commit()

    resp = await client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "newpass123"},
    )
    assert resp.status_code == 400
    assert "expired" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_reset_password_too_short(client):
    resp = await client.post(
        "/api/auth/reset-password",
        json={"token": "anything", "new_password": "short"},
    )
    assert resp.status_code == 400
    assert "6 characters" in resp.json()["detail"]
