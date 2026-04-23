"""MCP management tools: integration discovery and lifecycle management.

Exposed under the `agentport__` prefix, these allow an AI agent to browse
the integration catalog, install integrations, and manage auth flows.
"""

import asyncio
import json
import logging
import uuid

from fastapi import HTTPException
from mcp import types
from sqlmodel import Session, select

from agent_port.auth_start import start_oauth_for_installed
from agent_port.billing.limits import enforce_integration_limit
from agent_port.db import engine
from agent_port.integrations import registry as integration_registry
from agent_port.mcp.notifications import notify_tools_changed
from agent_port.mcp.refresh import refresh_one
from agent_port.models.integration import InstalledIntegration
from agent_port.models.oauth import OAuthState
from agent_port.models.tool_cache import ToolCache
from agent_port.models.tool_execution import ToolExecutionSetting
from agent_port.secrets.records import delete_secret, upsert_secret

logger = logging.getLogger(__name__)

MANAGEMENT_PREFIX = "agentport__"

_DEFAULT_APPROVAL_MODE = "require_approval"
_POLICY_NOTE = (
    "Reflects policy at the time of this call. Policy can change between "
    "describe_tool and call_tool; if call_tool returns an approval URL, that is "
    "authoritative. Modes: 'allow' runs without approval, 'require_approval' "
    "needs human approval before execution, 'deny' blocks the call."
)

