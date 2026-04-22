import base64
import json
from email.message import EmailMessage
from typing import Union

import httpx
from pydantic import Field

from agent_port.integrations.types import (
    ApiTool,
    AuthMethod,
    CustomIntegration,
    CustomTool,
    OAuthAuth,
    Param,
)

_GMAIL_OAUTH = OAuthAuth(
    method="oauth",
    provider="google",
    authorization_url="https://accounts.google.com/o/oauth2/v2/auth",
    token_url="https://oauth2.googleapis.com/token",
    scopes=["https://www.googleapis.com/auth/gmail.modify"],
    extra_auth_params={"access_type": "offline", "prompt": "consent"},
)

_TOOL_CATEGORIES: dict[str, str] = {
    "search_emails": "Messages",
    "get_email": "Messages",
    "send_email": "Messages",
    "trash_email": "Messages",
    "untrash_email": "Messages",
    "modify_labels": "Messages",
    "get_attachment": "Messages",
    "create_draft": "Drafts",
    "list_drafts": "Drafts",
    "get_draft": "Drafts",
    "update_draft": "Drafts",
    "send_draft": "Drafts",
    "delete_draft": "Drafts",
    "list_labels": "Labels",
    "create_label": "Labels",
    "delete_label": "Labels",
    "list_threads": "Threads",
    "get_thread": "Threads",
}

_BASE_URL = "https://gmail.googleapis.com"

# ---------------------------------------------------------------------------
# MIME helpers (used by CustomTool run functions below)
# ---------------------------------------------------------------------------


def _gmail_compose(args: dict) -> dict:
    """Build a Gmail-compatible raw message from structured fields."""
    msg = EmailMessage()
    msg["To"] = args["to"]
    msg["Subject"] = args["subject"]
    if args.get("cc"):
        msg["Cc"] = args["cc"]
    if args.get("bcc"):
        msg["Bcc"] = args["bcc"]
    if args.get("in_reply_to"):
        msg["In-Reply-To"] = args["in_reply_to"]
    if args.get("references"):
        msg["References"] = args["references"]

    if args.get("html_body"):
        msg.set_content(args.get("body", ""))
        msg.add_alternative(args["html_body"], subtype="html")
    else:
        msg.set_content(args["body"])

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    result: dict = {"raw": raw}
    if args.get("thread_id"):
        result["threadId"] = args["thread_id"]
    return result


def _response_to_result(response: httpx.Response) -> dict:
    if response.status_code >= 400:
        error_text = response.text
        try:
            error_text = json.dumps(response.json())
        except Exception:
            pass
        return {
            "content": [
                {"type": "text", "text": f"API error ({response.status_code}): {error_text}"}
            ],
            "isError": True,
        }
    try:
        return {
            "content": [{"type": "text", "text": json.dumps(response.json(), indent=2)}],
            "isError": False,
        }
    except Exception:
        return {
            "content": [{"type": "text", "text": response.text or "(empty response)"}],
            "isError": False,
        }


# ---------------------------------------------------------------------------
# Custom tool run functions
# ---------------------------------------------------------------------------

_COMPOSE_PARAMS = [
    Param(name="to", required=True, description="Recipient email address(es), comma-separated"),
    Param(name="subject", required=True, description="Email subject line"),
    Param(name="body", required=True, description="Email body (plain text)"),
    Param(name="cc", description="CC recipients, comma-separated"),
    Param(name="bcc", description="BCC recipients, comma-separated"),
    Param(name="html_body", description="HTML email body (optional, sent alongside plain text)"),
    Param(name="thread_id", description="Thread ID to reply within (get from get_email)"),
    Param(name="in_reply_to", description="Message-ID header of the email being replied to"),
    Param(name="references", description="References header for threading"),
]


async def _run_send_email(args: dict, auth_headers: dict) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{_BASE_URL}/gmail/v1/users/me/messages/send",
            json=_gmail_compose(args),
            headers=auth_headers,
            timeout=30.0,
        )
    return _response_to_result(r)


async def _run_create_draft(args: dict, auth_headers: dict) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{_BASE_URL}/gmail/v1/users/me/drafts",
            json={"message": _gmail_compose(args)},
            headers=auth_headers,
            timeout=30.0,
        )
    return _response_to_result(r)


