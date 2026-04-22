from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
)

_TOOL_CATEGORIES: dict[str, str] = {}


class WixIntegration(RemoteMcpIntegration):
    id: str = "wix"
    name: str = "Wix"
    description: str = "Website builder and business management platform"
    docs_url: str = "https://dev.wix.com/docs/sdk/articles/use-the-wix-mcp/about-the-wix-mcp"
    url: str = "https://mcp.wix.com/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
