from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
)

_TOOL_CATEGORIES: dict[str, str] = {}


class ZapierIntegration(RemoteMcpIntegration):
    id: str = "zapier"
    name: str = "Zapier"
    description: str = "Workflow automation connecting 8,000+ apps"
    docs_url: str = "https://zapier.com/mcp"
    url: str = "https://mcp.zapier.com/api/mcp/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
