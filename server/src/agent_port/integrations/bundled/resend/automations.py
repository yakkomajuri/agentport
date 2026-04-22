"""Resend automation and event tools."""

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
# Automation workflow schema
# ---------------------------------------------------------------------------

_STEPS_SCHEMA = {
    "type": "array",
    "description": "Ordered workflow steps",
    "items": {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "description": "Step type (e.g. 'send_email', 'delay', 'condition')",
            },
            "config": {
                "type": "object",
                "description": "Step-specific configuration",
            },
        },
    },
}

# ---------------------------------------------------------------------------
# Custom tools: get_automation (list all or get single)
# ---------------------------------------------------------------------------


async def _run_get_automation(args: dict, auth_headers: dict) -> dict:
    automation_id = args.get("id")
    async with httpx.AsyncClient() as client:
        if automation_id:
            r = await client.get(
                f"{_BASE_URL}/automations/{automation_id}",
                headers=auth_headers,
                timeout=30.0,
            )
        else:
            params: dict = {}
            if args.get("status"):
                params["status"] = args["status"]
            for key in ("limit", "after", "before"):
                if args.get(key) is not None:
                    params[key] = args[key]
            r = await client.get(
                f"{_BASE_URL}/automations",
                params=params or None,
                headers=auth_headers,
                timeout=30.0,
            )
    return response_to_result(r)


async def _run_get_automation_runs(args: dict, auth_headers: dict) -> dict:
    automation_id = args["automationId"]
    run_id = args.get("runId")
    async with httpx.AsyncClient() as client:
        if run_id:
            r = await client.get(
                f"{_BASE_URL}/automations/{automation_id}/runs/{run_id}",
                headers=auth_headers,
                timeout=30.0,
            )
        else:
            params: dict = {}
            if args.get("status"):
                params["status"] = args["status"]
            for key in ("limit", "after", "before"):
                if args.get(key) is not None:
                    params[key] = args[key]
            r = await client.get(
                f"{_BASE_URL}/automations/{automation_id}/runs",
                params=params or None,
                headers=auth_headers,
                timeout=30.0,
            )
    return response_to_result(r)


# ---------------------------------------------------------------------------
# Custom tool: manage_events (multi-action CRUD)
# ---------------------------------------------------------------------------


