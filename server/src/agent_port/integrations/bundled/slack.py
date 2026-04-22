from typing import Union

import httpx
from pydantic import Field

from agent_port.integrations.types import (
    ApiTool,
    AuthMethod,
    CustomIntegration,
    OAuthAuth,
    Param,
    TokenAuth,
)

_SLACK_OAUTH = OAuthAuth(
    method="oauth",
    provider="slack",
    authorization_url="https://slack.com/oauth/v2/authorize",
    token_url="https://slack.com/api/oauth.v2.access",
    scope_param="user_scope",
    scopes=[
        "search:read",
        "channels:read",
        "channels:history",
        "groups:read",
        "groups:history",
        "im:read",
        "im:history",
        "mpim:read",
        "mpim:history",
        "chat:write",
        "users:read",
        "users:read.email",
        "users.profile:read",
        "canvases:read",
        "canvases:write",
    ],
)

_SLACK_TOKEN = TokenAuth(
    method="token",
    label="Slack Bot Token",
    header="Authorization",
    format="Bearer {token}",
)

_TOOL_CATEGORIES: dict[str, str] = {
    # Search
    "search_messages": "Search",
    "search_files": "Search",
    # Channels
    "list_channels": "Channels",
    "get_channel_info": "Channels",
    # Messages
    "send_message": "Messages",
    "read_channel_history": "Messages",
    "read_thread": "Messages",
    # Users
    "list_users": "Users",
    "get_user_info": "Users",
    "get_user_profile": "Users",
    "lookup_user_by_email": "Users",
    # Canvases
    "create_canvas": "Canvases",
    "update_canvas": "Canvases",
    "read_canvas": "Canvases",
}

