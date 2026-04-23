"""HTTP execution client for CustomIntegration tools.

Handles both ApiTool (declarative REST) and CustomTool (code-backed)
tools, returning results in the same format as the MCP client.
"""

import json
import re
from urllib.parse import quote

import httpx
from sqlmodel import Session

from agent_port.db import engine
from agent_port.integrations.types import ApiTool, CustomIntegration, CustomTool, Param
from agent_port.models.integration import InstalledIntegration
from agent_port.models.oauth import OAuthState
from agent_port.secrets.records import get_secret_value

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def _auth_headers(
    installed: InstalledIntegration, oauth_state: OAuthState | None = None
) -> dict[str, str]:
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


# ---------------------------------------------------------------------------
# Param → JSON Schema
# ---------------------------------------------------------------------------


def params_to_input_schema(params: list[Param]) -> dict:
    """Convert a list of Param definitions to a JSON Schema object."""
    properties: dict = {}
    required: list[str] = []

    for p in params:
        if p.schema_override is not None:
            properties[p.name] = p.schema_override
        else:
            prop: dict = {"type": p.type}
            if p.description:
                prop["description"] = p.description
            if p.default is not None:
                prop["default"] = p.default
            if p.enum:
                prop["enum"] = p.enum
            if p.type == "array" and p.items:
                prop["items"] = {"type": p.items}
            properties[p.name] = prop
        if p.required:
            required.append(p.name)

    schema: dict = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


# ---------------------------------------------------------------------------
# URL / request construction
# ---------------------------------------------------------------------------

_PATH_PARAM_RE = re.compile(r"\{(\w+)\}")


def _extract_path_params(path: str) -> list[str]:
    return _PATH_PARAM_RE.findall(path)


def _build_url(base_url: str, path: str, args: dict) -> str:
    url = base_url.rstrip("/") + "/" + path.lstrip("/")
    for param in _extract_path_params(path):
        value = args.get(param, "")
        url = url.replace(f"{{{param}}}", quote(str(value), safe=""))
    return url


def _build_query(tool_def: ApiTool, args: dict) -> dict[str, str]:
    query_names = {p.name for p in tool_def.params if p.query}
    return {k: args[k] for k in query_names if k in args and args[k] is not None}


def _build_body(tool_def: ApiTool, args: dict) -> dict | None:
    """Auto-build body from args not consumed by path params or query string."""
    path_params = set(_extract_path_params(tool_def.path))
    query_params = {p.name for p in tool_def.params if p.query}
    excluded = path_params | query_params
    body = {k: v for k, v in args.items() if k not in excluded and v is not None}
    return body if body else None


# ---------------------------------------------------------------------------
# Public API — mirrors mcp/client.py interface
# ---------------------------------------------------------------------------


def list_tools(integration: CustomIntegration) -> list[dict]:
    """Return tool definitions as MCP-compatible dicts."""
    return [
        {
            "name": t.name,
            "description": t.description,
            "inputSchema": params_to_input_schema(t.params),
        }
        for t in integration.tools
    ]


def get_tool_def(integration: CustomIntegration, tool_name: str) -> ApiTool | CustomTool | None:
    """Look up a single tool definition by name."""
    for t in integration.tools:
        if t.name == tool_name:
            return t
    return None


async def call_tool(
    installed: InstalledIntegration,
    tool_def: ApiTool | CustomTool,
    args: dict,
    oauth_state: OAuthState | None = None,
) -> dict:
    """Execute a tool call and return an MCP-compatible result dict."""
    headers = _auth_headers(installed, oauth_state)

    if isinstance(tool_def, CustomTool):
        return await tool_def.run(args, headers)

    # ApiTool: declarative HTTP dispatch
    url = _build_url(installed.url, tool_def.path, args)
    query = _build_query(tool_def, args)

    body: dict | None = None
    if tool_def.method.upper() in ("POST", "PUT", "PATCH"):
        body = _build_body(tool_def, args)

    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=tool_def.method.upper(),
            url=url,
            params=query or None,
            json=body,
            headers=headers,
            timeout=30.0,
        )

    if response.status_code >= 400:
        error_text = response.text
        try:
            error_json = response.json()
            error_text = json.dumps(error_json)
        except Exception:
            pass
        return {
            "content": [
                {"type": "text", "text": f"API error ({response.status_code}): {error_text}"}
            ],
            "isError": True,
        }

    try:
        result = response.json()
        return {
            "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
            "isError": False,
        }
    except Exception:
        return {
            "content": [{"type": "text", "text": response.text or "(empty response)"}],
            "isError": False,
        }
