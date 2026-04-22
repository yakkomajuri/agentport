from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
    TokenAuth,
)

_TOOL_CATEGORIES: dict[str, str] = {}


class CalendlyIntegration(RemoteMcpIntegration):
    id: str = "calendly"
    name: str = "Calendly"
    description: str = "Scheduling and calendar management"
    docs_url: str = "https://developer.calendly.com/calendly-mcp-server"
    url: str = "https://mcp.calendly.com"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
            TokenAuth(
                method="token",
                label="Calendly Personal Access Token",
                header="Authorization",
                format="Bearer {token}",
            ),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
