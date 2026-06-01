"""HTTP execution client for CustomIntegration tools.

Handles both ApiTool (declarative REST) and CustomTool (code-backed)
tools, returning results in the same format as the MCP client.
"""

import json
import re
import time
from urllib.parse import quote

import httpx
from sqlmodel import Session

from agent_port.db import engine
from agent_port.integrations.types import ApiTool, CustomIntegration, CustomTool, Param, TokenAuth
from agent_port.models.integration import InstalledIntegration
from agent_port.models.oauth import OAuthState
from agent_port.secrets.records import get_secret_value
from agent_port.token_auth import build_token_auth_headers
from agent_port.upstream_safety import UnsafeUpstreamUrlError, validate_safe_url

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def _auth_headers(
    installed: InstalledIntegration,
    oauth_state: OAuthState | None = None,
    integration: CustomIntegration | None = None,
) -> dict[str, str]:
    if installed.auth_method == "token":
        with Session(engine) as session:
            token = get_secret_value(session, installed.token_secret_id)
        if token:
            token_auth = _token_auth(integration)
            if token_auth:
                return build_token_auth_headers(token_auth.header, token_auth.format, token)
            return build_token_auth_headers("Authorization", "Bearer {token}", token)

    if installed.auth_method == "oauth" and oauth_state:
        with Session(engine) as session:
            access_token = get_secret_value(session, oauth_state.access_token_secret_id)
        if access_token:
            return {"Authorization": f"Bearer {access_token}"}

    return {}


def _token_auth(integration: CustomIntegration | None) -> TokenAuth | None:
    if integration is None:
        return None
    for auth in integration.auth:
        if isinstance(auth, TokenAuth):
            return auth
    return None


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


async def _read_response_body(
    response: httpx.Response, max_response_bytes: int | None = None
) -> tuple[bytes, bool]:
    if max_response_bytes is None:
        return await response.aread(), False

    chunks: list[bytes] = []
    total = 0
    truncated = False
    async for chunk in response.aiter_bytes():
        if total + len(chunk) > max_response_bytes:
            keep = max_response_bytes - total
            if keep > 0:
                chunks.append(chunk[:keep])
            truncated = True
            break
        chunks.append(chunk)
        total += len(chunk)
    return b"".join(chunks), truncated


def _decode_response_body(response: httpx.Response, body: bytes) -> str:
    if not body:
        return ""
    encoding = response.encoding or "utf-8"
    return body.decode(encoding, errors="replace")


def _result_from_response(
    response: httpx.Response,
    body: bytes,
    duration_ms: int,
    *,
    truncated: bool,
) -> dict:
    text = _decode_response_body(response, body)
    if truncated:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "API response exceeded the maximum allowed response size.",
                }
            ],
            "isError": True,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        }

    if response.status_code >= 400:
        error_text = text
        try:
            error_text = json.dumps(json.loads(text))
        except Exception:
            pass
        return {
            "content": [
                {"type": "text", "text": f"API error ({response.status_code}): {error_text}"}
            ],
            "isError": True,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        }

    try:
        result = json.loads(text)
        content_text = json.dumps(result, indent=2)
    except Exception:
        content_text = text or "(empty response)"

    return {
        "content": [{"type": "text", "text": content_text}],
        "isError": False,
        "status_code": response.status_code,
        "duration_ms": duration_ms,
    }


async def dispatch_api_tool(
    *,
    base_url: str,
    tool_def: ApiTool,
    args: dict,
    headers: dict[str, str],
    timeout: float | httpx.Timeout = 30.0,
    follow_redirects: bool = False,
    max_request_body_bytes: int | None = None,
    max_response_bytes: int | None = None,
) -> dict:
    """Execute a declarative ApiTool against an HTTP API."""
    url = _build_url(base_url, tool_def.path, args)
    # Re-validate the full URL at dispatch time. The base URL was checked when
    # the integration was saved, but the hostname's DNS records may have
    # changed (or been crafted) to point at internal IPs since then.
    try:
        validate_safe_url(url, allow_query=True)
    except UnsafeUpstreamUrlError as exc:
        return {
            "content": [{"type": "text", "text": f"Unsafe upstream URL: {exc}"}],
            "isError": True,
            "status_code": None,
            "duration_ms": 0,
        }

    query = _build_query(tool_def, args)

    body: dict | None = None
    if tool_def.method.upper() in ("POST", "PUT", "PATCH"):
        body = _build_body(tool_def, args)

    if body is not None and max_request_body_bytes is not None:
        body_bytes = json.dumps(body, separators=(",", ":")).encode()
        if len(body_bytes) > max_request_body_bytes:
            return {
                "content": [{"type": "text", "text": "API request body is too large."}],
                "isError": True,
                "status_code": None,
                "duration_ms": 0,
            }

    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=follow_redirects) as client:
        async with client.stream(
            method=tool_def.method.upper(),
            url=url,
            params=query or None,
            json=body,
            headers=headers,
        ) as response:
            body_bytes, truncated = await _read_response_body(response, max_response_bytes)

    duration_ms = int((time.perf_counter() - start) * 1000)
    return _result_from_response(
        response,
        body_bytes,
        duration_ms,
        truncated=truncated,
    )


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
    integration: CustomIntegration | None = None,
    auth_headers: dict[str, str] | None = None,
) -> dict:
    """Execute a tool call and return an MCP-compatible result dict."""
    headers = (
        auth_headers
        if auth_headers is not None
        else _auth_headers(installed, oauth_state, integration)
    )

    if isinstance(tool_def, CustomTool):
        return await tool_def.run(args, headers)

    return await dispatch_api_tool(
        base_url=installed.url,
        tool_def=tool_def,
        args=args,
        headers=headers,
    )