_TOOLS: list[ApiTool] = [
    # ── Search ────────────────────────────────────────────────────────────
    ApiTool(
        name="search_messages",
        description=(
            "Search for messages across the workspace. Supports Slack search modifiers "
            "like from:, in:, has:, before:, after:, and more."
        ),
        method="GET",
        path="/search.messages",
        params=[
            Param(name="query", required=True, query=True, description="Search query string"),
            Param(
                name="sort",
                query=True,
                enum=["score", "timestamp"],
                description="Sort order (default: score)",
            ),
            Param(
                name="sort_dir",
                query=True,
                enum=["asc", "desc"],
                description="Sort direction (default: desc)",
            ),
            Param(
                name="count",
                type="integer",
                query=True,
                description="Number of results per page (default 20, max 100)",
            ),
            Param(name="page", type="integer", query=True, description="Page number (default 1)"),
        ],
    ),
    ApiTool(
        name="search_files",
        description=(
            "Search for files shared in the workspace. Supports Slack search modifiers "
            "like from:, in:, type:, before:, after:."
        ),
        method="GET",
        path="/search.files",
        params=[
            Param(name="query", required=True, query=True, description="Search query string"),
            Param(
                name="sort",
                query=True,
                enum=["score", "timestamp"],
                description="Sort order (default: score)",
            ),
            Param(
                name="sort_dir",
                query=True,
                enum=["asc", "desc"],
                description="Sort direction (default: desc)",
            ),
            Param(
                name="count",
                type="integer",
                query=True,
                description="Number of results per page (default 20, max 100)",
            ),
            Param(name="page", type="integer", query=True, description="Page number (default 1)"),
        ],
    ),
    # ── Channels ──────────────────────────────────────────────────────────
    ApiTool(
        name="list_channels",
        description=(
            "List conversations (channels, DMs, group DMs) in the workspace. "
            "Use the types parameter to filter by conversation type."
        ),
        method="GET",
        path="/conversations.list",
        params=[
            Param(
                name="types",
                query=True,
                description=(
                    "Comma-separated list of channel types to include: "
                    "public_channel, private_channel, mpim, im (default: public_channel)"
                ),
            ),
            Param(
                name="limit",
                type="integer",
                query=True,
                description="Maximum number of channels to return (default 100, max 1000)",
            ),
            Param(name="cursor", query=True, description="Pagination cursor for next page"),
            Param(
                name="exclude_archived",
                type="boolean",
                query=True,
                description="Exclude archived channels (default true)",
            ),
            Param(
                name="team_id",
                query=True,
                description="Team ID to list channels from (required for org-wide apps)",
            ),
        ],
    ),
    ApiTool(
        name="get_channel_info",
        description="Get detailed information about a specific channel, DM, or group DM.",
        method="GET",
        path="/conversations.info",
        params=[
            Param(name="channel", required=True, query=True, description="Channel ID"),
            Param(
                name="include_num_members",
                type="boolean",
                query=True,
                description="Include the number of members in the channel",
            ),
        ],
    ),
    # ── Messages ──────────────────────────────────────────────────────────
    ApiTool(
        name="send_message",
        description=(
            "Send a message to a channel, DM, or thread. Supports plain text and "
            "Block Kit for rich formatting. To reply in a thread, include thread_ts."
        ),
        method="POST",
        path="/chat.postMessage",
        params=[
            Param(
                name="channel",
                required=True,
                description="Channel ID, DM ID, or user ID to send the message to",
            ),
            Param(name="text", required=True, description="Message text (supports Slack mrkdwn)"),
            Param(
                name="blocks",
                schema_override={
                    "type": "array",
                    "description": (
                        "Block Kit blocks for rich message formatting. "
                        "See https://api.slack.com/block-kit"
                    ),
                    "items": {"type": "object"},
                },
            ),
            Param(
                name="thread_ts",
                description="Timestamp of the parent message to reply in a thread",
            ),
            Param(
                name="reply_broadcast",
                type="boolean",
                description="When replying in a thread, also post to the channel",
            ),
            Param(
                name="unfurl_links",
                type="boolean",
                description="Enable or disable URL unfurling",
            ),
            Param(
                name="unfurl_media",
                type="boolean",
                description="Enable or disable media unfurling",
            ),
            Param(
                name="mrkdwn",
                type="boolean",
                description="Enable Slack mrkdwn parsing in the text field (default true)",
            ),
        ],
    ),
    ApiTool(
        name="read_channel_history",
        description=(
            "Retrieve message history from a channel, DM, or group DM. "
            "Returns messages in reverse chronological order."
        ),
        method="GET",
        path="/conversations.history",
        params=[
            Param(name="channel", required=True, query=True, description="Channel ID"),
            Param(
                name="limit",
                type="integer",
                query=True,
                description="Number of messages to return (default 100, max 1000)",
            ),
            Param(name="cursor", query=True, description="Pagination cursor for next page"),
            Param(
                name="latest",
                query=True,
                description="End of time range (Unix timestamp or message ts). Default: now",
            ),
            Param(
                name="oldest",
                query=True,
                description="Start of time range (Unix timestamp or message ts). Default: 0",
            ),
            Param(
                name="inclusive",
                type="boolean",
                query=True,
                description="Include messages with oldest or latest timestamps",
            ),
        ],
    ),
    ApiTool(
        name="read_thread",
        description="Retrieve all replies in a message thread.",
        method="GET",
        path="/conversations.replies",
        params=[
            Param(name="channel", required=True, query=True, description="Channel ID"),
            Param(
                name="ts",
                required=True,
                query=True,
                description="Timestamp of the parent message",
            ),
            Param(
                name="limit",
                type="integer",
                query=True,
                description="Number of replies to return (default 1000, max 1000)",
            ),
            Param(name="cursor", query=True, description="Pagination cursor for next page"),
            Param(
                name="latest",
                query=True,
                description="End of time range (Unix timestamp)",
            ),
            Param(
                name="oldest",
                query=True,
                description="Start of time range (Unix timestamp)",
            ),
            Param(
                name="inclusive",
                type="boolean",
                query=True,
                description="Include messages with oldest or latest timestamps",
            ),
        ],
    ),
    # ── Users ─────────────────────────────────────────────────────────────
    ApiTool(
        name="list_users",
        description="List all users in the workspace. Returns profiles, statuses, and roles.",
        method="GET",
        path="/users.list",
        params=[
            Param(
                name="limit",
                type="integer",
                query=True,
                description="Number of users to return per page (default 200, max 200)",
            ),
            Param(name="cursor", query=True, description="Pagination cursor for next page"),
            Param(
                name="team_id",
                query=True,
                description="Team ID (required for org-wide apps)",
            ),
        ],
    ),
    ApiTool(
        name="get_user_info",
        description=(
            "Get detailed information about a user, including their profile, "
            "status, timezone, and admin status."
        ),
        method="GET",
        path="/users.info",
        params=[
            Param(name="user", required=True, query=True, description="User ID"),
        ],
    ),
    ApiTool(
        name="get_user_profile",
        description=(
            "Get a user's full profile including custom profile fields, "
            "status text, status emoji, and display name."
        ),
        method="GET",
        path="/users.profile.get",
        params=[
            Param(name="user", required=True, query=True, description="User ID"),
        ],
    ),
    ApiTool(
        name="lookup_user_by_email",
        description="Find a user by their email address.",
        method="GET",
        path="/users.lookupByEmail",
        params=[
            Param(name="email", required=True, query=True, description="Email address to look up"),
        ],
    ),
    # ── Canvases ──────────────────────────────────────────────────────────
    ApiTool(
        name="create_canvas",
        description="Create a new Slack canvas with markdown content.",
        method="POST",
        path="/canvases.create",
        params=[
            Param(name="title", required=True, description="Canvas title"),
            Param(
                name="document_content",
                required=True,
                schema_override={
                    "type": "object",
                    "description": "Canvas content",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["markdown"],
                            "description": "Content type (use 'markdown')",
                        },
                        "markdown": {
                            "type": "string",
                            "description": "Markdown content for the canvas",
                        },
                    },
                    "required": ["type", "markdown"],
                },
            ),
        ],
    ),
    ApiTool(
        name="update_canvas",
        description=(
            "Edit an existing Slack canvas. Supports inserting, replacing, and deleting sections."
        ),
        method="POST",
        path="/canvases.edit",
        params=[
            Param(name="canvas_id", required=True, description="Canvas ID to edit"),
            Param(
                name="changes",
                required=True,
                schema_override={
                    "type": "array",
                    "description": "List of changes to apply to the canvas",
                    "items": {
                        "type": "object",
                        "properties": {
                            "operation": {
                                "type": "string",
                                "enum": [
                                    "insert_at_start",
                                    "insert_at_end",
                                    "insert_before_section",
                                    "insert_after_section",
                                    "replace_section",
                                    "delete_section",
                                ],
                                "description": "The edit operation to perform",
                            },
                            "section_id": {
                                "type": "string",
                                "description": (
                                    "Target section ID (required for insert_before_section, "
                                    "insert_after_section, replace_section, delete_section)"
                                ),
                            },
                            "document_content": {
                                "type": "object",
                                "description": "Content for insert/replace operations",
                                "properties": {
                                    "type": {
                                        "type": "string",
                                        "enum": ["markdown"],
                                    },
                                    "markdown": {"type": "string"},
                                },
                                "required": ["type", "markdown"],
                            },
                        },
                        "required": ["operation"],
                    },
                },
            ),
        ],
    ),
    ApiTool(
        name="read_canvas",
        description="Read canvas content by looking up its sections. Returns sections as markdown.",
        method="POST",
        path="/canvases.sections.lookup",
        params=[
            Param(name="canvas_id", required=True, description="Canvas ID to read"),
            Param(
                name="criteria",
                required=True,
                schema_override={
                    "type": "object",
                    "description": "Criteria for which sections to return",
                    "properties": {
                        "section_types": {
                            "type": "array",
                            "description": (
                                "Types of sections to return: "
                                "any_header, h1, h2, h3, or empty for all"
                            ),
                            "items": {"type": "string"},
                        },
                        "contains_text": {
                            "type": "string",
                            "description": "Only return sections containing this text",
                        },
                    },
                },
            ),
        ],
    ),
]


class SlackIntegration(CustomIntegration):
    id: str = "slack"
    name: str = "Slack"
    description: str = (
        "Search messages and files, send and read messages, "
        "manage canvases, and access user profiles"
    )
    docs_url: str = "https://api.slack.com/methods"
    base_url: str = "https://slack.com/api"
    auth: list[AuthMethod] = Field(default=[_SLACK_OAUTH, _SLACK_TOKEN])
    tools: list[Union[ApiTool]] = Field(default=_TOOLS)
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)

    async def validate_auth(self, token: str) -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                "https://slack.com/api/auth.test",
                headers={"Authorization": f"Bearer {token}"},
            )
        data = r.json() if r.status_code < 500 else {}
        if not data.get("ok"):
            raise ValueError(f"Slack rejected the token: {data.get('error', 'unknown')}")
