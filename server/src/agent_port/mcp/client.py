from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from sqlmodel import Session

from agent_port.db import engine
from agent_port.models.integration import InstalledIntegration
from agent_port.models.oauth import OAuthState
from agent_port.secrets.records import get_secret_value


def _auth_headers(installed: InstalledIntegration, oauth_state: OAuthState | None = None) -> dict:
    if installed.auth_method == "token":
        with Session(engine) as session:
            token = get_secret_value(session, installed.token_secret_id)
        if token:
            return {"Authorization": f"Bearer {token}"}

    if installed.auth_method == "oauth" and oauth_state:
        with Session(engine) as session:
            access_token = get_secret_value(session, oauth_state.access_token_secret_id)
        if access_token:
            return {"Authorization": f"Bearer {access_token}"}

    return {}


def _unwrap_exception(e: BaseException) -> str:
    """Return a readable error string, unpacking ExceptionGroup sub-exceptions."""
    if isinstance(e, BaseExceptionGroup):
        parts = [_unwrap_exception(sub) for sub in e.exceptions]
        return "; ".join(parts)
    return str(e)


async def validate_token(url: str, token: str) -> None:
    """Verify a token works by attempting to list tools. Raises RuntimeError on failure."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with streamablehttp_client(url, headers=headers) as (r, w, _):
            async with ClientSession(r, w) as session:
                await session.initialize()
                await session.list_tools()
    except BaseExceptionGroup as eg:
        raise RuntimeError(_unwrap_exception(eg)) from eg


async def list_tools(
    installed: InstalledIntegration, oauth_state: OAuthState | None = None
) -> list[dict]:
    headers = _auth_headers(installed, oauth_state)
    try:
        async with streamablehttp_client(installed.url, headers=headers) as (r, w, _):
            async with ClientSession(r, w) as session:
                await session.initialize()
                result = await session.list_tools()
                return [t.model_dump() for t in result.tools]
    except BaseExceptionGroup as eg:
        raise RuntimeError(_unwrap_exception(eg)) from eg


async def call_tool(
    installed: InstalledIntegration,
    tool_name: str,
    args: dict,
    oauth_state: OAuthState | None = None,
) -> dict:
    headers = _auth_headers(installed, oauth_state)
    try:
        async with streamablehttp_client(installed.url, headers=headers) as (r, w, _):
            async with ClientSession(r, w) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, args)
                return {
                    "content": [c.model_dump() for c in result.content],
                    "isError": result.isError,
                }
    except BaseExceptionGroup as eg:
        raise RuntimeError(_unwrap_exception(eg)) from eg