MANAGEMENT_TOOLS: list[types.Tool] = [
    types.Tool(
        name="agentport__list_available_integrations",
        description=(
            "List integrations available to install from the AgentPort catalog. "
            "Returns id, name, description, type, supported auth methods, and docs URL. "
            "Optionally filter by type or search by free-text query (matches id, name, "
            "and description; whitespace-separated tokens are ANDed)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "description": "Filter by type: remote_mcp or custom",
                    "enum": ["remote_mcp", "custom"],
                },
                "query": {
                    "type": "string",
                    "description": (
                        "Free-text search. Case-insensitive; tokens are ANDed. "
                        "e.g. 'analytics', 'payments', 'email marketing'."
                    ),
                },
            },
        },
    ),
    types.Tool(
        name="agentport__get_integration",
        description=(
            "Get details of a specific bundled integration by its ID. "
            "Returns full metadata including auth methods and docs URL."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "integration_id": {
                    "type": "string",
                    "description": "The bundled integration ID, e.g. 'resend', 'github', 'stripe'",
                }
            },
            "required": ["integration_id"],
        },
    ),
    types.Tool(
        name="agentport__list_installed_integrations",
        description=(
            "List all integrations currently installed for this organization. "
            "Shows integration_id, type, auth_method, and connection status."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="agentport__install_integration",
        description=(
            "Install a bundled integration for this organization. "
            "For token auth: provide the API token — integration connects immediately. "
            "For oauth: an authorization URL is returned; share it with the user so they "
            "can complete the flow in their browser, then call agentport__get_auth_status."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "integration_id": {
                    "type": "string",
                    "description": "Bundled integration ID to install, e.g. 'resend', 'github'",
                },
                "auth_method": {
                    "type": "string",
                    "description": "Authentication method: 'token' or 'oauth'",
                    "enum": ["token", "oauth"],
                },
                "token": {
                    "type": "string",
                    "description": "API token (required when auth_method is 'token')",
                },
            },
            "required": ["integration_id", "auth_method"],
        },
    ),
    types.Tool(
        name="agentport__uninstall_integration",
        description="Remove an installed integration and delete its stored credentials.",
        inputSchema={
            "type": "object",
            "properties": {
                "integration_id": {
                    "type": "string",
                    "description": "Bundled integration ID of the installed integration to remove",
                }
            },
            "required": ["integration_id"],
        },
    ),
    types.Tool(
        name="agentport__get_auth_status",
        description=(
            "Check the authentication status of an installed integration. "
            "Returns whether it is connected and, for OAuth integrations, the flow status."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "integration_id": {
                    "type": "string",
                    "description": "Bundled integration ID of the installed integration",
                }
            },
            "required": ["integration_id"],
        },
    ),
    types.Tool(
        name="agentport__start_oauth_flow",
        description=(
            "Start or restart the OAuth authorization flow for an already-installed integration. "
            "Returns an authorization URL for the user to visit in their browser. "
            "Use this to reconnect an integration whose OAuth token has expired."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "integration_id": {
                    "type": "string",
                    "description": "Bundled integration ID of the installed integration",
                }
            },
            "required": ["integration_id"],
        },
    ),
    types.Tool(
        name="agentport__list_integration_tools",
        description=(
            "List tools available via installed integrations. "
            "If `integration_id` is given, returns that integration's tools (waits up to "
            "5 s for the cache to populate on first call). If omitted, searches across "
            "every installed integration's cached tools — fast, does not wait for missing "
            "caches. Optional `query` filters tools by name/description (case-insensitive, "
            "tokens ANDed). Each tool includes an `approval_mode` field indicating whether "
            "invoking it will run immediately ('allow'), require human approval "
            "('require_approval'), or be blocked ('deny')."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "integration_id": {
                    "type": "string",
                    "description": (
                        "Bundled integration ID. Omit to search across all installed integrations."
                    ),
                },
                "query": {
                    "type": "string",
                    "description": (
                        "Free-text search. Case-insensitive; tokens are ANDed. "
                        "Matches tool name and description."
                    ),
                },
            },
        },
    ),
    types.Tool(
        name="agentport__describe_tool",
        description=(
            "Return the full schema and description for a single tool in an installed "
            "integration. Use this after list_integration_tools to fetch the exact input "
            "schema before calling call_tool. Also returns an `approval` block describing "
            "the current approval policy for the tool (mode + whether it is configured or "
            "the default)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "integration_id": {
                    "type": "string",
                    "description": "Bundled integration ID of the installed integration",
                },
                "tool_name": {
                    "type": "string",
                    "description": "Name of the tool as returned by list_integration_tools",
                },
            },
            "required": ["integration_id", "tool_name"],
        },
    ),
    types.Tool(
        name="agentport__await_approval",
        description=(
            "Long-poll for a human approval decision on a tool call that returned an "
            "approval URL. Call this immediately after sharing the URL from call_tool — "
            "do NOT wait for the human to reply in chat. Returns the tool's real result "
            "when approved, a denied message when denied, or a 'still pending' message "
            "if the human hasn't decided within the server's long-poll budget (loop back "
            "in by calling this tool again with the same request_id)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "request_id": {
                    "type": "string",
                    "description": (
                        "Approval request UUID returned by agentport__call_tool in its "
                        "approval-required response."
                    ),
                }
            },
            "required": ["request_id"],
        },
    ),
    types.Tool(
        name="agentport__call_tool",
        description=(
            "Invoke a tool provided by an installed integration. Routes through the "
            "AgentPort approval policy and logs the call. For OAuth integrations, tokens "
            "are refreshed automatically on expiry. If the tool requires human approval, "
            "this returns an approval URL to share with a human — after they approve, "
            "retry with the same arguments."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "integration_id": {
                    "type": "string",
                    "description": "Bundled integration ID (e.g. 'gmail', 'notion', 'stripe').",
                },
                "tool_name": {
                    "type": "string",
                    "description": (
                        "Name of the tool to call, as returned by list_integration_tools "
                        "(without the integration_id prefix)."
                    ),
                },
                "arguments": {
                    "type": "object",
                    "description": (
                        "Arguments to pass to the tool. Must match the tool's input schema "
                        "(retrieve via describe_tool)."
                    ),
                    "additionalProperties": True,
                },
                "additional_info": {
                    "type": "string",
                    "description": (
                        "Optional free-text explanation of why you are making this tool "
                        "call. Shown to humans reviewing the call; never forwarded to the "
                        "underlying tool."
                    ),
                },
            },
            "required": ["integration_id", "tool_name", "arguments"],
        },
    ),
]


def _serialize_integration(integration) -> dict:
    return {
        "id": integration.id,
        "name": integration.name,
        "description": integration.description,
        "type": integration.type,
        "auth_methods": [a.method for a in integration.auth],
        "docs_url": integration.docs_url,
    }


def _serialize_installed(installed: InstalledIntegration) -> dict:
    return {
        "integration_id": installed.integration_id,
        "type": installed.type,
        "auth_method": installed.auth_method,
        "connected": installed.connected,
        "added_at": installed.added_at.isoformat(),
    }


