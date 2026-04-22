from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
    TokenAuth,
)

_TOOL_CATEGORIES: dict[str, str] = {}


class RampIntegration(RemoteMcpIntegration):
    id: str = "ramp"
    name: str = "Ramp"
    description: str = "Corporate expense management and finance"
    docs_url: str = "https://docs.ramp.com/mcp"
    url: str = "https://ramp-mcp-remote.ramp.com/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
            TokenAuth(
                method="token",
                label="Ramp API Key",
                header="Authorization",
                format="Bearer {token}",
            ),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
