import httpx
import pytest
from sqlmodel import select

from agent_port.models.oauth import OAuthState
from agent_port.models.secret import Secret


class FakeOAuthAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, url, headers=None):
        return httpx.Response(
            401,
            headers={
                "WWW-Authenticate": 'Bearer resource_metadata="https://auth.example.com/.well-known/oauth-protected-resource/mcp"'
            },
            request=httpx.Request("GET", url, headers=headers),
        )

    async def send(self, request):
        if request.url.path == "/.well-known/oauth-protected-resource/mcp":
            return httpx.Response(
                200,
                json={
                    "resource": "https://mcp.posthog.com/mcp",
                    "authorization_servers": ["https://auth.example.com"],
                    "scopes_supported": ["openid", "profile"],
                },
                request=request,
            )
        if request.url.path == "/.well-known/oauth-authorization-server":
            return httpx.Response(
                200,
                json={
                    "issuer": "https://auth.example.com",
                    "authorization_endpoint": "https://auth.example.com/authorize",
                    "token_endpoint": "https://auth.example.com/token",
                    "registration_endpoint": "https://auth.example.com/register",
                    "scopes_supported": ["openid", "profile"],
                },
                request=request,
            )
        if request.url.path == "/register":
            return httpx.Response(
                201,
                json={
                    "client_id": "client_123",
                    "redirect_uris": ["http://localhost:4747/api/auth/callback"],
                    "grant_types": ["authorization_code", "refresh_token"],
                    "response_types": ["code"],
                    "token_endpoint_auth_method": "none",
                    "client_name": "AgentPort",
                },
                request=request,
            )
        raise AssertionError(f"Unexpected request to {request.method} {request.url}")

    async def post(self, url, data=None, headers=None):
        return httpx.Response(
            200,
            json={
                "access_token": "access_token",
                "refresh_token": "refresh_token",
                "token_type": "Bearer",
            },
            request=httpx.Request("POST", url, headers=headers),
        )


@pytest.fixture
def fake_oauth_http(monkeypatch):
    monkeypatch.setattr("agent_port.api.auth.httpx.AsyncClient", FakeOAuthAsyncClient)
    monkeypatch.setattr("agent_port.auth_start.httpx.AsyncClient", FakeOAuthAsyncClient)
    monkeypatch.setattr("agent_port.api.auth.refresh_one", lambda *args, **kwargs: None)


@pytest.mark.anyio
async def test_start_oauth(client, fake_oauth_http):
    # First install with oauth
    await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "oauth",
        },
    )

    resp = await client.post("/api/auth/posthog/start")
    assert resp.status_code == 200
    data = resp.json()
    assert "authorization_url" in data
    assert "state" in data
    assert data["authorization_url"].startswith("https://auth.example.com/authorize?")

    installed = await client.get("/api/installed")
    assert installed.status_code == 200
    assert installed.json()[0]["connected"] is False


@pytest.mark.anyio
async def test_start_oauth_not_found(client):
    resp = await client.post("/api/auth/nonexistent/start")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_start_oauth_wrong_auth_method(client):
    await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "token",
            "token": "phx_key",
        },
    )

    resp = await client.post("/api/auth/posthog/start")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_oauth_callback(client, fake_oauth_http):
    # Install with oauth and start the flow
    install_resp = await client.post(
        "/api/installed",
        json={
            "integration_id": "posthog",
            "auth_method": "oauth",
        },
    )
    assert install_resp.status_code == 201

    start_resp = await client.post("/api/auth/posthog/start")
    assert start_resp.status_code == 200
    state = start_resp.json()["state"]

    # Simulate the callback
    resp = await client.get(
        f"/api/auth/callback?code=test_code&state={state}",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"].endswith("/integrations/posthog")

    installed = await client.get("/api/installed")
    assert installed.status_code == 200
    assert installed.json()[0]["connected"] is True


@pytest.mark.anyio
async def test_oauth_callback_no_pending(client):
    resp = await client.get(
        "/api/auth/callback?code=test_code&state=test_state",
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_disconnect_cleans_up_oauth_state_and_secrets(client, session, fake_oauth_http):
    """Disconnecting an OAuth integration must clean up its OAuthState row
    and all associated secrets, so reconnecting starts from a clean slate."""
    # Install with OAuth, start the flow, and complete the callback.
    await client.post(
        "/api/installed",
        json={"integration_id": "posthog", "auth_method": "oauth"},
    )
    start = await client.post("/api/auth/posthog/start")
    state = start.json()["state"]
    await client.get(
        f"/api/auth/callback?code=test_code&state={state}",
        follow_redirects=False,
    )

    # Confirm the OAuth state and secrets exist before disconnect.
    assert session.exec(select(OAuthState)).first() is not None
    assert session.exec(select(Secret)).first() is not None

    resp = await client.delete("/api/installed/posthog")
    assert resp.status_code == 204

    session.expire_all()
    assert session.exec(select(OAuthState)).all() == []
    assert session.exec(select(Secret)).all() == []


@pytest.mark.anyio
async def test_reconnect_after_disconnect_succeeds(client, fake_oauth_http):
    """Disconnecting and reconnecting an OAuth integration must not 500."""
    # Initial connect: install → start → callback.
    await client.post(
        "/api/installed",
        json={"integration_id": "posthog", "auth_method": "oauth"},
    )
    start = await client.post("/api/auth/posthog/start")
    state = start.json()["state"]
    await client.get(
        f"/api/auth/callback?code=test_code&state={state}",
        follow_redirects=False,
    )

    # Disconnect.
    resp = await client.delete("/api/installed/posthog")
    assert resp.status_code == 204

    # Reconnect from scratch: install → start → callback.
    reinstall = await client.post(
        "/api/installed",
        json={"integration_id": "posthog", "auth_method": "oauth"},
    )
    assert reinstall.status_code == 201

    restart = await client.post("/api/auth/posthog/start")
    assert restart.status_code == 200
    new_state = restart.json()["state"]

    callback = await client.get(
        f"/api/auth/callback?code=test_code&state={new_state}",
        follow_redirects=False,
    )
    assert callback.status_code == 302

    installed = await client.get("/api/installed")
    assert installed.json()[0]["connected"] is True