def _text(data) -> list[types.TextContent]:
    if isinstance(data, str):
        return [types.TextContent(type="text", text=data)]
    return [types.TextContent(type="text", text=json.dumps(data, indent=2))]


def _matches_query(query: str, *haystacks: str) -> bool:
    """Case-insensitive AND match of whitespace-separated tokens against any haystack."""
    tokens = [t for t in query.lower().split() if t]
    if not tokens:
        return True
    blob = " ".join(h.lower() for h in haystacks if h)
    return all(tok in blob for tok in tokens)


def _resolve_approval_mode(org_id, integration_id: str, tool_name: str) -> tuple[str, str]:
    """Return (mode, source) for a (org, integration, tool). source ∈ {configured, default}."""
    with Session(engine) as db:
        setting = db.exec(
            select(ToolExecutionSetting)
            .where(ToolExecutionSetting.org_id == org_id)
            .where(ToolExecutionSetting.integration_id == integration_id)
            .where(ToolExecutionSetting.tool_name == tool_name)
        ).first()
    if setting:
        return setting.mode, "configured"
    return _DEFAULT_APPROVAL_MODE, "default"


def _load_policy_map_for_integration(org_id, integration_id: str) -> dict[str, str]:
    """Return {tool_name: mode} for all configured settings in one integration."""
    with Session(engine) as db:
        settings = db.exec(
            select(ToolExecutionSetting)
            .where(ToolExecutionSetting.org_id == org_id)
            .where(ToolExecutionSetting.integration_id == integration_id)
        ).all()
    return {s.tool_name: s.mode for s in settings}


async def _handle_list_available(args: dict) -> list[types.TextContent]:
    filter_type = args.get("type")
    query = (args.get("query") or "").strip()
    all_integrations = integration_registry.list_all()
    if filter_type:
        all_integrations = [i for i in all_integrations if i.type == filter_type]
    if query:
        all_integrations = [
            i for i in all_integrations if _matches_query(query, i.id, i.name, i.description or "")
        ]
    return _text([_serialize_integration(i) for i in all_integrations])


async def _handle_get_integration(args: dict) -> list[types.TextContent]:
    integration_id = args.get("integration_id", "")
    integration = integration_registry.get(integration_id)
    if not integration:
        return _text(f"Integration '{integration_id}' not found in catalog.")
    return _text(_serialize_integration(integration))


async def _handle_list_installed(org_id) -> list[types.TextContent]:
    with Session(engine) as db:
        rows = db.exec(
            select(InstalledIntegration).where(InstalledIntegration.org_id == org_id)
        ).all()
        return _text([_serialize_installed(r) for r in rows])


async def _handle_install(args: dict, org_id) -> list[types.TextContent]:
    integration_id = args.get("integration_id", "")
    auth_method = args.get("auth_method", "")
    token = args.get("token")

    bundled = integration_registry.get(integration_id)
    if not bundled:
        return _text(f"Integration '{integration_id}' not found in catalog.")

    valid_methods = {a.method for a in bundled.auth}
    if auth_method not in valid_methods:
        return _text(
            f"Auth method '{auth_method}' not supported for '{integration_id}'. "
            f"Supported: {sorted(valid_methods)}"
        )

    if auth_method == "token" and not token:
        return _text("A token is required when auth_method is 'token'.")

    with Session(engine) as db:
        existing = db.exec(
            select(InstalledIntegration)
            .where(InstalledIntegration.org_id == org_id)
            .where(InstalledIntegration.integration_id == integration_id)
        ).first()
        if existing:
            if existing.connected:
                return _text(f"Integration '{integration_id}' is already installed.")
            db.delete(existing)
            db.flush()

        try:
            enforce_integration_limit(org_id, db)
        except HTTPException as exc:
            detail = exc.detail
            if isinstance(detail, dict):
                return _text({"installed": False, **detail})
            return _text(
                {
                    "installed": False,
                    "error": "install_not_allowed",
                    "message": str(detail),
                }
            )

        if bundled.type == "remote_mcp":
            url = bundled.url
        elif bundled.type == "custom":
            url = bundled.base_url
        else:
            url = ""

        connected = auth_method == "token" and bool(token)

        installed = InstalledIntegration(
            org_id=org_id,
            integration_id=integration_id,
            type=bundled.type,
            url=url,
            auth_method=auth_method,
            connected=connected,
        )
        db.add(installed)
        db.flush()

        if token:
            secret = upsert_secret(
                db,
                org_id=org_id,
                kind="integration_token",
                ref=f"integrations/{org_id}/{integration_id}/token",
                value=token,
                secret_id=installed.token_secret_id,
            )
            installed.token_secret_id = secret.id
            db.add(installed)

        db.commit()
        db.refresh(installed)

        if auth_method == "oauth":
            from agent_port.models.org import Org

            org = db.get(Org, org_id)
            try:
                oauth_result = await start_oauth_for_installed(db, installed, org)
                return _text(
                    {
                        "installed": True,
                        "connected": False,
                        "integration_id": integration_id,
                        "authorization_url": oauth_result["authorization_url"],
                        "message": (
                            "Integration installed. Visit the authorization_url to complete OAuth, "
                            "then call agentport__get_auth_status to confirm."
                        ),
                    }
                )
            except Exception as exc:
                logger.warning("OAuth start failed after install for %s: %s", integration_id, exc)
                return _text(
                    {
                        "installed": True,
                        "connected": False,
                        "integration_id": integration_id,
                        "message": (
                            f"Integration installed but OAuth flow could not be started: {exc}. "
                            "Call agentport__start_oauth_flow to retry."
                        ),
                    }
                )

        if connected:
            asyncio.create_task(refresh_one(org_id, integration_id))

        return _text(
            {
                "installed": True,
                "connected": connected,
                "integration_id": integration_id,
                "message": (
                    "Integration installed and connected."
                    if connected
                    else "Integration installed."
                ),
            }
        )


