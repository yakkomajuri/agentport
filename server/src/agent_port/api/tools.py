import asyncio
import json
import logging
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from agent_port import api_client
from agent_port.analytics import posthog_client
from agent_port.approvals.normalize import hash_normalized_args, normalize_tool_args
from agent_port.approvals.policy import evaluate_policy
from agent_port.approvals.requests import (
    create_auto_approved_request,
    get_or_create_approval_request,
    try_consume_approved_request,
)
from agent_port.config import settings
from agent_port.db import get_session
from agent_port.dependencies import AgentAuth, get_agent_auth
from agent_port.integrations import registry as integration_registry
from agent_port.integrations.types import CustomIntegration
from agent_port.mcp import client as mcp_client
from agent_port.mcp import oauth as oauth_refresh
from agent_port.models.integration import InstalledIntegration
from agent_port.models.log import LogEntry
from agent_port.models.oauth import OAuthState
from agent_port.models.tool_cache import CACHE_TTL, ToolCache
from agent_port.models.tool_execution import ToolExecutionSetting

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tools", tags=["tools"])

_CACHE_POLL_INTERVAL = 0.3
_CACHE_POLL_TIMEOUT = 5.0


class CallToolRequest(BaseModel):
    tool_name: str
    args: dict = {}
    # Optional free-text explanation the agent can attach to justify the call.
    # Surfaced on approval requests and in logs. Never sent to the upstream tool.
    additional_info: str | None = None


async def _wait_for_in_progress_refresh(
    installed: InstalledIntegration,
    session: Session,
) -> list[dict] | None:
    bind = session.get_bind()
    if bind is None:
        return None

    with Session(bind) as wait_session:
        latest_installed = wait_session.exec(
            select(InstalledIntegration)
            .where(InstalledIntegration.org_id == installed.org_id)
            .where(InstalledIntegration.integration_id == installed.integration_id)
        ).first()
    if not latest_installed or not latest_installed.updating_tool_cache:
        return None

    logger.info(
        "tool_cache WAIT %s (org=%s) refresh already in progress",
        installed.integration_id,
        installed.org_id,
    )
    deadline = asyncio.get_event_loop().time() + _CACHE_POLL_TIMEOUT
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(_CACHE_POLL_INTERVAL)
        with Session(bind) as wait_session:
            latest_installed = wait_session.exec(
                select(InstalledIntegration)
                .where(InstalledIntegration.org_id == installed.org_id)
                .where(InstalledIntegration.integration_id == installed.integration_id)
            ).first()
            cache = wait_session.exec(
                select(ToolCache)
                .where(ToolCache.org_id == installed.org_id)
                .where(ToolCache.integration_id == installed.integration_id)
            ).first()

        if cache and (datetime.utcnow() - cache.fetched_at) < CACHE_TTL:
            logger.info(
                "tool_cache WAIT-HIT %s (org=%s) age=%.1fs",
                installed.integration_id,
                installed.org_id,
                (datetime.utcnow() - cache.fetched_at).total_seconds(),
            )
            return json.loads(cache.tools_json)

        if not latest_installed or not latest_installed.updating_tool_cache:
            if cache:
                logger.info(
                    "tool_cache WAIT-DONE %s (org=%s) using cache age=%.1fs",
                    installed.integration_id,
                    installed.org_id,
                    (datetime.utcnow() - cache.fetched_at).total_seconds(),
                )
                return json.loads(cache.tools_json)
            logger.info(
                "tool_cache WAIT-DONE %s (org=%s) no cache available after refresh",
                installed.integration_id,
                installed.org_id,
            )
            return None

    logger.info(
        "tool_cache WAIT-TIMEOUT %s (org=%s) after %.1fs",
        installed.integration_id,
        installed.org_id,
        _CACHE_POLL_TIMEOUT,
    )
    return None


def _get_execution_modes(session: Session, org_id, integration_id: str) -> dict[str, str]:
    settings = session.exec(
        select(ToolExecutionSetting)
        .where(ToolExecutionSetting.org_id == org_id)
        .where(ToolExecutionSetting.integration_id == integration_id)
    ).all()
    return {setting.tool_name: setting.mode for setting in settings}


