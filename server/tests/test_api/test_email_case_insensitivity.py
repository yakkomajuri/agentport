"""Regression tests for security finding 01 - duplicate accounts via email
case-sensitivity mismatch.

Every auth-path lookup must treat ``user.email`` as case-insensitive, and
new rows must be stored in the canonical lowercase + stripped form.
"""

from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from agent_port.api.google_login import _find_or_create_user
from agent_port.config import settings
from agent_port.db import get_session
from agent_port.main import app
from agent_port.models.user import User
from agent_port.security import hash_password


def _select_users(session):
    return session.exec(select(User)).all()


def _find_user(session, email: str):
    return session.exec(select(User).where(User.email == email)).first()


@pytest.fixture(name="unauth_client")
async def unauth_client_fixture(monkeypatch, mocker):
    """Public (unauthenticated) client against a fresh in-memory DB.

    The default `client` fixture in conftest.py overrides get_current_user
    to a pre-created test_user, which doesn't fit register/login flows.
    """
    monkeypatch.setattr(settings, "skip_email_verification", True)
    monkeypatch.setattr(settings, "block_signups", False)
    monkeypatch.setattr(settings, "is_self_hosted", False)

    # Silence outbound email during registration/password-reset flows.
    mocker.patch("agent_port.email.verification.send_email")
    mocker.patch("agent_port.api.password_reset.send_email")

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    session = Session(engine)

    def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, session

    app.dependency_overrides.clear()
    session.close()