async def _handle_uninstall(args: dict, org_id) -> list[types.TextContent]:
    integration_id = args.get("integration_id", "")
    with Session(engine) as db:
        installed = db.exec(
            select(InstalledIntegration)
            .where(InstalledIntegration.org_id == org_id)
            .where(InstalledIntegration.integration_id == integration_id)
        ).first()
        if not installed:
            return _text(f"No installed integration '{integration_id}' found.")

        oauth_state = db.exec(
            select(OAuthState)
            .where(OAuthState.org_id == org_id)
            .where(OAuthState.integration_id == integration_id)
        ).first()
        if oauth_state:
            delete_secret(db, oauth_state.client_secret_secret_id)
            delete_secret(db, oauth_state.access_token_secret_id)
            delete_secret(db, oauth_state.refresh_token_secret_id)
            db.delete(oauth_state)

        if installed.auth_method == "token":
            delete_secret(db, installed.token_secret_id)

        db.delete(installed)
        db.commit()

    await notify_tools_changed(org_id)
    return _text(f"Integration '{integration_id}' uninstalled.")


async def _handle_get_auth_status(args: dict, org_id) -> list[types.TextContent]:
    integration_id = args.get("integration_id", "")
    with Session(engine) as db:
        installed = db.exec(
            select(InstalledIntegration)
            .where(InstalledIntegration.org_id == org_id)
            .where(InstalledIntegration.integration_id == integration_id)
        ).first()
        if not installed:
            return _text(f"No installed integration '{integration_id}' found.")

        result: dict = {
            "integration_id": integration_id,
            "auth_method": installed.auth_method,
            "connected": installed.connected,
        }

        if installed.auth_method == "oauth":
            oauth_state = db.exec(
                select(OAuthState)
                .where(OAuthState.org_id == org_id)
                .where(OAuthState.integration_id == integration_id)
            ).first()
            result["oauth_status"] = oauth_state.status if oauth_state else "none"

        return _text(result)


async def _handle_start_oauth_flow(args: dict, org_id) -> list[types.TextContent]:
    integration_id = args.get("integration_id", "")
    with Session(engine) as db:
        installed = db.exec(
            select(InstalledIntegration)
            .where(InstalledIntegration.org_id == org_id)
            .where(InstalledIntegration.integration_id == integration_id)
        ).first()
        if not installed:
            return _text(f"No installed integration '{integration_id}' found.")
        if installed.auth_method != "oauth":
            return _text(
                f"Integration '{integration_id}' uses '{installed.auth_method}' auth, not OAuth."
            )

        from agent_port.models.org import Org

        org = db.get(Org, org_id)
        try:
            result = await start_oauth_for_installed(db, installed, org)
            return _text(
                {
                    "authorization_url": result["authorization_url"],
                    "message": (
                        "Visit the authorization_url to complete OAuth, "
                        "then call agentport__get_auth_status to confirm."
                    ),
                }
            )
        except ValueError as exc:
            return _text(f"Failed to start OAuth flow: {exc}")


