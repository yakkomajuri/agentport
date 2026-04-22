from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
)

_TOOL_CATEGORIES: dict[str, str] = {}


class NetlifyIntegration(RemoteMcpIntegration):
    id: str = "netlify"
    name: str = "Netlify"
    description: str = "Web deployment platform and serverless functions"
    docs_url: str = "https://docs.netlify.com/build/build-with-ai/netlify-mcp-server/"
    url: str = "https://netlify-mcp.netlify.app/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
