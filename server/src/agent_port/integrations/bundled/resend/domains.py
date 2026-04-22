"""Resend domain tools: create, list, verify, and manage sending domains."""

from agent_port.integrations.types import ApiTool, Param

_PAGINATION_PARAMS = [
    Param(name="limit", type="integer", query=True, description="Max results (1-100)"),
    Param(name="after", query=True, description="Cursor for next page"),
    Param(name="before", query=True, description="Cursor for previous page"),
]

TOOLS: list[ApiTool] = [
    ApiTool(
        name="create_domain",
        description=(
            "Create a new sending domain in Resend. "
            "Returns DNS records that must be added for verification."
        ),
        method="POST",
        path="/domains",
        params=[
            Param(name="name", required=True, description="Domain name (e.g. 'mail.example.com')"),
            Param(
                name="region",
                enum=["us-east-1", "eu-west-1", "sa-east-1", "ap-northeast-1"],
                description="AWS region for the domain",
            ),
            Param(name="customReturnPath", description="Custom return path subdomain"),
            Param(name="openTracking", type="boolean", description="Enable open tracking"),
            Param(name="clickTracking", type="boolean", description="Enable click tracking"),
            Param(
                name="tls",
                enum=["opportunistic", "enforced"],
                description="TLS mode for outgoing emails",
            ),
            Param(
                name="capabilities",
                schema_override={
                    "type": "object",
                    "description": "Domain capabilities configuration",
                },
            ),
        ],
    ),
    ApiTool(
        name="list_domains",
        description="List all domains configured in Resend.",
        method="GET",
        path="/domains",
        params=_PAGINATION_PARAMS,
    ),
    ApiTool(
        name="get_domain",
        description="Get a domain by ID with full details including DNS records.",
        method="GET",
        path="/domains/{id}",
        params=[
            Param(name="id", required=True, description="Domain ID"),
        ],
    ),
    ApiTool(
        name="update_domain",
        description="Update tracking settings, TLS mode, and capabilities for a domain.",
        method="PATCH",
        path="/domains/{id}",
        params=[
            Param(name="id", required=True, description="Domain ID"),
            Param(
                name="clickTracking", type="boolean", description="Enable/disable click tracking"
            ),
            Param(name="openTracking", type="boolean", description="Enable/disable open tracking"),
            Param(
                name="tls",
                enum=["opportunistic", "enforced"],
                description="TLS mode",
            ),
            Param(
                name="capabilities",
                schema_override={
                    "type": "object",
                    "description": "Updated capabilities configuration",
                },
            ),
        ],
    ),
    ApiTool(
        name="remove_domain",
        description="Remove a domain by ID.",
        method="DELETE",
        path="/domains/{id}",
        params=[
            Param(name="id", required=True, description="Domain ID"),
        ],
    ),
    ApiTool(
        name="verify_domain",
        description="Trigger domain verification. DNS records must already be configured.",
        method="POST",
        path="/domains/{id}/verify",
        params=[
            Param(name="id", required=True, description="Domain ID"),
        ],
    ),
]