async def _handle_list_integration_tools(args: dict, org_id) -> list[types.TextContent]:
    integration_id = (args.get("integration_id") or "").strip()
    query = (args.get("query") or "").strip()

    if integration_id:
        return await _list_tools_for_integration(org_id, integration_id, query)
    return await _list_tools_across_integrations(org_id, query)


async def _list_tools_for_integration(
    org_id, integration_id: str, query: str
) -> list[types.TextContent]:
    with Session(engine) as db:
        installed = db.exec(
            select(InstalledIntegration)
            .where(InstalledIntegration.org_id == org_id)
            .where(InstalledIntegration.integration_id == integration_id)
        ).first()
        if not installed:
            return _text(f"No installed integration '{integration_id}' found.")

        cache = db.exec(
            select(ToolCache)
            .where(ToolCache.org_id == org_id)
            .where(ToolCache.integration_id == integration_id)
        ).first()
        is_updating = installed.updating_tool_cache

    if cache is None or is_updating:
        await _wait_for_cache(org_id, integration_id, is_updating)
        with Session(engine) as db:
            cache = db.exec(
                select(ToolCache)
                .where(ToolCache.org_id == org_id)
                .where(ToolCache.integration_id == integration_id)
            ).first()

    if cache is None:
        return _text(
            f"No tools found for '{integration_id}'. The integration may not be connected yet."
        )

    tools = json.loads(cache.tools_json)
    if query:
        tools = [
            t for t in tools if _matches_query(query, t.get("name", ""), t.get("description", ""))
        ]

    policy_map = _load_policy_map_for_integration(org_id, integration_id)
    for t in tools:
        t["approval_mode"] = policy_map.get(t.get("name", ""), _DEFAULT_APPROVAL_MODE)

    return _text({"integration_id": integration_id, "tools": tools})


async def _list_tools_across_integrations(org_id, query: str) -> list[types.TextContent]:
    """Search every installed integration's cached tool list.

    Does not wait for missing caches — cross-integration search should be fast,
    and a just-installed integration has its own refresh task running.
    """
    results: list[dict] = []
    with Session(engine) as db:
        installed_rows = db.exec(
            select(InstalledIntegration).where(InstalledIntegration.org_id == org_id)
        ).all()
        installed_ids = {r.integration_id for r in installed_rows}
        caches = db.exec(select(ToolCache).where(ToolCache.org_id == org_id)).all()
        settings = db.exec(
            select(ToolExecutionSetting).where(ToolExecutionSetting.org_id == org_id)
        ).all()
    policy_map: dict[tuple[str, str], str] = {
        (s.integration_id, s.tool_name): s.mode for s in settings
    }

    for cache in caches:
        if cache.integration_id not in installed_ids:
            continue
        try:
            tools = json.loads(cache.tools_json)
        except Exception:
            continue
        for t in tools:
            name = t.get("name", "")
            description = t.get("description", "")
            if query and not _matches_query(query, name, description):
                continue
            results.append(
                {
                    "integration_id": cache.integration_id,
                    "name": name,
                    "description": description,
                    "approval_mode": policy_map.get(
                        (cache.integration_id, name), _DEFAULT_APPROVAL_MODE
                    ),
                }
            )

    return _text({"tools": results})