async def _get_tools_cached(
    installed: InstalledIntegration,
    oauth_state: OAuthState | None,
    session: Session,
) -> list[dict]:
    t_start = time.time()
    integration_id = installed.integration_id
    now = datetime.utcnow()
    cache = session.exec(
        select(ToolCache)
        .where(ToolCache.org_id == installed.org_id)
        .where(ToolCache.integration_id == integration_id)
    ).first()

    if cache and (now - cache.fetched_at) < CACHE_TTL:
        age_s = (now - cache.fetched_at).total_seconds()
        logger.info(
            "tool_cache HIT %s (org=%s) age=%.1fs dur=%dms",
            integration_id,
            installed.org_id,
            age_s,
            int((time.time() - t_start) * 1000),
        )
        return json.loads(cache.tools_json)

    waited_tools = await _wait_for_in_progress_refresh(installed, session)
    if waited_tools is not None:
        return waited_tools

    miss_reason = (
        "no_row" if not cache else f"stale({(now - cache.fetched_at).total_seconds():.0f}s)"
    )
    logger.info(
        "tool_cache MISS %s (org=%s) reason=%s - fetching upstream",
        integration_id,
        installed.org_id,
        miss_reason,
    )

    # Pre-flight: refresh if token is known to be expired
    if (
        installed.auth_method == "oauth"
        and oauth_state
        and oauth_refresh.is_token_expired(oauth_state)
    ):
        refreshed = await oauth_refresh.refresh_tokens(oauth_state)
        if refreshed:
            oauth_state = refreshed

    # API integrations define tools statically - no remote call needed.
    bundled = integration_registry.get(integration_id)
    is_api = isinstance(bundled, CustomIntegration)

    tools: list[dict] | None = None
    last_error: Exception | None = None

    t_upstream = time.time()
    if is_api:
        tools = api_client.list_tools(bundled)
    else:
        for attempt in range(2):
            try:
                tools = await mcp_client.list_tools(installed, oauth_state)
                last_error = None
                break
            except Exception as e:
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
    upstream_ms = int((time.time() - t_upstream) * 1000)

    if last_error:
        logger.warning(
            "tool_cache upstream FAIL %s (org=%s) upstream=%dms err=%s cache_fallback=%s",
            integration_id,
            installed.org_id,
            upstream_ms,
            last_error,
            bool(cache),
        )
        if cache:
            return json.loads(cache.tools_json)
        raise last_error

    assert tools is not None

    tools_json = json.dumps(tools)
    if cache:
        cache.tools_json = tools_json
        cache.fetched_at = now
        session.add(cache)
    else:
        session.add(
            ToolCache(
                org_id=installed.org_id,
                integration_id=integration_id,
                tools_json=tools_json,
                fetched_at=now,
            )
        )
    session.commit()
    logger.info(
        "tool_cache WRITE %s (org=%s) tools=%d upstream=%dms total=%dms",
        integration_id,
        installed.org_id,
        len(tools),
        upstream_ms,
        int((time.time() - t_start) * 1000),
    )
    return tools


def _annotate_tools(
    tools: list[dict],
    session: Session,
    org_id,
    integration_id: str,
) -> list[dict]:
    execution_modes = _get_execution_modes(session, org_id, integration_id)
    categories: dict[str, str] = {}
    if integration_id:
        bundled = integration_registry.get(integration_id)
        if bundled:
            categories = bundled.tool_categories
    for tool in tools:
        tool_name = tool.get("name", "")
        tool["execution_mode"] = execution_modes.get(tool_name, "require_approval")
        if categories:
            tool["category"] = categories.get(tool_name)
    return tools


@router.get("")
async def list_all_tools(
    session: Session = Depends(get_session),
    agent_auth: AgentAuth = Depends(get_agent_auth),
) -> list[dict]:
    current_org = agent_auth.org
    installed_list = session.exec(
        select(InstalledIntegration).where(InstalledIntegration.org_id == current_org.id)
    ).all()
    all_tools: list[dict] = []
    for installed in installed_list:
        try:
            oauth_state = session.exec(
                select(OAuthState)
                .where(OAuthState.org_id == current_org.id)
                .where(OAuthState.integration_id == installed.integration_id)
            ).first()
            tools = await _get_tools_cached(installed, oauth_state, session)
            for tool in tools:
                tool["integration_id"] = installed.integration_id
            _annotate_tools(tools, session, current_org.id, installed.integration_id)
            all_tools.extend(tools)
        except Exception:
            continue
    return all_tools


