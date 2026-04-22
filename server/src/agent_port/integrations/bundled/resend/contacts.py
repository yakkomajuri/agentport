"""Resend contact tools: CRUD, segment membership, and topic subscriptions."""

from typing import Union

import httpx

from agent_port.integrations.bundled.resend._http import _BASE_URL, response_to_result
from agent_port.integrations.types import ApiTool, CustomTool, Param

_PAGINATION_PARAMS = [
    Param(name="limit", type="integer", query=True, description="Max results (1-100)"),
    Param(name="after", query=True, description="Cursor for next page"),
    Param(name="before", query=True, description="Cursor for previous page"),
]

# ---------------------------------------------------------------------------
# Helpers for tools that accept id OR email
# ---------------------------------------------------------------------------


def _resolve_contact_id(args: dict) -> str | None:
    """Return whichever identifier the caller provided (id preferred over email)."""
    return args.get("id") or args.get("email")


def _missing_id_result() -> dict:
    return {
        "content": [{"type": "text", "text": "Either 'id' or 'email' is required"}],
        "isError": True,
    }


_ID_OR_EMAIL_PARAMS = [
    Param(name="id", description="Contact ID (UUID)"),
    Param(name="email", description="Contact email address"),
]

# ---------------------------------------------------------------------------
# Custom tools: get / update / remove contact (accept id OR email)
# ---------------------------------------------------------------------------


async def _run_get_contact(args: dict, auth_headers: dict) -> dict:
    contact_id = _resolve_contact_id(args)
    if not contact_id:
        return _missing_id_result()
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{_BASE_URL}/contacts/{contact_id}",
            headers=auth_headers,
            timeout=30.0,
        )
    return response_to_result(r)


async def _run_update_contact(args: dict, auth_headers: dict) -> dict:
    contact_id = _resolve_contact_id(args)
    if not contact_id:
        return _missing_id_result()
    body = {k: v for k, v in args.items() if k not in ("id", "email") and v is not None}
    async with httpx.AsyncClient() as client:
        r = await client.patch(
            f"{_BASE_URL}/contacts/{contact_id}",
            json=body,
            headers=auth_headers,
            timeout=30.0,
        )
    return response_to_result(r)


async def _run_remove_contact(args: dict, auth_headers: dict) -> dict:
    contact_id = _resolve_contact_id(args)
    if not contact_id:
        return _missing_id_result()
    async with httpx.AsyncClient() as client:
        r = await client.delete(
            f"{_BASE_URL}/contacts/{contact_id}",
            headers=auth_headers,
            timeout=30.0,
        )
    return response_to_result(r)


# ---------------------------------------------------------------------------
# Custom tools: segment membership (accept contactId OR email)
# ---------------------------------------------------------------------------

_CONTACT_OR_EMAIL_PARAMS = [
    Param(name="contactId", description="Contact ID (UUID)"),
    Param(name="email", description="Contact email address"),
]


def _resolve_contact_or_email(args: dict) -> str | None:
    return args.get("contactId") or args.get("email")


async def _run_add_contact_to_segment(args: dict, auth_headers: dict) -> dict:
    contact = _resolve_contact_or_email(args)
    if not contact:
        return _missing_id_result()
    segment_id = args.get("segmentId")
    if not segment_id:
        return {
            "content": [{"type": "text", "text": "'segmentId' is required"}],
            "isError": True,
        }
    body: dict = {}
    if args.get("contactId"):
        body["contactId"] = args["contactId"]
    else:
        body["email"] = args["email"]
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{_BASE_URL}/segments/{segment_id}/contacts",
            json=body,
            headers=auth_headers,
            timeout=30.0,
        )
    return response_to_result(r)


async def _run_remove_contact_from_segment(args: dict, auth_headers: dict) -> dict:
    contact = _resolve_contact_or_email(args)
    if not contact:
        return _missing_id_result()
    segment_id = args.get("segmentId")
    if not segment_id:
        return {
            "content": [{"type": "text", "text": "'segmentId' is required"}],
            "isError": True,
        }
    async with httpx.AsyncClient() as client:
        r = await client.delete(
            f"{_BASE_URL}/segments/{segment_id}/contacts/{contact}",
            headers=auth_headers,
            timeout=30.0,
        )
    return response_to_result(r)


async def _run_list_contact_segments(args: dict, auth_headers: dict) -> dict:
    contact_id = _resolve_contact_or_email(args)
    if not contact_id:
        return _missing_id_result()
    params = {k: args[k] for k in ("limit", "after", "before") if args.get(k) is not None}
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{_BASE_URL}/contacts/{contact_id}/segments",
            params=params or None,
            headers=auth_headers,
            timeout=30.0,
        )
    return response_to_result(r)


# ---------------------------------------------------------------------------
# Custom tools: topic subscriptions (accept id OR email)
# ---------------------------------------------------------------------------


