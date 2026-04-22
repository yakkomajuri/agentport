import json
import logging
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime

from mcp import types
from mcp.server import Server
from mcp.server.lowlevel.server import NotificationOptions
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from sqlmodel import Session, col, select

from agent_port import api_client
from agent_port.approvals import events as approval_events
from agent_port.approvals.policy import evaluate_policy
from agent_port.approvals.requests import (
    create_auto_approved_request,
    get_or_create_approval_request,
    try_consume_approved_request,
)
from agent_port.config import settings
from agent_port.db import engine
from agent_port.integrations import registry as integration_registry
from agent_port.integrations.types import CustomIntegration
from agent_port.mcp import client as mcp_client
from agent_port.mcp import management_tools
from agent_port.mcp import oauth as oauth_refresh
from agent_port.mcp.notifications import register_session
from agent_port.models.integration import InstalledIntegration
from agent_port.models.log import LogEntry
from agent_port.models.oauth import OAuthState
from agent_port.models.tool_approval_request import ToolApprovalRequest

logger = logging.getLogger(__name__)

# Injected per-request by the ASGI wrapper before handle_request runs.
_current_auth: ContextVar = ContextVar("_current_auth")


@dataclass
class RequestMeta:
    ip: str | None
    user_agent: str | None


_current_request_meta: ContextVar[RequestMeta | None] = ContextVar(
    "_current_request_meta", default=None
)

mcp_server = Server("AgentPort")

# Advertise `tools.listChanged: true` in the initialize handshake so clients
# know to honour `notifications/tools/list_changed` pushes. The SDK's session
# manager calls create_initialization_options() with no arguments, so we patch
# it on this instance to set tools_changed=True.
_default_create_init_options = mcp_server.create_initialization_options


def _create_init_options_with_list_changed(
    notification_options: NotificationOptions | None = None,
    experimental_capabilities: dict | None = None,
):
    return _default_create_init_options(
        notification_options or NotificationOptions(tools_changed=True),
        experimental_capabilities or {},
    )


mcp_server.create_initialization_options = _create_init_options_with_list_changed


@mcp_server.list_tools()
async def _list_tools() -> list[types.Tool]:
    auth = _current_auth.get()
    org_id = auth.org.id

    # Register this MCP session under its org so tool-list mutations elsewhere
    # can push notifications/tools/list_changed to it. Safe to call repeatedly.
    try:
        register_session(org_id, mcp_server.request_context.session)
    except LookupError:
        # Running outside a request context (shouldn't happen here) — skip.
        pass

    # The MCP surface is deliberately narrow: the meta tools are the only
    # top-level tools. Upstream integration tools are discovered via
    # agentport__list_integration_tools and invoked via agentport__call_tool.
    return list(management_tools.MANAGEMENT_TOOLS)


@mcp_server.call_tool()
async def _call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    auth = _current_auth.get()

    if name.startswith(management_tools.MANAGEMENT_PREFIX):
        return await management_tools.dispatch(name, arguments, auth)

    return [
        types.TextContent(
            type="text",
            text=(
                f"Unknown tool: {name}. Invoke upstream integration tools via "
                "agentport__call_tool(integration_id, tool_name, arguments)."
            ),
        )
    ]