@router.get("/{integration_id}")
async def list_tools(
    integration_id: str,
    session: Session = Depends(get_session),
    agent_auth: AgentAuth = Depends(get_agent_auth),
) -> list[dict]:
    current_org = agent_auth.org
    installed = session.exec(
        select(InstalledIntegration)
        .where(InstalledIntegration.org_id == current_org.id)
        .where(InstalledIntegration.integration_id == integration_id)
    ).first()
    if not installed:
        raise HTTPException(
            status_code=404, detail=f"Installed integration '{integration_id}' not found"
        )

    oauth_state = session.exec(
        select(OAuthState)
        .where(OAuthState.org_id == current_org.id)
        .where(OAuthState.integration_id == integration_id)
    ).first()
    try:
        tools = await _get_tools_cached(installed, oauth_state, session)
        return _annotate_tools(tools, session, current_org.id, integration_id)
    except Exception as e:
        logger.warning("Failed to list tools for %s: %s", integration_id, e)
        raise HTTPException(
            status_code=502, detail=f"Failed to list tools for integration '{integration_id}'"
        ) from e


@router.post("/{integration_id}/call")
async def call_tool(
    integration_id: str,
    body: CallToolRequest,
    session: Session = Depends(get_session),
    agent_auth: AgentAuth = Depends(get_agent_auth),
) -> dict:
    current_org = agent_auth.org
    api_key_label = agent_auth.api_key.name if agent_auth.api_key else None
    api_key_prefix = agent_auth.api_key.key_prefix if agent_auth.api_key else None
    impersonator_user_id = (
        agent_auth.impersonator.id if agent_auth.impersonator is not None else None
    )
    installed = session.exec(
        select(InstalledIntegration)
        .where(InstalledIntegration.org_id == current_org.id)
        .where(InstalledIntegration.integration_id == integration_id)
    ).first()
    if not installed:
        raise HTTPException(
            status_code=404, detail=f"Installed integration '{integration_id}' not found"
        )

    # Evaluate approval policy
    decision = evaluate_policy(session, current_org.id, integration_id, body.tool_name, body.args)
    auto_approval_id = None
    consumed_approval = None

    if not decision.allowed:
        if decision.reason == "denied":
            log = LogEntry(
                org_id=current_org.id,
                integration_id=integration_id,
                tool_name=body.tool_name,
                args_json=json.dumps(body.args),
                outcome="denied",
                api_key_label=api_key_label,
                api_key_prefix=api_key_prefix,
                impersonator_user_id=impersonator_user_id,
                additional_info=body.additional_info,
            )
            session.add(log)
            session.commit()
            posthog_client.capture(
                distinct_id=str(current_org.id),
                event="tool_call_denied_by_policy",
                properties={"integration_id": integration_id, "tool_name": body.tool_name},
            )
            return JSONResponse(
                status_code=403,
                content={
                    "error": "denied",
                    "message": "This tool has been blocked and cannot be executed.",
                    "integration_id": integration_id,
                    "tool_name": body.tool_name,
                },
            )

        # Check for a consumable approve-once request
        normalized = normalize_tool_args(body.args)
        args_hash = hash_normalized_args(normalized)
        consumed = try_consume_approved_request(
            session, current_org.id, integration_id, body.tool_name, args_hash
        )
        if not consumed:
            # Create or reuse a pending approval request
            requested_by_agent = f"api_key:{agent_auth.api_key.id}" if agent_auth.api_key else None
            approval_req = get_or_create_approval_request(
                session,
                current_org.id,
                integration_id,
                body.tool_name,
                body.args,
                requested_by_agent=requested_by_agent,
                additional_info=body.additional_info,
            )
            # Only create a log if one doesn't already exist for this approval request.
            # get_or_create_approval_request reuses existing pending requests, so if the
            # agent retries before approval we must not create a duplicate log entry.
            existing_approval_log = session.exec(
                select(LogEntry).where(LogEntry.approval_request_id == approval_req.id)
            ).first()
            if not existing_approval_log:
                log = LogEntry(
                    org_id=current_org.id,
                    integration_id=integration_id,
                    tool_name=body.tool_name,
                    args_json=json.dumps(body.args),
                    outcome="approval_required",
                    approval_request_id=approval_req.id,
                    args_hash=args_hash,
                    api_key_label=api_key_label,
                    api_key_prefix=api_key_prefix,
                    impersonator_user_id=impersonator_user_id,
                    additional_info=body.additional_info,
                )
                session.add(log)
                session.commit()
            approval_url = f"{settings.ui_base_url}/approve/{approval_req.id}"
            return JSONResponse(
                status_code=403,
                content={
                    "error": "approval_required",
                    "approval_request_id": str(approval_req.id),
                    "approval_url": approval_url,
                    "message": (
                        "Tool call requires approval before execution. "
                        "Once you receive this request, share the URL with a human and "
                        "explain that this tool call requires approval, which they can "
                        "give using the link. "
                        f"Then share this link in full: {approval_url}"
                    ),
                    "integration_id": integration_id,
                    "tool_name": body.tool_name,
                },
            )
        consumed_approval = consumed

    if decision.reason == "tool_allowed":
        req_by = f"api_key:{agent_auth.api_key.id}" if agent_auth.api_key else None
        auto_req = create_auto_approved_request(
            session,
            current_org.id,
            integration_id,
            body.tool_name,
            body.args,
            requested_by_agent=req_by,
            api_key_label=api_key_label,
            api_key_prefix=api_key_prefix,
            additional_info=body.additional_info,
        )
        auto_approval_id = auto_req.id

    oauth_state = session.exec(
        select(OAuthState)
        .where(OAuthState.org_id == current_org.id)
        .where(OAuthState.integration_id == integration_id)
    ).first()

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
    bundled_int = integration_registry.get(installed.integration_id)
    is_api = isinstance(bundled_int, CustomIntegration)

    start = time.time()
    result: dict = {}
    last_error: Exception | None = None

    if is_api:
        tool_def = api_client.get_tool_def(bundled_int, body.tool_name)
        if not tool_def:
            raise HTTPException(
                status_code=404,
                detail=f"Tool '{body.tool_name}' not found in integration",
            )
        for attempt in range(2):
            try:
                result = await api_client.call_tool(installed, tool_def, body.args, oauth_state)
                last_error = None
                break
            except Exception as e:
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
                result = await mcp_client.call_tool(
                    installed, body.tool_name, body.args, oauth_state
                )
                last_error = None
                break
            except Exception as e:
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

    duration_ms = int((time.time() - start) * 1000)
    error_str = str(last_error) if last_error else None
    outcome = "error" if last_error else "executed"
    access_reason = "approved_any" if decision.reason == "tool_allowed" else None

    if consumed_approval:
        # Update the existing approval_required/approved log in-place so the full
        # gate → approved → executed lifecycle appears as a single log entry in the UI.
        existing_log = session.exec(
            select(LogEntry).where(LogEntry.approval_request_id == consumed_approval.id)
        ).first()
        if existing_log:
            existing_log.result_json = json.dumps(result) if result else None
            existing_log.error = error_str
            existing_log.duration_ms = duration_ms
            existing_log.outcome = outcome
            if body.additional_info and not existing_log.additional_info:
                existing_log.additional_info = body.additional_info
            if impersonator_user_id is not None and existing_log.impersonator_user_id is None:
                existing_log.impersonator_user_id = impersonator_user_id
            session.add(existing_log)
            session.commit()
        else:
            log = LogEntry(
                org_id=current_org.id,
                integration_id=integration_id,
                tool_name=body.tool_name,
                args_json=json.dumps(body.args),
                result_json=json.dumps(result) if result else None,
                error=error_str,
                duration_ms=duration_ms,
                outcome=outcome,
                approval_request_id=consumed_approval.id,
                access_reason=access_reason,
                api_key_label=api_key_label,
                api_key_prefix=api_key_prefix,
                impersonator_user_id=impersonator_user_id,
                additional_info=body.additional_info,
            )
            session.add(log)
            session.commit()
    else:
        log = LogEntry(
            org_id=current_org.id,
            integration_id=integration_id,
            tool_name=body.tool_name,
            args_json=json.dumps(body.args),
            result_json=json.dumps(result) if result else None,
            error=error_str,
            duration_ms=duration_ms,
            outcome=outcome,
            approval_request_id=auto_approval_id,
            access_reason=access_reason,
            api_key_label=api_key_label,
            api_key_prefix=api_key_prefix,
            impersonator_user_id=impersonator_user_id,
            additional_info=body.additional_info,
        )
        session.add(log)
        session.commit()

    if last_error:
        logger.warning("Tool call failed for %s/%s: %s", integration_id, body.tool_name, last_error)
        raise HTTPException(
            status_code=502,
            detail=f"Tool call to '{body.tool_name}' on integration '{integration_id}' failed",
        ) from last_error

    # Separate event for impersonated calls so downstream billing and usage
    # analytics can filter them out of the target's attribution.
    event_name = "tool_called_impersonated" if impersonator_user_id else "tool_called"
    posthog_client.capture(
        distinct_id=str(current_org.id),
        event=event_name,
        properties={
            "integration_id": integration_id,
            "tool_name": body.tool_name,
            "duration_ms": duration_ms,
            "access_reason": access_reason,
            "impersonator_user_id": str(impersonator_user_id) if impersonator_user_id else None,
        },
    )
    return result