async def _handle_describe_tool(args: dict, org_id) -> list[types.TextContent]:
    integration_id = (args.get("integration_id") or "").strip()
    tool_name = (args.get("tool_name") or "").strip()
    if not integration_id or not tool_name:
        return _text("Both integration_id and tool_name are required.")

    with Session(engine) as db:
        installed = db.exec(
            select(InstalledIntegration)
            .where(InstalledIntegration.org_id == org_id)
            .where(InstalledIntegration.integration_id == integration_id)
        ).first()
        if not installed:
            return _text(f"No installed integration '{integration_id}' found.")

        cache = db.exec(
            select(ToolCache)
            .where(ToolCache.org_id == org_id)
            .where(ToolCache.integration_id == integration_id)
        ).first()
        is_updating = installed.updating_tool_cache

    if cache is None or is_updating:
        await _wait_for_cache(org_id, integration_id, is_updating)
        with Session(engine) as db:
            cache = db.exec(
                select(ToolCache)
                .where(ToolCache.org_id == org_id)
                .where(ToolCache.integration_id == integration_id)
            ).first()

    if cache is None:
        return _text(
            f"No tools found for '{integration_id}'. The integration may not be connected yet."
        )

    tools = json.loads(cache.tools_json)
    for t in tools:
        if t.get("name") == tool_name:
            mode, source = _resolve_approval_mode(org_id, integration_id, tool_name)
            return _text(
                {
                    "integration_id": integration_id,
                    "tool": t,
                    "approval": {
                        "mode": mode,
                        "source": source,
                        "note": _POLICY_NOTE,
                    },
                }
            )
    return _text(
        f"Tool '{tool_name}' not found in '{integration_id}'. "
        "Call list_integration_tools to see available tools."
    )


async def _handle_await_approval(args: dict) -> list[types.TextContent]:
    raw = (args.get("request_id") or "").strip() if isinstance(args.get("request_id"), str) else ""
    if not raw:
        return _text("`request_id` is required (the UUID from call_tool's approval response).")

    try:
        request_id = uuid.UUID(raw)
    except ValueError:
        return _text(f"`request_id` must be a UUID. Got: {raw!r}")

    # Lazy import to avoid the server <-> management_tools import cycle.
    from agent_port.mcp.server import await_approval

    return await await_approval(request_id)


async def _handle_call_tool(args: dict) -> list[types.TextContent]:
    integration_id = (args.get("integration_id") or "").strip()
    tool_name = (args.get("tool_name") or "").strip()
    arguments = args.get("arguments")
    additional_info = args.get("additional_info")

    if not integration_id or not tool_name:
        return _text("Both integration_id and tool_name are required.")
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        return _text("`arguments` must be an object.")

    # Forward additional_info via the conventional key — the executor pops it.
    if isinstance(additional_info, str) and additional_info.strip():
        arguments = {**arguments, "additional_info": additional_info}

    # Lazy import to avoid the server <-> management_tools import cycle.
    from agent_port.mcp.server import execute_upstream_tool

    return await execute_upstream_tool(integration_id, tool_name, arguments)


async def _wait_for_cache(org_id, integration_id: str, already_updating: bool) -> None:
    """Trigger a refresh if not already running, then poll until the flag clears."""
    if not already_updating:
        asyncio.create_task(refresh_one(org_id, integration_id))

    deadline = asyncio.get_event_loop().time() + 5.0
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.3)
        with Session(engine) as db:
            installed = db.exec(
                select(InstalledIntegration)
                .where(InstalledIntegration.org_id == org_id)
                .where(InstalledIntegration.integration_id == integration_id)
            ).first()
            if not installed or not installed.updating_tool_cache:
                return


async def dispatch(name: str, arguments: dict, auth) -> list[types.TextContent]:
    """Route a management tool call to its handler. auth is the AgentAuth dataclass."""
    org_id = auth.org.id

    handlers = {
        "agentport__list_available_integrations": lambda: _handle_list_available(arguments),
        "agentport__get_integration": lambda: _handle_get_integration(arguments),
        "agentport__list_installed_integrations": lambda: _handle_list_installed(org_id),
        "agentport__install_integration": lambda: _handle_install(arguments, org_id),
        "agentport__uninstall_integration": lambda: _handle_uninstall(arguments, org_id),
        "agentport__get_auth_status": lambda: _handle_get_auth_status(arguments, org_id),
        "agentport__start_oauth_flow": lambda: _handle_start_oauth_flow(arguments, org_id),
        "agentport__list_integration_tools": lambda: _handle_list_integration_tools(
            arguments, org_id
        ),
        "agentport__describe_tool": lambda: _handle_describe_tool(arguments, org_id),
        "agentport__call_tool": lambda: _handle_call_tool(arguments),
        "agentport__await_approval": lambda: _handle_await_approval(arguments),
    }

    handler = handlers.get(name)
    if handler is None:
        return [types.TextContent(type="text", text=f"Unknown management tool: {name}")]
    return await handler()
