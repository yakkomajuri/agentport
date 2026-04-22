"""Resend management tools: API keys, webhooks, and logs."""

from agent_port.integrations.types import ApiTool, Param

_PAGINATION_PARAMS = [
    Param(name="limit", type="integer", query=True, description="Max results (1-100)"),
    Param(name="after", query=True, description="Cursor for next page"),
    Param(name="before", query=True, description="Cursor for previous page"),
]

# ---------------------------------------------------------------------------
# Webhook event types
# ---------------------------------------------------------------------------

_WEBHOOK_EVENTS_SCHEMA = {
    "type": "array",
    "description": "Event types to subscribe to (minimum 1)",
    "items": {
        "type": "string",
        "enum": [
            "email.sent",
            "email.delivered",
            "email.delivery_delayed",
            "email.complained",
            "email.bounced",
            "email.opened",
            "email.clicked",
            "contact.created",
            "contact.updated",
            "contact.deleted",
        ],
    },
    "minItems": 1,
}

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS: list[ApiTool] = [
    # ── API Keys ─────────────────────────────────────────────────────────
    ApiTool(
        name="create_api_key",
        description=("Create a new API key. The full token is only shown once in the response."),
        method="POST",
        path="/api-keys",
        params=[
            Param(name="name", required=True, description="API key name (max 50 chars)"),
            Param(
                name="permission",
                enum=["full_access", "sending_access"],
                description="Permission level",
            ),
            Param(
                name="domainId",
                description="Restrict to a specific domain (only with sending_access)",
            ),
        ],
    ),
    ApiTool(
        name="list_api_keys",
        description="List all API keys with names, IDs, and creation dates.",
        method="GET",
        path="/api-keys",
        params=_PAGINATION_PARAMS,
    ),
    ApiTool(
        name="remove_api_key",
        description="Remove an API key by ID.",
        method="DELETE",
        path="/api-keys/{id}",
        params=[
            Param(name="id", required=True, description="API key ID"),
        ],
    ),
    # ── Webhooks ─────────────────────────────────────────────────────────
    ApiTool(
        name="create_webhook",
        description="Create a webhook to receive event notifications at an endpoint URL.",
        method="POST",
        path="/webhooks",
        params=[
            Param(name="endpoint", required=True, description="Webhook endpoint URL"),
            Param(name="events", required=True, schema_override=_WEBHOOK_EVENTS_SCHEMA),
        ],
    ),
    ApiTool(
        name="list_webhooks",
        description="List all webhooks.",
        method="GET",
        path="/webhooks",
        params=[],
    ),
    ApiTool(
        name="get_webhook",
        description="Get a webhook by ID.",
        method="GET",
        path="/webhooks/{webhookId}",
        params=[
            Param(name="webhookId", required=True, description="Webhook ID"),
        ],
    ),
    ApiTool(
        name="update_webhook",
        description="Update webhook endpoint, events, or status.",
        method="PATCH",
        path="/webhooks/{webhookId}",
        params=[
            Param(name="webhookId", required=True, description="Webhook ID"),
            Param(name="endpoint", description="Updated endpoint URL"),
            Param(name="events", schema_override=_WEBHOOK_EVENTS_SCHEMA),
            Param(
                name="status",
                enum=["enabled", "disabled"],
                description="Enable or disable the webhook",
            ),
        ],
    ),
    ApiTool(
        name="remove_webhook",
        description="Remove a webhook by ID.",
        method="DELETE",
        path="/webhooks/{webhookId}",
        params=[
            Param(name="webhookId", required=True, description="Webhook ID"),
        ],
    ),
    # ── Logs ─────────────────────────────────────────────────────────────
    ApiTool(
        name="list_logs",
        description="List API request logs for your Resend account.",
        method="GET",
        path="/logs",
        params=_PAGINATION_PARAMS,
    ),
    ApiTool(
        name="get_log",
        description="Get detailed API request log with full request and response bodies.",
        method="GET",
        path="/logs/{logId}",
        params=[
            Param(name="logId", required=True, description="Log entry ID"),
        ],
    ),
]
