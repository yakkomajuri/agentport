from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
)

_TOOL_CATEGORIES: dict[str, str] = {}


class AttioIntegration(RemoteMcpIntegration):
    id: str = "attio"
    name: str = "Attio"
    description: str = "Next-generation CRM for relationship management"
    docs_url: str = "https://docs.attio.com/mcp/overview"
    url: str = "https://mcp.attio.com/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
