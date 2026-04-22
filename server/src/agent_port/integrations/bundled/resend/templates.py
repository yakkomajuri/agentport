"""Resend template tools: create, edit, compose, publish, and duplicate email templates."""

from agent_port.integrations.types import ApiTool, Param

_PAGINATION_PARAMS = [
    Param(name="limit", type="integer", query=True, description="Max results (1-100)"),
    Param(name="after", query=True, description="Cursor for next page"),
    Param(name="before", query=True, description="Cursor for previous page"),
]

_VARIABLE_SCHEMA = {
    "type": "array",
    "description": "Template variables (up to 50). Use {{{variable}}} syntax in HTML.",
    "items": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Variable name"},
            "description": {"type": "string"},
            "default": {"type": "string", "description": "Default value"},
            "required": {"type": "boolean"},
        },
        "required": ["name"],
    },
}

TOOLS: list[ApiTool] = [
    ApiTool(
        name="create_template",
        description=(
            "Create a new email template in draft status. "
            "Use {{{variable}}} syntax for dynamic content in HTML."
        ),
        method="POST",
        path="/templates",
        params=[
            Param(name="name", required=True, description="Template name"),
            Param(
                name="html",
                required=True,
                description="HTML content with {{{variable}}} placeholders",
            ),
            Param(name="subject", description="Default subject line"),
            Param(name="from", description="Default sender address"),
            Param(name="replyTo", description="Default reply-to address"),
            Param(name="text", description="Plain text fallback"),
            Param(name="alias", description="URL-friendly alias for the template"),
            Param(name="variables", schema_override=_VARIABLE_SCHEMA),
        ],
    ),
    ApiTool(
        name="list_templates",
        description="List all email templates.",
        method="GET",
        path="/templates",
        params=_PAGINATION_PARAMS,
    ),
    ApiTool(
        name="get_template",
        description="Get a template by ID, alias, or Resend dashboard URL.",
        method="GET",
        path="/templates/{id}",
        params=[
            Param(
                name="id",
                required=True,
                description="Template ID, alias, or dashboard URL",
            ),
        ],
    ),
    ApiTool(
        name="update_template",
        description="Update template metadata, content, or variables.",
        method="PATCH",
        path="/templates/{id}",
        params=[
            Param(name="id", required=True, description="Template ID"),
            Param(name="name", description="Updated name"),
            Param(name="html", description="Updated HTML content"),
            Param(name="subject", description="Updated subject line"),
            Param(name="from", description="Updated sender address"),
            Param(name="replyTo", description="Updated reply-to address"),
            Param(name="text", description="Updated plain text fallback"),
            Param(name="alias", description="Updated alias"),
            Param(name="variables", schema_override=_VARIABLE_SCHEMA),
        ],
    ),
    ApiTool(
        name="remove_template",
        description="Remove a template by ID, alias, or dashboard URL.",
        method="DELETE",
        path="/templates/{id}",
        params=[
            Param(
                name="id",
                required=True,
                description="Template ID, alias, or dashboard URL",
            ),
        ],
    ),
    ApiTool(
        name="publish_template",
        description=("Publish a template. Must be published before it can be used to send."),
        method="POST",
        path="/templates/{id}/publish",
        params=[
            Param(
                name="id",
                required=True,
                description="Template ID, alias, or dashboard URL",
            ),
        ],
    ),
    ApiTool(
        name="duplicate_template",
        description="Duplicate a template, creating a new draft copy.",
        method="POST",
        path="/templates/{id}/duplicate",
        params=[
            Param(
                name="id",
                required=True,
                description="Template ID, alias, or dashboard URL",
            ),
        ],
    ),
]