@pytest.mark.anyio
async def test_register_stores_email_lowercased(unauth_client):
    client, session = unauth_client

    resp = await client.post(
        "/api/users/register",
        json={"email": "Mixed.Case@Example.COM  ", "password": "Pass12345!"},
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "mixed.case@example.com"

    users = _select_users(session)
    assert len(users) == 1
    assert users[0].email == "mixed.case@example.com"


@pytest.mark.anyio
async def test_register_rejects_case_variant_duplicate(unauth_client):
    client, session = unauth_client

    first = await client.post(
        "/api/users/register",
        json={"email": "dup@example.com", "password": "Pass12345!"},
    )
    assert first.status_code == 201

    dup = await client.post(
        "/api/users/register",
        json={"email": "DUP@EXAMPLE.COM", "password": "Pass12345!"},
    )
    assert dup.status_code == 409
    assert dup.json()["detail"] == "Email already registered"

    users = _select_users(session)
    assert len(users) == 1


@pytest.mark.anyio
async def test_login_accepts_any_case(unauth_client):
    client, _ = unauth_client

    reg = await client.post(
        "/api/users/register",
        json={"email": "login@example.com", "password": "Pass12345!"},
    )
    assert reg.status_code == 201

    # Varying the case of the registered email must still log in.
    for variant in ("login@example.com", "LOGIN@example.com", "Login@Example.COM"):
        resp = await client.post(
            "/api/auth/token",
            data={"username": variant, "password": "Pass12345!"},
        )
        assert resp.status_code == 200, f"variant={variant!r}"
        assert resp.json()["access_token"]


@pytest.mark.anyio
async def test_forgot_password_finds_account_regardless_of_case(unauth_client):
    client, session = unauth_client

    reg = await client.post(
        "/api/users/register",
        json={"email": "reset@example.com", "password": "Pass12345!"},
    )
    assert reg.status_code == 201

    # Mixed-case request should still trigger a reset token on the row.
    resp = await client.post(
        "/api/auth/forgot-password",
        json={"email": "RESET@example.COM"},
    )
    assert resp.status_code == 200

    user = _find_user(session, "reset@example.com")
    assert user is not None
    assert user.password_reset_token_hash is not None
    assert user.password_reset_expires_at is not None


@pytest.mark.anyio
async def test_resend_verification_by_email_finds_account_regardless_of_case(unauth_client, mocker):
    client, session = unauth_client

    # Seed an unverified user directly (resend-by-email targets these).
    user = User(
        email="verify@example.com",
        hashed_password=hash_password("Pass12345!"),
        email_verified=False,
    )
    session.add(user)
    session.commit()

    send = mocker.patch("agent_port.email.verification.send_email")
    resp = await client.post(
        "/api/auth/resend-verification-by-email",
        json={"email": "VERIFY@Example.COM"},
    )
    assert resp.status_code == 200
    # A verification email was dispatched to the matching row.
    send.assert_called_once()


@pytest.mark.anyio
async def test_google_find_or_create_matches_existing_row_case_insensitively(
    unauth_client,
):
    _, session = unauth_client

    # Pre-existing password-only row, lowercased per the new normalization.
    existing = User(
        email="google@example.com",
        hashed_password=hash_password("Pass12345!"),
        email_verified=False,
    )
    session.add(existing)
    session.commit()
    session.refresh(existing)

    # Google returns the email in a different case.
    user = _find_or_create_user(
        session,
        sub="google-sub-xyz",
        email="GOOGLE@Example.COM",
        email_verified=True,
    )
    session.commit()

    # Same row was linked, not a new one.
    assert user.id == existing.id
    assert user.google_sub == "google-sub-xyz"
    assert user.email == "google@example.com"  # still lowercase
    assert len(_select_users(session)) == 1


@pytest.mark.anyio
async def test_google_find_or_create_stores_new_user_lowercased(unauth_client):
    _, session = unauth_client

    user = _find_or_create_user(
        session,
        sub="google-sub-new",
        email="  NEW.User@Example.COM  ",
        email_verified=True,
    )
    session.commit()

    assert user.email == "new.user@example.com"


# -- DB-level uniqueness -------------------------------------------------


@pytest.mark.anyio
async def test_db_index_rejects_case_variant_duplicate(unauth_client):
    """The functional unique index on LOWER(email) must block direct inserts
    of case-variant rows even if the application code is bypassed."""
    _, session = unauth_client

    session.add(User(email="idx@example.com", hashed_password="h"))
    session.commit()

    import sqlalchemy.exc

    session.add(User(email="IDX@example.com", hashed_password="h"))
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        session.commit()
    session.rollback()


# -- Google-login E2E via HTTP callback ---------------------------------


class _FakeGoogleMixedCaseClient:
    token_response: dict = {"access_token": "g_access_token"}
    userinfo_response: dict = {
        "sub": "google-sub-mixed",
        "email": "MIXED@Example.COM",
        "email_verified": True,
        "name": "Mixed",
    }

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, url, data=None, headers=None):
        return httpx.Response(
            200,
            json=self.token_response,
            request=httpx.Request("POST", url, headers=headers),
        )

    async def get(self, url, headers=None):
        return httpx.Response(
            200,
            json=self.userinfo_response,
            request=httpx.Request("GET", url, headers=headers),
        )


@pytest.mark.anyio
async def test_google_callback_links_existing_user_via_case_variant(unauth_client, monkeypatch):
    """Google returns MIXED@Example.COM; we have a lowercase row - should link."""
    client, session = unauth_client
    monkeypatch.setattr(settings, "google_login_client_id", "gid.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "google_login_client_secret", "gsecret")
    monkeypatch.setattr("agent_port.api.google_login.httpx.AsyncClient", _FakeGoogleMixedCaseClient)

    existing = User(email="mixed@example.com", hashed_password="h", email_verified=False)
    session.add(existing)
    session.commit()

    start = await client.get("/api/auth/google/login")
    state = parse_qs(urlparse(start.json()["authorization_url"]).query)["state"][0]

    resp = await client.get(
        f"/api/auth/google/callback?code=c&state={state}",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "access_token=" in resp.headers["location"]

    users = _select_users(session)
    assert len(users) == 1  # no duplicate row was created
    assert users[0].google_sub == "google-sub-mixed"
    assert users[0].email == "mixed@example.com"
