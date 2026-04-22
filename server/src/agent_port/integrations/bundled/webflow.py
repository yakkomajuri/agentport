from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
    TokenAuth,
)

_TOOL_CATEGORIES: dict[str, str] = {}


class WebflowIntegration(RemoteMcpIntegration):
    id: str = "webflow"
    name: str = "Webflow"
    description: str = "Visual website builder and CMS platform"
    docs_url: str = "https://developers.webflow.com/mcp/reference/overview"
    url: str = "https://mcp.webflow.com/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
            TokenAuth(
                method="token",
                label="Webflow API Token",
                header="Authorization",
                format="Bearer {token}",
            ),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
