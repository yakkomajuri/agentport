from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
    TokenAuth,
)

_TOOL_CATEGORIES: dict[str, str] = {}


class SquareIntegration(RemoteMcpIntegration):
    id: str = "square"
    name: str = "Square"
    description: str = "Payment processing, invoicing, and commerce management"
    docs_url: str = "https://developer.squareup.com/docs/mcp"
    url: str = "https://mcp.squareup.com/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
            TokenAuth(
                method="token",
                label="Square Access Token",
                header="Authorization",
                format="Bearer {token}",
            ),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