async def execute_upstream_tool(
    integration_id: str, tool_name: str, arguments: dict
) -> list[types.TextContent]:
    """Run an integration tool through the full approval/logging/OAuth-refresh path.

    Used by the agentport__call_tool meta-tool. Relies on _current_auth and
    _current_request_meta being set by the ASGI wrapper for this request.
    """
    auth = _current_auth.get()
    org = auth.org
    meta = _current_request_meta.get()
    requester_ip = meta.ip if meta else None
    user_agent = meta.user_agent if meta else None
    api_key_label = auth.api_key.name if auth.api_key else None
    api_key_prefix = auth.api_key.key_prefix if auth.api_key else None
    impersonator_user_id = auth.impersonator.id if auth.impersonator is not None else None

    if not isinstance(arguments, dict):
        arguments = {}

    # Optional free-text rationale from the agent. Pop so it doesn't get forwarded
    # to the upstream tool, whose schema may reject unknown fields.
    additional_info: str | None = None
    if "additional_info" in arguments:
        raw = arguments.pop("additional_info")
        if isinstance(raw, str) and raw.strip():
            additional_info = raw

    # ID of the approval request consumed on the approve_once path, if any.
    consumed_approval_id = None
    # ID of the auto-approved request created on the wildcard-policy path, if any.
    auto_approval_id = None
    # ID of an existing pending/approved LogEntry to update at execution time.
    pending_log_id: int | None = None

    with Session(engine) as session:
        installed = session.exec(
            select(InstalledIntegration)
            .where(InstalledIntegration.org_id == org.id)
            .where(InstalledIntegration.integration_id == integration_id)
        ).first()
        if not installed:
            return [
                types.TextContent(type="text", text=f"Integration '{integration_id}' not found.")
            ]

        decision = evaluate_policy(session, org.id, integration_id, tool_name, arguments)

        if not decision.allowed:
            if decision.reason == "denied":
                session.add(
                    LogEntry(
                        org_id=org.id,
                        integration_id=integration_id,
                        tool_name=tool_name,
                        args_json=json.dumps(arguments),
                        args_hash=decision.args_hash,
                        outcome="denied",
                        requester_ip=requester_ip,
                        user_agent=user_agent,
                        api_key_label=api_key_label,
                        api_key_prefix=api_key_prefix,
                        impersonator_user_id=impersonator_user_id,
                        additional_info=additional_info,
                    )
                )
                session.commit()
                return [
                    types.TextContent(
                        type="text", text="This tool has been blocked and cannot be executed."
                    )
                ]

            # Try to consume an already-approved (approve_once) request.
            consumed = try_consume_approved_request(
                session, org.id, integration_id, tool_name, decision.args_hash
            )
            if not consumed:
                requested_by = f"api_key:{auth.api_key.id}" if auth.api_key else None
                approval_req = get_or_create_approval_request(
                    session,
                    org.id,
                    integration_id,
                    tool_name,
                    arguments,
                    requested_by_agent=requested_by,
                    requester_ip=requester_ip,
                    user_agent=user_agent,
                    api_key_label=api_key_label,
                    additional_info=additional_info,
                )

                # Create a pending log entry so the request shows up in the logs immediately.
                # Guard against duplicates if the agent retries the blocked call.
                existing_pending = session.exec(
                    select(LogEntry)
                    .where(LogEntry.approval_request_id == approval_req.id)
                    .where(LogEntry.outcome == "pending")
                ).first()
                if not existing_pending:
                    session.add(
                        LogEntry(
                            org_id=org.id,
                            integration_id=integration_id,
                            tool_name=tool_name,
                            args_json=json.dumps(arguments),
                            args_hash=decision.args_hash,
                            approval_request_id=approval_req.id,
                            outcome="pending",
                            requester_ip=requester_ip,
                            user_agent=user_agent,
                            api_key_label=api_key_label,
                            api_key_prefix=api_key_prefix,
                            impersonator_user_id=impersonator_user_id,
                            additional_info=additional_info,
                        )
                    )
                    session.commit()

                approval_url = f"{settings.ui_base_url}/approve/{approval_req.id}"
                return [
                    types.TextContent(
                        type="text",
                        text=(
                            "AgentPort is a gateway for human-in-the-loop tool calling. "
                            "This tool was marked by a human as needing approval. "
                            "Share this URL with a human and explain what you were trying to do "
                            "(don't assume they can read this response): "
                            f"{approval_url}\n\n"
                            "Then, without waiting for a chat reply from the human, call "
                            "agentport__await_approval(request_id="
                            f'"{approval_req.id}") to be notified as soon as they decide. '
                            "If it returns 'still pending', call it again until you get a "
                            "decision or the human tells you to stop."
                        ),
                    )
                ]

            consumed_approval_id = consumed.id

        # For the tool_allowed path, create an auto-approved request record now.
        if decision.allowed and decision.reason == "tool_allowed":
            requested_by = f"api_key:{auth.api_key.id}" if auth.api_key else None
            auto_req = create_auto_approved_request(
                session,
                org.id,
                integration_id,
                tool_name,
                arguments,
                requested_by_agent=requested_by,
                requester_ip=requester_ip,
                user_agent=user_agent,
                api_key_label=api_key_label,
                api_key_prefix=api_key_prefix,
                additional_info=additional_info,
            )
            auto_approval_id = auto_req.id

        # For the approve_once path, find the pending/approved LogEntry to update later.
        if consumed_approval_id:
            existing_log = session.exec(
                select(LogEntry)
                .where(LogEntry.approval_request_id == consumed_approval_id)
                .where(col(LogEntry.outcome).in_(["pending", "approved"]))
            ).first()
            if existing_log:
                pending_log_id = existing_log.id

        access_reason: str | None = None
        if consumed_approval_id:
            access_reason = "approved_once"
        elif decision.reason == "tool_allowed":
            access_reason = "approved_any"

    return await _dispatch_and_log(
        org_id=org.id,
        integration_id=integration_id,
        tool_name=tool_name,
        arguments=arguments,
        args_hash=decision.args_hash,
        access_reason=access_reason,
        approval_request_id=consumed_approval_id or auto_approval_id,
        pending_log_id=pending_log_id,
        additional_info=additional_info,
        impersonator_user_id=impersonator_user_id,
        requester_ip=requester_ip,
        user_agent=user_agent,
        api_key_label=api_key_label,
        api_key_prefix=api_key_prefix,
    )


