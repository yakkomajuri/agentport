from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
    TokenAuth,
)

_TOOL_CATEGORIES: dict[str, str] = {}


class AsanaIntegration(RemoteMcpIntegration):
    id: str = "asana"
    name: str = "Asana"
    description: str = "Project and task management for teams"
    docs_url: str = "https://developers.asana.com/docs/using-asanas-mcp-server"
    url: str = "https://mcp.asana.com/v2/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
            TokenAuth(
                method="token",
                label="Asana Personal Access Token",
                header="Authorization",
                format="Bearer {token}",
            ),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
