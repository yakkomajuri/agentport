"""Resend broadcast tools: create, send, manage, and compose campaigns."""

from agent_port.integrations.types import ApiTool, Param

_PAGINATION_PARAMS = [
    Param(name="limit", type="integer", query=True, description="Max results (1-100)"),
    Param(name="after", query=True, description="Cursor for next page"),
    Param(name="before", query=True, description="Cursor for previous page"),
]

TOOLS: list[ApiTool] = [
    ApiTool(
        name="create_broadcast",
        description=(
            "Create a broadcast campaign (one email sent to an entire segment). "
            "This does NOT send the broadcast; use send_broadcast after creating."
        ),
        method="POST",
        path="/broadcasts",
        params=[
            Param(name="name", description="Broadcast name (auto-generated if omitted)"),
            Param(name="segmentId", required=True, description="Target segment ID"),
            Param(name="subject", required=True, description="Email subject line"),
            Param(name="text", required=True, description="Plain text body"),
            Param(name="html", description="HTML body"),
            Param(name="previewText", description="Preview text shown in inbox"),
            Param(name="from", description="Sender address (required if not pre-configured)"),
            Param(name="replyTo", description="Reply-to address"),
        ],
    ),
    ApiTool(
        name="send_broadcast",
        description="Send or schedule an existing broadcast by ID.",
        method="POST",
        path="/broadcasts/{broadcastId}/send",
        params=[
            Param(
                name="broadcastId",
                required=True,
                description="Broadcast ID or Resend dashboard URL",
            ),
            Param(
                name="scheduledAt",
                description="Schedule time as ISO 8601 or natural language (omit to send now)",
            ),
        ],
    ),
    ApiTool(
        name="list_broadcasts",
        description="List all broadcast campaigns with ID, name, audience, status, and timestamps.",
        method="GET",
        path="/broadcasts",
        params=_PAGINATION_PARAMS,
    ),
    ApiTool(
        name="get_broadcast",
        description="Retrieve full details of a specific broadcast.",
        method="GET",
        path="/broadcasts/{broadcastId}",
        params=[
            Param(
                name="broadcastId",
                required=True,
                description="Broadcast ID or Resend dashboard URL",
            ),
        ],
    ),
    ApiTool(
        name="update_broadcast",
        description=(
            "Update broadcast metadata including name, subject, sender, "
            "HTML, text, audience, reply-to, and preview text."
        ),
        method="PATCH",
        path="/broadcasts/{broadcastId}",
        params=[
            Param(name="broadcastId", required=True, description="Broadcast ID"),
            Param(name="audienceId", required=True, description="Target audience ID"),
            Param(name="name", description="Updated name"),
            Param(name="segmentId", description="New target segment ID"),
            Param(name="from", description="Updated sender address"),
            Param(name="html", description="Updated HTML body"),
            Param(name="text", description="Updated plain text body"),
            Param(name="subject", description="Updated subject line"),
            Param(name="replyTo", description="Updated reply-to address"),
            Param(name="previewText", description="Updated preview text"),
        ],
    ),
    ApiTool(
        name="remove_broadcast",
        description="Remove a broadcast by ID or Resend dashboard URL.",
        method="DELETE",
        path="/broadcasts/{broadcastId}",
        params=[
            Param(
                name="broadcastId",
                required=True,
                description="Broadcast ID or Resend dashboard URL",
            ),
        ],
    ),
]