async def _run_update_draft(args: dict, auth_headers: dict) -> dict:
    draft_id = args["id"]
    async with httpx.AsyncClient() as client:
        r = await client.put(
            f"{_BASE_URL}/gmail/v1/users/me/drafts/{draft_id}",
            json={"message": _gmail_compose(args)},
            headers=auth_headers,
            timeout=30.0,
        )
    return _response_to_result(r)


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

_TOOLS: list[Union[ApiTool, CustomTool]] = [
    # ── Messages ──────────────────────────────────────────────────────────
    ApiTool(
        name="search_emails",
        description=(
            "Search and list emails. Use the 'q' parameter for Gmail search syntax "
            "(e.g. 'from:alice subject:meeting is:unread'). Returns message IDs and thread IDs."
        ),
        method="GET",
        path="/gmail/v1/users/me/messages",
        params=[
            Param(
                name="q", query=True, description="Gmail search query (e.g. 'from:alice is:unread')"
            ),
            Param(
                name="maxResults",
                type="integer",
                query=True,
                description="Maximum number of results (default 10, max 500)",
                default=10,
            ),
            Param(
                name="labelIds",
                query=True,
                description="Label ID to filter by (e.g. 'INBOX', 'SENT', 'DRAFT')",
            ),
            Param(name="pageToken", query=True, description="Token for pagination"),
            Param(
                name="includeSpamTrash",
                type="boolean",
                query=True,
                description="Include spam and trash in results",
            ),
        ],
    ),
    ApiTool(
        name="get_email",
        description=(
            "Get the full content of an email by its ID. "
            "Returns headers, body content, labels, and attachment metadata."
        ),
        method="GET",
        path="/gmail/v1/users/me/messages/{id}",
        params=[
            Param(name="id", required=True, description="The email message ID"),
            Param(
                name="format",
                query=True,
                enum=["full", "metadata", "minimal", "raw"],
                description="Response format (default: full)",
                default="full",
            ),
        ],
    ),
    CustomTool(
        name="send_email",
        description=(
            "Send a new email. Optionally include thread_id, in_reply_to, and references "
            "headers to send as a reply within an existing thread."
        ),
        params=_COMPOSE_PARAMS,
        run=_run_send_email,
    ),
    ApiTool(
        name="trash_email",
        description="Move an email to the trash.",
        method="POST",
        path="/gmail/v1/users/me/messages/{id}/trash",
        params=[
            Param(name="id", required=True, description="The email message ID"),
        ],
    ),
    ApiTool(
        name="untrash_email",
        description="Remove an email from the trash.",
        method="POST",
        path="/gmail/v1/users/me/messages/{id}/untrash",
        params=[
            Param(name="id", required=True, description="The email message ID"),
        ],
    ),
    ApiTool(
        name="modify_labels",
        description=(
            "Add or remove labels on an email (e.g. mark as read by removing UNREAD label)."
        ),
        method="POST",
        path="/gmail/v1/users/me/messages/{id}/modify",
        params=[
            Param(name="id", required=True, description="The email message ID"),
            Param(
                name="addLabelIds",
                type="array",
                items="string",
                description="Label IDs to add (e.g. ['STARRED', 'IMPORTANT'])",
            ),
            Param(
                name="removeLabelIds",
                type="array",
                items="string",
                description="Label IDs to remove (e.g. ['UNREAD'] to mark as read)",
            ),
        ],
    ),
    ApiTool(
        name="get_attachment",
        description="Download an email attachment by message ID and attachment ID.",
        method="GET",
        path="/gmail/v1/users/me/messages/{messageId}/attachments/{id}",
        params=[
            Param(name="messageId", required=True, description="The email message ID"),
            Param(name="id", required=True, description="The attachment ID"),
        ],
    ),
    # ── Drafts ────────────────────────────────────────────────────────────
    CustomTool(
        name="create_draft",
        description="Create a new email draft.",
        params=_COMPOSE_PARAMS,
        run=_run_create_draft,
    ),
    ApiTool(
        name="list_drafts",
        description="List all email drafts.",
        method="GET",
        path="/gmail/v1/users/me/drafts",
        params=[
            Param(
                name="maxResults",
                type="integer",
                query=True,
                description="Maximum number of drafts to return",
                default=10,
            ),
            Param(name="pageToken", query=True, description="Token for pagination"),
            Param(name="q", query=True, description="Search query to filter drafts"),
        ],
    ),
    ApiTool(
        name="get_draft",
        description="Get the full content of a draft by its ID.",
        method="GET",
        path="/gmail/v1/users/me/drafts/{id}",
        params=[
            Param(name="id", required=True, description="The draft ID"),
            Param(
                name="format",
                query=True,
                enum=["full", "metadata", "minimal", "raw"],
                description="Response format",
                default="full",
            ),
        ],
    ),
    CustomTool(
        name="update_draft",
        description="Replace a draft with new content.",
        params=[
            Param(name="id", required=True, description="The draft ID to update"),
            *_COMPOSE_PARAMS,
        ],
        run=_run_update_draft,
    ),
    ApiTool(
        name="send_draft",
        description="Send an existing draft by its ID.",
        method="POST",
        path="/gmail/v1/users/me/drafts/send",
        params=[
            Param(name="id", required=True, description="The draft ID to send"),
        ],
    ),
    ApiTool(
        name="delete_draft",
        description="Permanently delete a draft.",
        method="DELETE",
        path="/gmail/v1/users/me/drafts/{id}",
        params=[
            Param(name="id", required=True, description="The draft ID to delete"),
        ],
    ),
    # ── Labels ────────────────────────────────────────────────────────────
    ApiTool(
        name="list_labels",
        description="List all labels in the Gmail account (INBOX, SENT, custom labels, etc.).",
        method="GET",
        path="/gmail/v1/users/me/labels",
        params=[],
    ),
    ApiTool(
        name="create_label",
        description="Create a new Gmail label.",
        method="POST",
        path="/gmail/v1/users/me/labels",
        params=[
            Param(name="name", required=True, description="The label name"),
            Param(
                name="labelListVisibility",
                enum=["labelShow", "labelShowIfUnread", "labelHide"],
                description="Visibility of the label in the label list",
            ),
            Param(
                name="messageListVisibility",
                enum=["show", "hide"],
                description="Visibility of messages with this label in message list",
            ),
        ],
    ),
    ApiTool(
        name="delete_label",
        description="Delete a Gmail label by ID. Built-in labels cannot be deleted.",
        method="DELETE",
        path="/gmail/v1/users/me/labels/{id}",
        params=[
            Param(name="id", required=True, description="The label ID to delete"),
        ],
    ),
    # ── Threads ───────────────────────────────────────────────────────────
    ApiTool(
        name="list_threads",
        description=(
            "List email threads. Use 'q' for search syntax. "
            "Returns thread IDs with snippet previews."
        ),
        method="GET",
        path="/gmail/v1/users/me/threads",
        params=[
            Param(name="q", query=True, description="Gmail search query"),
            Param(
                name="maxResults",
                type="integer",
                query=True,
                description="Maximum number of threads to return",
                default=10,
            ),
            Param(name="labelIds", query=True, description="Label ID to filter by"),
            Param(name="pageToken", query=True, description="Token for pagination"),
            Param(
                name="includeSpamTrash",
                type="boolean",
                query=True,
                description="Include spam and trash",
            ),
        ],
    ),
    ApiTool(
        name="get_thread",
        description="Get all messages in an email thread.",
        method="GET",
        path="/gmail/v1/users/me/threads/{id}",
        params=[
            Param(name="id", required=True, description="The thread ID"),
            Param(
                name="format",
                query=True,
                enum=["full", "metadata", "minimal"],
                description="Response format for messages in the thread",
                default="full",
            ),
        ],
    ),
]


class GmailIntegration(CustomIntegration):
    id: str = "gmail"
    name: str = "Gmail"
    description: str = "Read, send, and manage emails and drafts"
    docs_url: str = "https://developers.google.com/gmail/api/reference/rest"
    base_url: str = _BASE_URL
    auth: list[AuthMethod] = Field(default=[_GMAIL_OAUTH])
    tools: list[Union[ApiTool, CustomTool]] = Field(default=_TOOLS)
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)

    def is_available(self) -> tuple[bool, str | None]:
        from agent_port.config import settings

        if settings.get_oauth_credentials("google"):
            return True, None
        return (
            False,
            "Set the env vars OAUTH_GOOGLE_CLIENT_ID and "
            "OAUTH_GOOGLE_CLIENT_SECRET to use this integration.",
        )
