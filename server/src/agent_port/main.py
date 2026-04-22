import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler as _default_http_handler
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from mcp.server.auth.routes import create_auth_routes, create_protected_resource_routes
from mcp.server.auth.settings import ClientRegistrationOptions, RevocationOptions
from pydantic import AnyHttpUrl
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

# basicConfig must run before any agent_port module initializes its logger
# so the format applies everywhere — hence the intentional late imports below.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

from agent_port.analytics import posthog_client  # noqa: E402
from agent_port.api import (  # noqa: E402
    admin,
    api_keys,
    auth,
    billing,
    email_verification,
    google_login,
    installed,
    integrations,
    logs,
    oauth_server,
    password_change,
    password_reset,
    tool_approvals,
    tool_settings,
    tools,
    totp,
    user_auth,
    users,
)
from agent_port.config import settings  # noqa: E402
from agent_port.mcp.asgi import mcp_asgi_app  # noqa: E402
from agent_port.mcp.oauth_provider import oauth_provider  # noqa: E402
from agent_port.mcp.refresh import tool_cache_refresh_loop  # noqa: E402
from agent_port.mcp.server import session_manager  # noqa: E402

ASSET_CACHE_CONTROL = "public, max-age=31536000, immutable"
HTML_CACHE_CONTROL = "no-cache"


def validate_startup_settings() -> None:
    if settings.dev:
        return
    if settings.jwt_secret_key == "change-me-in-production":
        raise RuntimeError(
            "Refusing to start with the default JWT secret key. Set JWT_SECRET_KEY to a "
            "secure value before starting AgentPort."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_startup_settings()
    task = asyncio.create_task(tool_cache_refresh_loop())
    try:
        async with session_manager.run():
            yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        posthog_client.flush()


def _ui_file_response(path: Path, *, cache_control: str | None = None) -> FileResponse:
    headers = {"Cache-Control": cache_control} if cache_control else None
    return FileResponse(path, headers=headers)


app = FastAPI(
    title="AgentPort",
    description="Universal tool gateway for AI agents",
    version="0.1.0",
    lifespan=lifespan,
)

if settings.dev:

    @app.exception_handler(StarletteHTTPException)
    async def _dev_http_exception_handler(request: Request, exc: StarletteHTTPException):
        if exc.status_code >= 500:
            logger.error(
                "HTTP %d on %s %s: %s",
                exc.status_code,
                request.method,
                request.url.path,
                exc.detail,
            )
        return await _default_http_handler(request, exc)

    @app.exception_handler(Exception)
    async def _dev_unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


app.add_middleware(GZipMiddleware, minimum_size=500)

app.mount("/mcp", mcp_asgi_app)


class _MCPPathMiddleware:
    """Normalise /mcp (no trailing slash) → /mcp/ before routing.

    Starlette's Mount("/mcp") compiles to regex ^/mcp/(?P<path>.*)$ so a
    request for exactly /mcp never matches.  FastAPI's redirect_slashes=True
    then issues a 307 to /mcp/, but HTTP clients (including Claude Code) drop
    the Authorization header when following that redirect, causing a 401.
    Normalising the path here prevents the redirect entirely.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("path") == "/mcp":
            scope = {**scope, "path": "/mcp/"}
        await self.app(scope, receive, send)


app.add_middleware(_MCPPathMiddleware)


class _ImmutableAssetStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code < 400:
            response.headers.setdefault("Cache-Control", ASSET_CACHE_CONTROL)
        return response


app.include_router(integrations.router)
app.include_router(admin.router)
app.include_router(api_keys.router)
app.include_router(billing.router)
app.include_router(users.router)
app.include_router(user_auth.router)
app.include_router(google_login.router)
app.include_router(email_verification.router)
app.include_router(password_change.router)
app.include_router(password_reset.router)
app.include_router(totp.router)
app.include_router(installed.router)
app.include_router(auth.router)
app.include_router(tools.router)
app.include_router(tool_settings.router)
app.include_router(tool_approvals.router)
app.include_router(logs.router)
app.include_router(oauth_server.router)

# MCP SDK OAuth Authorization Server routes
for route in create_auth_routes(
    provider=oauth_provider,
    issuer_url=AnyHttpUrl(settings.base_url),
    client_registration_options=ClientRegistrationOptions(enabled=True),
    revocation_options=RevocationOptions(enabled=True),
):
    app.router.routes.append(route)

# MCP SDK Protected Resource Metadata routes
for route in create_protected_resource_routes(
    resource_url=AnyHttpUrl(f"{settings.base_url}/mcp"),
    authorization_servers=[AnyHttpUrl(settings.base_url)],
    resource_name="AgentPort MCP",
):
    app.router.routes.append(route)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# ─── UI static file serving ───────────────────────────────────────────────────
# ui_dist/ is copied in by the Dockerfile. Skip silently in local dev where
# only the Python server runs (UI is served by Vite on :5173).

_ui_dist = Path(__file__).parent.parent.parent / "ui_dist"

if _ui_dist.exists():
    _ui_index = _ui_dist / "index.html"

    # Serve hashed JS/CSS bundles from /assets (Vite's default output dir).
    app.mount(
        "/assets",
        _ImmutableAssetStaticFiles(directory=_ui_dist / "assets"),
        name="ui-assets",
    )

    # Catch-all: serve any existing root-level static file (favicon, etc.),
    # otherwise hand off to the React app so client-side routing works.
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        candidate = (_ui_dist / full_path).resolve()
        if candidate.is_relative_to(_ui_dist) and candidate.is_file():
            cache_control = HTML_CACHE_CONTROL if candidate == _ui_index else None
            return _ui_file_response(candidate, cache_control=cache_control)
        return _ui_file_response(_ui_index, cache_control=HTML_CACHE_CONTROL)
