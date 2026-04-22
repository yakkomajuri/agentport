"""Resend email tools: send, receive, list, and manage email attachments."""

from typing import Union

import httpx

from agent_port.integrations.bundled.resend._http import _BASE_URL, response_to_result
from agent_port.integrations.types import ApiTool, CustomTool, Param

# ---------------------------------------------------------------------------
# Pagination params reused across list endpoints
# ---------------------------------------------------------------------------

_PAGINATION_PARAMS = [
    Param(
        name="limit",
        type="integer",
        query=True,
        description="Max results to return (1-100)",
    ),
    Param(name="after", query=True, description="Cursor for next page"),
    Param(name="before", query=True, description="Cursor for previous page"),
]

# ---------------------------------------------------------------------------
# Attachment schema for send_email
# ---------------------------------------------------------------------------

_ATTACHMENT_SCHEMA = {
    "type": "array",
    "description": "File attachments (up to 40 MB total)",
    "items": {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "File name"},
            "content": {
                "type": "string",
                "description": "Base64-encoded file content",
            },
            "path": {
                "type": "string",
                "description": "URL to fetch the attachment from (alternative to content)",
            },
            "content_type": {"type": "string", "description": "MIME type"},
        },
        "required": ["filename"],
    },
}

_TAG_SCHEMA = {
    "type": "array",
    "description": "Email tags for tracking",
    "items": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "value": {"type": "string"},
        },
        "required": ["name", "value"],
    },
}

# ---------------------------------------------------------------------------
# Custom tool: send_batch_emails (body is a raw array)
# ---------------------------------------------------------------------------

_BATCH_EMAIL_SCHEMA = {
    "type": "array",
    "description": "Array of 1-100 email objects",
    "items": {
        "type": "object",
        "properties": {
            "from": {"type": "string", "description": "Sender email address"},
            "to": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Recipient email addresses",
            },
            "subject": {"type": "string"},
            "text": {"type": "string", "description": "Plain text body"},
            "html": {"type": "string", "description": "HTML body"},
            "cc": {"type": "array", "items": {"type": "string"}},
            "bcc": {"type": "array", "items": {"type": "string"}},
            "replyTo": {"type": "string"},
            "scheduledAt": {"type": "string", "description": "ISO 8601 or natural language"},
            "tags": _TAG_SCHEMA,
        },
        "required": ["to", "subject"],
    },
}


async def _run_send_batch_emails(args: dict, auth_headers: dict) -> dict:
    emails = args.get("emails", [])
    if not emails:
        return {
            "content": [{"type": "text", "text": "At least one email is required"}],
            "isError": True,
        }
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{_BASE_URL}/emails/batch",
            json=emails,
            headers=auth_headers,
            timeout=30.0,
        )
    return response_to_result(r)


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS: list[Union[ApiTool, CustomTool]] = [
    # ── Send ─────────────────────────────────────────────────────────────
    ApiTool(
        name="send_email",
        description=(
            "Send a single transactional email to one or more recipients. "
            "Supports scheduling, attachments (up to 40 MB), tags, and topic targeting."
        ),
        method="POST",
        path="/emails",
        params=[
            Param(
                name="to",
                required=True,
                type="array",
                items="string",
                description="Recipient email addresses",
            ),
            Param(name="subject", required=True, description="Email subject line"),
            Param(name="text", required=True, description="Plain text email body"),
            Param(name="html", description="HTML email body (optional)"),
            Param(name="from", description="Sender email address (optional if pre-configured)"),
            Param(name="cc", type="array", items="string", description="CC recipients"),
            Param(name="bcc", type="array", items="string", description="BCC recipients"),
            Param(
                name="scheduledAt",
                description="Send time as ISO 8601 or natural language (e.g. 'in 1 hour')",
            ),
            Param(name="attachments", schema_override=_ATTACHMENT_SCHEMA),
            Param(name="tags", schema_override=_TAG_SCHEMA),
            Param(name="topicId", description="Topic ID for subscription management"),
            Param(
                name="replyTo",
                description="Reply-to email address or array of addresses",
            ),
        ],
    ),
    CustomTool(
        name="send_batch_emails",
        description=(
            "Send up to 100 transactional emails in one API call. "
            "Each email object supports the same fields as send_email."
        ),
        params=[
            Param(name="emails", required=True, schema_override=_BATCH_EMAIL_SCHEMA),
        ],
        run=_run_send_batch_emails,
    ),
    # ── Sent emails ──────────────────────────────────────────────────────
    ApiTool(
        name="list_emails",
        description="List recently sent emails with metadata.",
        method="GET",
        path="/emails",
        params=_PAGINATION_PARAMS,
    ),
    ApiTool(
        name="get_email",
        description="Retrieve full details of a sent transactional email by ID.",
        method="GET",
        path="/emails/{id}",
        params=[
            Param(name="id", required=True, description="Email ID"),
        ],
    ),
    ApiTool(
        name="cancel_email",
        description="Cancel a scheduled email before it is sent.",
        method="POST",
        path="/emails/{id}/cancel",
        params=[
            Param(name="id", required=True, description="Scheduled email ID"),
        ],
    ),
    ApiTool(
        name="update_email",
        description="Reschedule a scheduled email by updating its send time.",
        method="PATCH",
        path="/emails/{id}",
        params=[
            Param(name="id", required=True, description="Scheduled email ID"),
            Param(
                name="scheduled_at",
                required=True,
                description="New send time in ISO 8601 format",
            ),
        ],
    ),
    # ── Received emails ──────────────────────────────────────────────────
    ApiTool(
        name="list_received_emails",
        description="List emails received by your Resend receiving address.",
        method="GET",
        path="/received-emails",
        params=_PAGINATION_PARAMS,
    ),
    ApiTool(
        name="get_received_email",
        description="Get full details of a received email including headers and raw download URL.",
        method="GET",
        path="/received-emails/{id}",
        params=[
            Param(name="id", required=True, description="Received email ID"),
        ],
    ),
    # ── Received email attachments ───────────────────────────────────────
    ApiTool(
        name="list_received_email_attachments",
        description="List attachments from a received email with download URLs.",
        method="GET",
        path="/received-emails/{emailId}/attachments",
        params=[
            Param(name="emailId", required=True, description="Received email ID"),
            *_PAGINATION_PARAMS,
        ],
    ),
    ApiTool(
        name="get_received_email_attachment",
        description="Retrieve a specific attachment from a received email with download URL.",
        method="GET",
        path="/received-emails/{emailId}/attachments/{id}",
        params=[
            Param(name="emailId", required=True, description="Received email ID"),
            Param(name="id", required=True, description="Attachment ID"),
        ],
    ),
    # ── Sent email attachments ───────────────────────────────────────────
    ApiTool(
        name="list_sent_email_attachments",
        description="List attachments from a sent email with download URLs.",
        method="GET",
        path="/emails/{emailId}/attachments",
        params=[
            Param(name="emailId", required=True, description="Sent email ID"),
            *_PAGINATION_PARAMS,
        ],
    ),
    ApiTool(
        name="get_sent_email_attachment",
        description="Retrieve a specific attachment from a sent email with download URL.",
        method="GET",
        path="/emails/{emailId}/attachments/{id}",
        params=[
            Param(name="emailId", required=True, description="Sent email ID"),
            Param(name="id", required=True, description="Attachment ID"),
        ],
    ),
]
