"""Per-org registry of live MCP sessions and the `tools/list_changed` notifier.

In stateful StreamableHTTP mode each client holds a persistent `ServerSession`.
When an integration is installed, connected, or removed, we push
`notifications/tools/list_changed` down every live session bound to that org so
the client re-fetches its cached tool list instead of waiting for a reconnect.

Sessions are tracked in a WeakSet so they drop out automatically once the
underlying session task exits; failed sends are also pruned eagerly.
"""

from __future__ import annotations

import logging
import uuid
import weakref

from mcp.server.session import ServerSession

logger = logging.getLogger(__name__)

_sessions_by_org: dict[uuid.UUID, weakref.WeakSet[ServerSession]] = {}


def register_session(org_id: uuid.UUID, session: ServerSession) -> None:
    bucket = _sessions_by_org.get(org_id)
    if bucket is None:
        bucket = weakref.WeakSet()
        _sessions_by_org[org_id] = bucket
    bucket.add(session)


async def notify_tools_changed(org_id: uuid.UUID) -> None:
    """Push `notifications/tools/list_changed` to every live session for the org.

    Sessions that fail the send (closed, crashed) are dropped from the registry.
    Safe to call from any async context; never raises.
    """
    bucket = _sessions_by_org.get(org_id)
    if not bucket:
        return
    for session in list(bucket):
        try:
            await session.send_tool_list_changed()
        except Exception:
            logger.debug(
                "notify_tools_changed: dropping dead session for org %s", org_id, exc_info=True
            )
            bucket.discard(session)
    if not bucket:
        _sessions_by_org.pop(org_id, None)
