from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
    TokenAuth,
)

_TOOL_CATEGORIES: dict[str, str] = {}


class IntercomIntegration(RemoteMcpIntegration):
    id: str = "intercom"
    name: str = "Intercom"
    description: str = "Customer messaging, support, and engagement platform"
    docs_url: str = "https://www.intercom.com/help/en/articles/intercom-mcp"
    url: str = "https://mcp.intercom.com/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
            TokenAuth(
                method="token",
                label="Intercom Access Token",
                header="Authorization",
                format="Bearer {token}",
            ),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
