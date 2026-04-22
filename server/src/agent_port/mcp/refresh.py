import asyncio
import json
import logging
from datetime import datetime

from sqlmodel import Session, select

from agent_port import api_client
from agent_port.db import engine
from agent_port.integrations import registry as integration_registry
from agent_port.integrations.types import CustomIntegration
from agent_port.mcp import client as mcp_client
from agent_port.mcp import oauth as oauth_refresh
from agent_port.mcp.notifications import notify_tools_changed
from agent_port.models.integration import InstalledIntegration
from agent_port.models.oauth import OAuthState
from agent_port.models.tool_cache import CACHE_TTL, ToolCache

logger = logging.getLogger(__name__)

REFRESH_INTERVAL = 3600  # seconds


async def _refresh_all() -> None:
    with Session(engine) as session:
        integrations = session.exec(select(InstalledIntegration)).all()
        for installed in integrations:
            try:
                now = datetime.utcnow()
                cache = session.exec(
                    select(ToolCache)
                    .where(ToolCache.org_id == installed.org_id)
                    .where(ToolCache.integration_id == installed.integration_id)
                ).first()
                if cache and (now - cache.fetched_at) < CACHE_TTL:
                    continue

                if not installed.connected:
                    logger.debug(
                        "Skipping tool cache refresh for %s (org %s): auth not completed",
                        installed.integration_id,
                        installed.org_id,
                    )
                    continue

                # API integrations define tools statically — no remote call.
                bundled = integration_registry.get(installed.integration_id)
                is_api = isinstance(bundled, CustomIntegration)

                if is_api:
                    tools = api_client.list_tools(bundled)
                else:
                    oauth_state = session.exec(
                        select(OAuthState)
                        .where(OAuthState.org_id == installed.org_id)
                        .where(OAuthState.integration_id == installed.integration_id)
                    ).first()

                    if (
                        installed.auth_method == "oauth"
                        and oauth_state
                        and oauth_refresh.is_token_expired(oauth_state)
                    ):
                        refreshed = await oauth_refresh.refresh_tokens(oauth_state)
                        if refreshed:
                            oauth_state = refreshed

                    tools: list[dict] = []
                    for attempt in range(2):
                        try:
                            tools = await mcp_client.list_tools(installed, oauth_state)
                            break
                        except Exception as e:
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
                            raise

                tools_json = json.dumps(tools)
                if cache:
                    cache.tools_json = tools_json
                    cache.fetched_at = now
                    session.add(cache)
                else:
                    session.add(
                        ToolCache(
                            org_id=installed.org_id,
                            integration_id=installed.integration_id,
                            tools_json=tools_json,
                            fetched_at=now,
                        )
                    )
                session.commit()
                logger.info(
                    "Refreshed tool cache: %s (org %s)", installed.integration_id, installed.org_id
                )
            except Exception:
                logger.exception(
                    "Tool cache refresh failed: %s (org %s)",
                    installed.integration_id,
                    installed.org_id,
                )


async def refresh_one(org_id, integration_id: str) -> None:
    """Refresh the tool cache for a single integration. Safe to fire-and-forget.

    Sets updating_tool_cache=True at the start and clears it when done (even on error),
    so callers can poll that flag to know when a refresh is in progress.
    """
    with Session(engine) as session:
        installed = session.exec(
            select(InstalledIntegration)
            .where(InstalledIntegration.org_id == org_id)
            .where(InstalledIntegration.integration_id == integration_id)
        ).first()
        if not installed or not installed.connected:
            return

        installed.updating_tool_cache = True
        session.add(installed)
        session.commit()

        bundled = integration_registry.get(installed.integration_id)
        is_api = isinstance(bundled, CustomIntegration)
        oauth_state = None

        if not is_api:
            oauth_state = session.exec(
                select(OAuthState)
                .where(OAuthState.org_id == org_id)
                .where(OAuthState.integration_id == integration_id)
            ).first()

            if (
                installed.auth_method == "oauth"
                and oauth_state
                and oauth_refresh.is_token_expired(oauth_state)
            ):
                refreshed = await oauth_refresh.refresh_tokens(oauth_state)
                if refreshed:
                    oauth_state = refreshed

        try:
            if is_api:
                tools = api_client.list_tools(bundled)
            else:
                tools: list[dict] = []
                for attempt in range(2):
                    try:
                        tools = await mcp_client.list_tools(installed, oauth_state)
                        break
                    except Exception as exc:
                        if (
                            attempt == 0
                            and installed.auth_method == "oauth"
                            and oauth_state
                            and oauth_refresh.is_auth_error(exc)
                        ):
                            refreshed = await oauth_refresh.refresh_tokens(oauth_state)
                            if refreshed:
                                oauth_state = refreshed
                                continue
                        raise

            now = datetime.utcnow()
            tools_json = json.dumps(tools)
            cache = session.exec(
                select(ToolCache)
                .where(ToolCache.org_id == org_id)
                .where(ToolCache.integration_id == integration_id)
            ).first()
            if cache:
                cache.tools_json = tools_json
                cache.fetched_at = now
                session.add(cache)
            else:
                session.add(
                    ToolCache(
                        org_id=org_id,
                        integration_id=integration_id,
                        tools_json=tools_json,
                        fetched_at=now,
                    )
                )
            session.commit()
            logger.info("Refreshed tool cache: %s (org %s)", integration_id, org_id)
            notified_org_id = org_id
        except Exception:
            logger.exception("Tool cache refresh failed: %s (org %s)", integration_id, org_id)
            notified_org_id = None
        finally:
            installed.updating_tool_cache = False
            session.add(installed)
            session.commit()

    # After releasing the DB session: push tools/list_changed to live MCP
    # sessions for this org so their cached tool lists get re-fetched.
    if notified_org_id is not None:
        await notify_tools_changed(notified_org_id)


async def tool_cache_refresh_loop() -> None:
    logger.info("Running initial tool cache refresh")
    await _refresh_all()
    while True:
        await asyncio.sleep(REFRESH_INTERVAL)
        logger.info("Running background tool cache refresh")
        await _refresh_all()
