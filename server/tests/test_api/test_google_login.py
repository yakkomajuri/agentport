from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from agent_port.api.google_login import _find_or_create_user
from agent_port.config import settings
from agent_port.db import get_session
from agent_port.main import app
from agent_port.models.google_login_state import GoogleLoginState
from agent_port.models.org import Org
from agent_port.models.org_membership import OrgMembership
from agent_port.models.user import User


class _FakeGoogleAsyncClient:
    """Stand-in for httpx.AsyncClient during Google login tests.

    Responds to Google's token and userinfo endpoints with preset payloads.
    """

    token_response: dict = {"access_token": "g_access_token"}
    userinfo_response: dict = {
        "sub": "google-sub-123",
        "email": "alice@example.com",
        "email_verified": True,
        "name": "Alice",
    }
    token_status: int = 200
    userinfo_status: int = 200

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, url, data=None, headers=None):
        return httpx.Response(
            self.token_status,
            json=self.token_response,
            request=httpx.Request("POST", url, headers=headers),
        )

    async def get(self, url, headers=None):
        return httpx.Response(
            self.userinfo_status,
            json=self.userinfo_response,
            request=httpx.Request("GET", url, headers=headers),
        )


@pytest.fixture(name="fresh_client")
async def fresh_client_fixture(monkeypatch):
    """Public (unauthenticated) client against a fresh in-memory DB.

    The default `client` fixture injects a pre-existing test_user/test_org, which
    would interfere with our "new user via Google" assertions. So we build our
    own isolated environment here.
    """
    monkeypatch.setattr(settings, "google_login_client_id", "gid.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "google_login_client_secret", "gsecret")
    monkeypatch.setattr(settings, "block_signups", False)
    monkeypatch.setattr(settings, "is_self_hosted", False)
    monkeypatch.setattr("agent_port.api.google_login.httpx.AsyncClient", _FakeGoogleAsyncClient)

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
async def test_start_returns_authorization_url(fresh_client):
    client, session = fresh_client

    resp = await client.get("/api/auth/google/login")
    assert resp.status_code == 200

    url = resp.json()["authorization_url"]
    parsed = urlparse(url)
    assert parsed.netloc == "accounts.google.com"
    params = parse_qs(parsed.query)
    assert params["client_id"] == ["gid.apps.googleusercontent.com"]
    assert params["response_type"] == ["code"]
    assert params["code_challenge_method"] == ["S256"]
    assert "state" in params

    # A pending row is persisted
    pending = session.exec(select(GoogleLoginState)).all()
    assert len(pending) == 1
    assert pending[0].state == params["state"][0]


@pytest.mark.anyio
async def test_start_returns_503_when_unconfigured(fresh_client, monkeypatch):
    client, _ = fresh_client
    monkeypatch.setattr(settings, "google_login_client_id", "")

    resp = await client.get("/api/auth/google/login")
    assert resp.status_code == 503


@pytest.mark.anyio
async def test_callback_creates_new_user_and_redirects_with_token(fresh_client):
    client, session = fresh_client

    start = await client.get("/api/auth/google/login")
    state = parse_qs(urlparse(start.json()["authorization_url"]).query)["state"][0]

    resp = await client.get(
        f"/api/auth/google/callback?code=code_xyz&state={state}",
        follow_redirects=False,
    )

    assert resp.status_code == 302
    location = resp.headers["location"]
    assert location.startswith(f"{settings.ui_base_url}/login/google/callback#")
    assert "access_token=" in location
    assert "token_type=bearer" in location

    user = session.exec(select(User).where(User.email == "alice@example.com")).first()
    assert user is not None
    assert user.google_sub == "google-sub-123"
    assert user.hashed_password is None
    assert user.email_verified is True

    # Org + membership auto-created
    membership = session.exec(select(OrgMembership).where(OrgMembership.user_id == user.id)).first()
    assert membership is not None
    assert membership.role == "owner"
    org = session.get(Org, membership.org_id)
    assert org is not None

    # Pending state row was cleared
    assert session.exec(select(GoogleLoginState)).all() == []


@pytest.mark.anyio
async def test_callback_links_existing_user_by_email(fresh_client):
    client, session = fresh_client

    # Pre-existing password-only account with the same email Google returns.
    existing = User(email="alice@example.com", hashed_password="hashed", email_verified=False)
    session.add(existing)
    session.commit()
    session.refresh(existing)

    start = await client.get("/api/auth/google/login")
    state = parse_qs(urlparse(start.json()["authorization_url"]).query)["state"][0]

    resp = await client.get(
        f"/api/auth/google/callback?code=code_xyz&state={state}",
        follow_redirects=False,
    )
    assert resp.status_code == 302

    session.expire_all()
    user = session.get(User, existing.id)
    assert user is not None
    assert user.google_sub == "google-sub-123"
    assert user.hashed_password == "hashed"  # still usable for password login
    assert user.email_verified is True  # Google-verified

    users = session.exec(select(User)).all()
    assert len(users) == 1  # no duplicate created


@pytest.mark.anyio
async def test_callback_reuses_existing_google_user(fresh_client):
    client, session = fresh_client

    existing = User(
        email="alice@example.com",
        hashed_password=None,
        google_sub="google-sub-123",
        email_verified=True,
    )
    session.add(existing)
    session.commit()

    start = await client.get("/api/auth/google/login")
    state = parse_qs(urlparse(start.json()["authorization_url"]).query)["state"][0]

    resp = await client.get(
        f"/api/auth/google/callback?code=code_xyz&state={state}",
        follow_redirects=False,
    )
    assert resp.status_code == 302

    users = session.exec(select(User)).all()
    assert len(users) == 1


@pytest.mark.anyio
async def test_callback_rejects_unknown_state(fresh_client):
    client, _ = fresh_client

    resp = await client.get(
        "/api/auth/google/callback?code=code_xyz&state=nonsense",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "google_error=invalid_state" in resp.headers["location"]


@pytest.mark.anyio
async def test_callback_propagates_oauth_error(fresh_client):
    client, _ = fresh_client

    start = await client.get("/api/auth/google/login")
    state = parse_qs(urlparse(start.json()["authorization_url"]).query)["state"][0]

    resp = await client.get(
        f"/api/auth/google/callback?state={state}&error=access_denied",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "google_error=access_denied" in resp.headers["location"]


@pytest.mark.anyio
async def test_callback_blocked_when_signups_disabled(fresh_client, monkeypatch):
    client, session = fresh_client
    monkeypatch.setattr(settings, "block_signups", True)

    start = await client.get("/api/auth/google/login")
    state = parse_qs(urlparse(start.json()["authorization_url"]).query)["state"][0]

    resp = await client.get(
        f"/api/auth/google/callback?code=code_xyz&state={state}",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "google_error=signups_disabled" in resp.headers["location"]
    assert session.exec(select(User)).all() == []


@pytest.mark.anyio
async def test_callback_blocked_when_self_hosted_org_exists(fresh_client, monkeypatch):
    client, session = fresh_client
    monkeypatch.setattr(settings, "is_self_hosted", True)

    session.add(Org(name="Existing"))
    session.commit()

    start = await client.get("/api/auth/google/login")
    state = parse_qs(urlparse(start.json()["authorization_url"]).query)["state"][0]

    resp = await client.get(
        f"/api/auth/google/callback?code=code_xyz&state={state}",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "google_error=self_hosted_org_exists" in resp.headers["location"]


# ---------------------------------------------------------------------------
# email_verified linking guard (finding #02)
# ---------------------------------------------------------------------------


@pytest.fixture(name="direct_session")
def direct_session_fixture():
    """Plain in-memory session for exercising _find_or_create_user directly."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()


def test_find_or_create_user_rejects_unverified_email_for_existing_account(direct_session):
    """An attacker-controlled Google identity with email_verified=false must
    NOT be silently linked to a pre-existing local account that happens to
    share the same email address."""
    victim = User(
        email="victim@example.com",
        hashed_password="hashed-password",
        email_verified=True,
    )
    direct_session.add(victim)
    direct_session.commit()
    direct_session.refresh(victim)
    victim_id = victim.id

    with pytest.raises(HTTPException) as err:
        _find_or_create_user(
            direct_session,
            sub="attacker-google-sub",
            email="victim@example.com",
            email_verified=False,
        )

    assert err.value.status_code == 403
    assert err.value.detail == "email_not_verified_by_idp"

    # The victim row must be untouched — in particular, google_sub must stay
    # None so the attacker's `sub` can't authenticate as the victim on a
    # subsequent login.
    direct_session.rollback()
    direct_session.expire_all()
    refreshed = direct_session.get(User, victim_id)
    assert refreshed is not None
    assert refreshed.google_sub is None
    assert refreshed.hashed_password == "hashed-password"


def test_find_or_create_user_links_when_email_verified(direct_session):
    """When Google marks the email verified, linking the existing local
    account is safe and expected."""
    existing = User(
        email="alice@example.com",
        hashed_password="hashed-password",
        email_verified=False,
    )
    direct_session.add(existing)
    direct_session.commit()
    direct_session.refresh(existing)

    result = _find_or_create_user(
        direct_session,
        sub="alice-google-sub",
        email="alice@example.com",
        email_verified=True,
    )
    direct_session.commit()

    assert result.id == existing.id
    assert result.google_sub == "alice-google-sub"
    assert result.email_verified is True  # promoted via Google-verified signal


def test_find_or_create_user_by_sub_unaffected_by_email_verified_flag(direct_session):
    """The lookup-by-sub branch is for users who already linked their Google
    account. It is not a linking step — Google just re-authenticated an
    already-known identity — so email_verified=false from Google must not
    block the login."""
    existing = User(
        email="bob@example.com",
        hashed_password=None,
        google_sub="bob-google-sub",
        email_verified=True,
    )
    direct_session.add(existing)
    direct_session.commit()
    direct_session.refresh(existing)

    result = _find_or_create_user(
        direct_session,
        sub="bob-google-sub",
        email="bob@example.com",
        email_verified=False,
    )

    assert result.id == existing.id
    assert result.google_sub == "bob-google-sub"


@pytest.mark.anyio
async def test_callback_rejects_unverified_email_for_existing_account(fresh_client, monkeypatch):
    """End-to-end: if the callback receives email_verified=false for an email
    that matches a pre-existing local account, it must NOT link the sub and
    must redirect with google_error=email_not_verified_by_idp."""
    client, session = fresh_client

    # Pre-existing local (password) account with no Google linkage.
    existing = User(
        email="victim@example.com",
        hashed_password="hashed-password",
        email_verified=True,
    )
    session.add(existing)
    session.commit()
    session.refresh(existing)
    existing_id = existing.id

    # Stub Google to return an unverified email matching the victim.
    monkeypatch.setattr(
        _FakeGoogleAsyncClient,
        "userinfo_response",
        {
            "sub": "attacker-google-sub",
            "email": "victim@example.com",
            "email_verified": False,
            "name": "Attacker",
        },
    )

    start = await client.get("/api/auth/google/login")
    state = parse_qs(urlparse(start.json()["authorization_url"]).query)["state"][0]

    resp = await client.get(
        f"/api/auth/google/callback?code=code_xyz&state={state}",
        follow_redirects=False,
    )

    assert resp.status_code == 302
    assert "google_error=email_not_verified_by_idp" in resp.headers["location"]
    assert "access_token=" not in resp.headers["location"]

    # The victim's row must not have been linked to the attacker's Google sub.
    session.expire_all()
    refreshed = session.get(User, existing_id)
    assert refreshed is not None
    assert refreshed.google_sub is None