async def _run_list_contact_topics(args: dict, auth_headers: dict) -> dict:
    contact_id = _resolve_contact_id(args)
    if not contact_id:
        return _missing_id_result()
    params = {k: args[k] for k in ("limit", "after", "before") if args.get(k) is not None}
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{_BASE_URL}/contacts/{contact_id}/topics",
            params=params or None,
            headers=auth_headers,
            timeout=30.0,
        )
    return response_to_result(r)


async def _run_update_contact_topics(args: dict, auth_headers: dict) -> dict:
    contact_id = _resolve_contact_id(args)
    if not contact_id:
        return _missing_id_result()
    topics = args.get("topics")
    if not topics:
        return {
            "content": [{"type": "text", "text": "'topics' array is required"}],
            "isError": True,
        }
    async with httpx.AsyncClient() as client:
        r = await client.patch(
            f"{_BASE_URL}/contacts/{contact_id}/topics",
            json={"topics": topics},
            headers=auth_headers,
            timeout=30.0,
        )
    return response_to_result(r)


# ---------------------------------------------------------------------------
# Topic subscription schema
# ---------------------------------------------------------------------------

_TOPIC_PREF_SCHEMA = {
    "type": "array",
    "description": "Topic subscription preferences",
    "items": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "Topic ID"},
            "subscribed": {
                "type": "boolean",
                "description": "Whether the contact is subscribed",
            },
        },
        "required": ["id", "subscribed"],
    },
}

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS: list[Union[ApiTool, CustomTool]] = [
    ApiTool(
        name="create_contact",
        description=(
            "Create a new contact in Resend with optional segment and topic subscriptions."
        ),
        method="POST",
        path="/contacts",
        params=[
            Param(name="email", required=True, description="Contact email address"),
            Param(name="firstName", description="First name"),
            Param(name="lastName", description="Last name"),
            Param(name="unsubscribed", type="boolean", description="Unsubscribed status"),
            Param(
                name="properties",
                schema_override={
                    "type": "object",
                    "description": "Custom key-value properties",
                    "additionalProperties": True,
                },
            ),
            Param(
                name="segmentIds",
                type="array",
                items="string",
                description="Segment IDs to add contact to",
            ),
            Param(name="topics", schema_override=_TOPIC_PREF_SCHEMA),
        ],
    ),
    ApiTool(
        name="list_contacts",
        description="List contacts with optional segment filtering.",
        method="GET",
        path="/contacts",
        params=[
            Param(name="segmentId", query=True, description="Filter by segment ID"),
            *_PAGINATION_PARAMS,
        ],
    ),
    CustomTool(
        name="get_contact",
        description="Retrieve a contact by ID or email address.",
        params=_ID_OR_EMAIL_PARAMS,
        run=_run_get_contact,
    ),
    CustomTool(
        name="update_contact",
        description="Modify contact information (first name, last name, unsubscribed, properties).",
        params=[
            *_ID_OR_EMAIL_PARAMS,
            Param(name="firstName", description="Updated first name"),
            Param(name="lastName", description="Updated last name"),
            Param(name="unsubscribed", type="boolean", description="Updated unsubscribed status"),
            Param(
                name="properties",
                schema_override={
                    "type": "object",
                    "description": "Updated custom properties",
                    "additionalProperties": True,
                },
            ),
        ],
        run=_run_update_contact,
    ),
    CustomTool(
        name="remove_contact",
        description="Remove a contact from Resend by ID or email address.",
        params=_ID_OR_EMAIL_PARAMS,
        run=_run_remove_contact,
    ),
    # ── Segment membership ───────────────────────────────────────────────
    CustomTool(
        name="add_contact_to_segment",
        description="Add a contact to a segment.",
        params=[
            *_CONTACT_OR_EMAIL_PARAMS,
            Param(name="segmentId", required=True, description="Segment ID"),
        ],
        run=_run_add_contact_to_segment,
    ),
    CustomTool(
        name="remove_contact_from_segment",
        description="Remove a contact from a segment.",
        params=[
            *_CONTACT_OR_EMAIL_PARAMS,
            Param(name="segmentId", required=True, description="Segment ID"),
        ],
        run=_run_remove_contact_from_segment,
    ),
    CustomTool(
        name="list_contact_segments",
        description="Display all segments a contact belongs to.",
        params=[
            *_CONTACT_OR_EMAIL_PARAMS,
            *_PAGINATION_PARAMS,
        ],
        run=_run_list_contact_segments,
    ),
    # ── Topic subscriptions ──────────────────────────────────────────────
    CustomTool(
        name="list_contact_topics",
        description="Display all topic subscriptions for a contact.",
        params=[
            *_ID_OR_EMAIL_PARAMS,
            *_PAGINATION_PARAMS,
        ],
        run=_run_list_contact_topics,
    ),
    CustomTool(
        name="update_contact_topics",
        description="Modify topic subscriptions for a contact.",
        params=[
            *_ID_OR_EMAIL_PARAMS,
            Param(name="topics", required=True, schema_override=_TOPIC_PREF_SCHEMA),
        ],
        run=_run_update_contact_topics,
    ),
]