async def _run_manage_events(args: dict, auth_headers: dict) -> dict:
    action = args.get("action")
    if not action:
        return {
            "content": [{"type": "text", "text": "'action' is required"}],
            "isError": True,
        }

    async with httpx.AsyncClient() as client:
        if action == "create":
            body: dict = {}
            if args.get("name"):
                body["name"] = args["name"]
            if args.get("schema"):
                body["schema"] = args["schema"]
            r = await client.post(
                f"{_BASE_URL}/events",
                json=body,
                headers=auth_headers,
                timeout=30.0,
            )
        elif action == "list":
            params: dict = {}
            for key in ("limit", "after", "before"):
                if args.get(key) is not None:
                    params[key] = args[key]
            r = await client.get(
                f"{_BASE_URL}/events",
                params=params or None,
                headers=auth_headers,
                timeout=30.0,
            )
        elif action == "get":
            identifier = args.get("identifier")
            if not identifier:
                return {
                    "content": [
                        {"type": "text", "text": "'identifier' is required for 'get' action"}
                    ],
                    "isError": True,
                }
            r = await client.get(
                f"{_BASE_URL}/events/{identifier}",
                headers=auth_headers,
                timeout=30.0,
            )
        elif action == "update":
            identifier = args.get("identifier")
            if not identifier:
                return {
                    "content": [
                        {"type": "text", "text": "'identifier' is required for 'update' action"}
                    ],
                    "isError": True,
                }
            body = {}
            if args.get("name"):
                body["name"] = args["name"]
            if args.get("schema"):
                body["schema"] = args["schema"]
            r = await client.patch(
                f"{_BASE_URL}/events/{identifier}",
                json=body,
                headers=auth_headers,
                timeout=30.0,
            )
        elif action == "remove":
            identifier = args.get("identifier")
            if not identifier:
                return {
                    "content": [
                        {"type": "text", "text": "'identifier' is required for 'remove' action"}
                    ],
                    "isError": True,
                }
            r = await client.delete(
                f"{_BASE_URL}/events/{identifier}",
                headers=auth_headers,
                timeout=30.0,
            )
        else:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Unknown action '{action}'. Use: create, list, get, update, remove"
                        ),
                    }
                ],
                "isError": True,
            }

    return response_to_result(r)


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS: list[Union[ApiTool, CustomTool]] = [
    # ── Automations ──────────────────────────────────────────────────────
    ApiTool(
        name="create_automation",
        description="Create an automation workflow triggered on events.",
        method="POST",
        path="/automations",
        params=[
            Param(name="name", required=True, description="Automation name"),
            Param(
                name="status",
                enum=["enabled", "disabled"],
                description="Initial status (default: disabled)",
            ),
            Param(name="steps", required=True, schema_override=_STEPS_SCHEMA),
        ],
    ),
    ApiTool(
        name="update_automation",
        description="Update automation name, status, or workflow.",
        method="PATCH",
        path="/automations/{id}",
        params=[
            Param(
                name="id",
                required=True,
                description="Automation ID or Resend dashboard URL",
            ),
            Param(name="name", description="Updated name"),
            Param(name="status", enum=["enabled", "disabled"], description="Updated status"),
            Param(name="steps", schema_override=_STEPS_SCHEMA),
        ],
    ),
    CustomTool(
        name="get_automation",
        description=(
            "Get automation details by ID, or list all automations when ID is omitted. "
            "Supports filtering by status and pagination."
        ),
        params=[
            Param(name="id", description="Automation ID (omit to list all)"),
            Param(name="status", enum=["enabled", "disabled"], description="Filter by status"),
            *_PAGINATION_PARAMS,
        ],
        run=_run_get_automation,
    ),
    ApiTool(
        name="remove_automation",
        description="Remove an automation by ID or dashboard URL.",
        method="DELETE",
        path="/automations/{id}",
        params=[
            Param(
                name="id",
                required=True,
                description="Automation ID or Resend dashboard URL",
            ),
        ],
    ),
    CustomTool(
        name="get_automation_runs",
        description=(
            "List runs for an automation, or get specific run details when runId is provided. "
            "Supports filtering by status and pagination."
        ),
        params=[
            Param(name="automationId", required=True, description="Automation ID"),
            Param(name="runId", description="Specific run ID (omit to list all runs)"),
            Param(
                name="status",
                enum=["running", "completed", "failed", "cancelled"],
                description="Filter by run status",
            ),
            *_PAGINATION_PARAMS,
        ],
        run=_run_get_automation_runs,
    ),
    # ── Events ───────────────────────────────────────────────────────────
    ApiTool(
        name="send_event",
        description="Fire an event to trigger automations for a specific contact.",
        method="POST",
        path="/events",
        params=[
            Param(
                name="name",
                required=True,
                description="Event name (e.g. 'user.created')",
            ),
            Param(name="contactId", description="Contact ID (provide contactId or email)"),
            Param(name="email", description="Contact email (provide contactId or email)"),
            Param(
                name="payload",
                schema_override={
                    "type": "object",
                    "description": "Key-value event data",
                    "additionalProperties": True,
                },
            ),
        ],
    ),
    CustomTool(
        name="manage_events",
        description=(
            "Create, list, get, update, or remove event definitions. "
            "Use 'action' to specify the operation."
        ),
        params=[
            Param(
                name="action",
                required=True,
                enum=["create", "list", "get", "update", "remove"],
                description="Operation to perform",
            ),
            Param(name="name", description="Event name (required for create)"),
            Param(
                name="identifier", description="Event ID or name (required for get/update/remove)"
            ),
            Param(
                name="schema",
                schema_override={
                    "type": "object",
                    "description": "Field name to type mapping",
                    "additionalProperties": {"type": "string"},
                },
            ),
            *_PAGINATION_PARAMS,
        ],
        run=_run_manage_events,
    ),
]