async def _dispatch_and_log(
    *,
    org_id: uuid.UUID,
    integration_id: str,
    tool_name: str,
    arguments: dict,
    args_hash: str,
    access_reason: str | None,
    approval_request_id: uuid.UUID | None,
    pending_log_id: int | None,
    additional_info: str | None,
    requester_ip: str | None,
    user_agent: str | None,
    api_key_label: str | None,
    api_key_prefix: str | None,
    impersonator_user_id: uuid.UUID | None,
) -> list[types.TextContent]:
    """Load the installed integration + oauth state, call the upstream tool, log.

    Shared by `execute_upstream_tool` (direct path) and `await_approval`
    (long-poll path). The caller has already handled policy evaluation and,
    where relevant, consumed the ToolApprovalRequest and created any pending
    log entry; here we just do the side-effectful work.
    """
    with Session(engine) as session:
        installed = session.exec(
            select(InstalledIntegration)
            .where(InstalledIntegration.org_id == org_id)
            .where(InstalledIntegration.integration_id == integration_id)
        ).first()
        if not installed:
            return [
                types.TextContent(type="text", text=f"Integration '{integration_id}' not found.")
            ]

        oauth_state = session.exec(
            select(OAuthState)
            .where(OAuthState.org_id == org_id)
            .where(OAuthState.integration_id == integration_id)
        ).first()

        # Refresh to reload any attributes expired by prior commits, then detach so
        # they remain accessible after the session closes.
        session.refresh(installed)
        session.expunge(installed)
        if oauth_state:
            session.refresh(oauth_state)
            session.expunge(oauth_state)

    # Pre-flight: refresh if token is known to be expired
    if (
        installed.auth_method == "oauth"
        and oauth_state
        and oauth_refresh.is_token_expired(oauth_state)
    ):
        refreshed = await oauth_refresh.refresh_tokens(oauth_state)
        if refreshed:
            oauth_state = refreshed

    # Dispatch to the right client based on integration type.
    bundled = integration_registry.get(installed.integration_id)
    is_api = isinstance(bundled, CustomIntegration)

    result: dict = {}
    last_error: Exception | None = None

    if is_api:
        tool_def = api_client.get_tool_def(bundled, tool_name)
        if not tool_def:
            return [types.TextContent(type="text", text=f"Tool '{tool_name}' not found.")]
        for attempt in range(2):
            try:
                result = await api_client.call_tool(installed, tool_def, arguments, oauth_state)
                last_error = None
                break
            except Exception as e:
                logger.exception(
                    "API tool call failed (attempt %d): %s__%s",
                    attempt + 1,
                    integration_id,
                    tool_name,
                )
                last_error = e
                if (
                    attempt == 0
                    and installed.auth_method == "oauth"
                    and oauth_state
                    and oauth_refresh.is_auth_error(e)
                ):
                    refreshed = await oauth_refresh.refresh_tokens(oauth_state)
                    if refreshed:
                        oauth_state = refreshed
                        continue
                break
    else:
        for attempt in range(2):
            try:
                result = await mcp_client.call_tool(installed, tool_name, arguments, oauth_state)
                last_error = None
                break
            except Exception as e:
                logger.exception(
                    "Tool call failed (attempt %d): %s__%s",
                    attempt + 1,
                    integration_id,
                    tool_name,
                )
                last_error = e
                if (
                    attempt == 0
                    and installed.auth_method == "oauth"
                    and oauth_state
                    and oauth_refresh.is_auth_error(e)
                ):
                    refreshed = await oauth_refresh.refresh_tokens(oauth_state)
                    if refreshed:
                        oauth_state = refreshed
                        continue
                break

    outcome = "error" if last_error else "executed"

    with Session(engine) as session:
        log = session.get(LogEntry, pending_log_id) if pending_log_id else None
        if log:
            # Update the existing pending/approved entry to reflect execution outcome.
            log.outcome = outcome
            log.result_json = json.dumps(result) if result and last_error is None else None
            log.error = str(last_error) if last_error else None
            log.access_reason = access_reason
            if additional_info and not log.additional_info:
                log.additional_info = additional_info
            if impersonator_user_id is not None and log.impersonator_user_id is None:
                log.impersonator_user_id = impersonator_user_id
            session.add(log)
        else:
            session.add(
                LogEntry(
                    org_id=org_id,
                    integration_id=integration_id,
                    tool_name=tool_name,
                    args_json=json.dumps(arguments),
                    args_hash=args_hash,
                    approval_request_id=approval_request_id,
                    requester_ip=requester_ip,
                    user_agent=user_agent,
                    api_key_label=api_key_label,
                    api_key_prefix=api_key_prefix,
                    access_reason=access_reason,
                    result_json=json.dumps(result) if result and last_error is None else None,
                    error=str(last_error) if last_error else None,
                    outcome=outcome,
                    impersonator_user_id=impersonator_user_id,
                    additional_info=additional_info,
                )
            )
        session.commit()

    if last_error is not None:
        return [types.TextContent(type="text", text=f"Tool call failed: {last_error}")]

    contents: list[types.TextContent] = []
    if result and "content" in result:
        for item in result["content"]:
            text = item.get("text", json.dumps(item))
            contents.append(types.TextContent(type="text", text=text))
    if not contents:
        contents.append(types.TextContent(type="text", text=json.dumps(result)))
    return contents


