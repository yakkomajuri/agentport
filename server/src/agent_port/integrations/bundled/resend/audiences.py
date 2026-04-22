"""Resend audience tools: segments, contact properties, and topics."""

from agent_port.integrations.types import ApiTool, Param

_PAGINATION_PARAMS = [
    Param(name="limit", type="integer", query=True, description="Max results (1-100)"),
    Param(name="after", query=True, description="Cursor for next page"),
    Param(name="before", query=True, description="Cursor for previous page"),
]

# ---------------------------------------------------------------------------
# Segments
# ---------------------------------------------------------------------------

_SEGMENT_TOOLS: list[ApiTool] = [
    ApiTool(
        name="create_segment",
        description="Create a new segment for targeting broadcasts.",
        method="POST",
        path="/segments",
        params=[
            Param(name="name", required=True, description="Segment name"),
        ],
    ),
    ApiTool(
        name="list_segments",
        description="List all segments with pagination.",
        method="GET",
        path="/segments",
        params=_PAGINATION_PARAMS,
    ),
    ApiTool(
        name="get_segment",
        description="Get a segment by ID.",
        method="GET",
        path="/segments/{id}",
        params=[
            Param(name="id", required=True, description="Segment ID"),
        ],
    ),
    ApiTool(
        name="remove_segment",
        description="Delete a segment by ID. Removal is irreversible.",
        method="DELETE",
        path="/segments/{id}",
        params=[
            Param(name="id", required=True, description="Segment ID"),
        ],
    ),
]

# ---------------------------------------------------------------------------
# Contact Properties
# ---------------------------------------------------------------------------

_CONTACT_PROPERTY_TOOLS: list[ApiTool] = [
    ApiTool(
        name="create_contact_property",
        description=(
            "Create a new custom contact attribute (e.g. company_name, plan_tier). "
            "Key must be alphanumeric/underscores, max 50 characters."
        ),
        method="POST",
        path="/contact-properties",
        params=[
            Param(
                name="key",
                required=True,
                description="Property key (alphanumeric and underscores, max 50 chars)",
            ),
            Param(
                name="type",
                required=True,
                enum=["string", "number"],
                description="Property value type",
            ),
            Param(
                name="fallbackValue",
                description="Default value when not set on a contact (must match type)",
            ),
        ],
    ),
    ApiTool(
        name="list_contact_properties",
        description="List all contact properties.",
        method="GET",
        path="/contact-properties",
        params=_PAGINATION_PARAMS,
    ),
    ApiTool(
        name="get_contact_property",
        description="Get a contact property by ID.",
        method="GET",
        path="/contact-properties/{contactPropertyId}",
        params=[
            Param(name="contactPropertyId", required=True, description="Contact property ID"),
        ],
    ),
    ApiTool(
        name="update_contact_property",
        description="Update a contact property's fallback value. Key and type cannot be modified.",
        method="PATCH",
        path="/contact-properties/{contactPropertyId}",
        params=[
            Param(name="contactPropertyId", required=True, description="Contact property ID"),
            Param(
                name="fallbackValue",
                required=True,
                description="New fallback value (string, number, or null)",
            ),
        ],
    ),
    ApiTool(
        name="remove_contact_property",
        description="Remove a contact property by ID.",
        method="DELETE",
        path="/contact-properties/{contactPropertyId}",
        params=[
            Param(name="contactPropertyId", required=True, description="Contact property ID"),
        ],
    ),
]

# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------

_TOPIC_TOOLS: list[ApiTool] = [
    ApiTool(
        name="create_topic",
        description="Create a subscription topic for managing contact preferences.",
        method="POST",
        path="/topics",
        params=[
            Param(name="name", required=True, description="Topic name (max 50 chars)"),
            Param(
                name="default_subscription",
                required=True,
                enum=["opt_in", "opt_out"],
                description="Default subscription behavior for new contacts",
            ),
            Param(name="description", description="Topic description (max 200 chars)"),
        ],
    ),
    ApiTool(
        name="list_topics",
        description="List all topics.",
        method="GET",
        path="/topics",
        params=[],
    ),
    ApiTool(
        name="get_topic",
        description="Get a topic by ID.",
        method="GET",
        path="/topics/{id}",
        params=[
            Param(name="id", required=True, description="Topic ID"),
        ],
    ),
    ApiTool(
        name="update_topic",
        description="Update topic name and description. Default subscription cannot be changed.",
        method="PATCH",
        path="/topics/{id}",
        params=[
            Param(name="id", required=True, description="Topic ID"),
            Param(name="name", description="Updated name (max 50 chars)"),
            Param(name="description", description="Updated description (max 200 chars)"),
        ],
    ),
    ApiTool(
        name="remove_topic",
        description="Remove a topic by ID.",
        method="DELETE",
        path="/topics/{id}",
        params=[
            Param(name="id", required=True, description="Topic ID"),
        ],
    ),
]

# ---------------------------------------------------------------------------
# Combined exports
# ---------------------------------------------------------------------------

TOOLS: list[ApiTool] = [*_SEGMENT_TOOLS, *_CONTACT_PROPERTY_TOOLS, *_TOPIC_TOOLS]