async def await_approval(request_id: uuid.UUID) -> list[types.TextContent]:
    """Long-poll for a decision on `request_id`.

    Returns:
    - The upstream tool result when the request is approved (executes the
      tool using the args stored on the ToolApprovalRequest).
    - A denied-by-human message on deny.
    - A still-pending message on timeout (agent can loop back in).

    Ownership is enforced: the request must belong to the caller's org,
    matching the existing /api/tool-approvals/requests/{id} behavior.
    """
    auth = _current_auth.get()
    org = auth.org
    meta = _current_request_meta.get()
    requester_ip = meta.ip if meta else None
    user_agent = meta.user_agent if meta else None
    api_key_label = auth.api_key.name if auth.api_key else None
    api_key_prefix = auth.api_key.key_prefix if auth.api_key else None
    impersonator_user_id = auth.impersonator.id if auth.impersonator is not None else None

    # Initial ownership + state check so we 404 fast on bad ids.
    with Session(engine) as session:
        req = session.get(ToolApprovalRequest, request_id)
        if not req or req.org_id != org.id:
            return [
                types.TextContent(type="text", text=f"Approval request '{request_id}' not found.")
            ]
        initial_status = req.status
        integration_id = req.integration_id
        tool_name = req.tool_name
        args_json = req.args_json
        args_hash = req.args_hash
        additional_info = req.additional_info

    # If a decision is already in the DB (e.g. approve/deny raced ahead of our
    # first call, or this is a retry after a timeout/server restart), skip the
    # wait and resolve directly.
    if initial_status in ("pending",):

        def _peek_status() -> str | None:
            with Session(engine) as session:
                current = session.get(ToolApprovalRequest, request_id)
                return current.status if current else None

        decision = await approval_events.wait_for_decision(
            request_id,
            timeout=float(settings.approval_long_poll_timeout_seconds),
            pre_check=_peek_status,
        )

        if decision == "timeout":
            return [
                types.TextContent(
                    type="text",
                    text=(
                        "Still pending — the human hasn't decided yet. Call "
                        f'agentport__await_approval(request_id="{request_id}") again to '
                        "keep waiting, or stop if they need more time."
                    ),
                )
            ]
        if decision == "denied":
            return [types.TextContent(type="text", text="This tool call was denied by the human.")]
        # decision == "approved": fall through to execute
    elif initial_status == "denied":
        return [types.TextContent(type="text", text="This tool call was denied by the human.")]
    elif initial_status != "approved":
        # expired / consumed / auto_approved: nothing to wait on and nothing
        # reasonable to re-execute here — tell the agent to restart the call.
        return [
            types.TextContent(
                type="text",
                text=(
                    f"Approval request '{request_id}' is '{initial_status}' and cannot be "
                    "awaited. Retry the original agentport__call_tool call to start over."
                ),
            )
        ]

    # Re-read to tolerate server-restart recovery: the expires_at cut-off may
    # have fired during the wait, or a concurrent /deny may have won.
    with Session(engine) as session:
        req = session.get(ToolApprovalRequest, request_id)
        if not req or req.org_id != org.id:
            return [
                types.TextContent(type="text", text=f"Approval request '{request_id}' not found.")
            ]
        if req.status == "denied":
            return [types.TextContent(type="text", text="This tool call was denied by the human.")]
        if req.status == "expired" or req.expires_at <= datetime.utcnow():
            return [
                types.TextContent(
                    type="text",
                    text=(
                        "Still pending — the human hasn't decided yet. Call "
                        f'agentport__await_approval(request_id="{request_id}") again to '
                        "keep waiting, or stop if they need more time."
                    ),
                )
            ]

    # Reconstruct args from the stored normalized JSON so we call the upstream
    # tool with exactly what the human approved.
    try:
        arguments = json.loads(args_json) if args_json else {}
    except ValueError:
        arguments = {}
    if not isinstance(arguments, dict):
        arguments = {}

    # Consume the approve_once record (atomic state transition). For
    # allow_tool_forever / auto_approved the agent should just call the tool
    # directly — but we handle approve_once here since that is the whole
    # point of this flow.
    consumed_approval_id: uuid.UUID | None = None
    pending_log_id: int | None = None
    access_reason = "approved_once"

    with Session(engine) as session:
        consumed = try_consume_approved_request(
            session, org.id, integration_id, tool_name, args_hash
        )
        if consumed is None:
            # Either already consumed (double-wait race) or not of decision_mode
            # approve_once. Fall back to "share the decision" rather than
            # attempting to execute twice.
            return [
                types.TextContent(
                    type="text",
                    text=(
                        "The approval was recorded but can no longer be consumed here "
                        "(it may have been used already). Retry the original "
                        "agentport__call_tool call if you still need the tool to run."
                    ),
                )
            ]
        consumed_approval_id = consumed.id

        existing_log = session.exec(
            select(LogEntry)
            .where(LogEntry.approval_request_id == consumed_approval_id)
            .where(col(LogEntry.outcome).in_(["pending", "approved"]))
        ).first()
        if existing_log:
            pending_log_id = existing_log.id

    return await _dispatch_and_log(
        org_id=org.id,
        integration_id=integration_id,
        tool_name=tool_name,
        arguments=arguments,
        args_hash=args_hash,
        access_reason=access_reason,
        approval_request_id=consumed_approval_id,
        pending_log_id=pending_log_id,
        additional_info=additional_info,
        impersonator_user_id=impersonator_user_id,
        requester_ip=requester_ip,
        user_agent=user_agent,
        api_key_label=api_key_label,
        api_key_prefix=api_key_prefix,
    )


# Stateful mode is required for server-pushed notifications like
# notifications/tools/list_changed — each client holds a persistent session
# with a dedicated SSE stream keyed by the mcp-session-id header. Idle
# sessions are reaped so dropped connections don't accumulate.
session_manager = StreamableHTTPSessionManager(
    app=mcp_server,
    stateless=False,
    session_idle_timeout=1800,
)
