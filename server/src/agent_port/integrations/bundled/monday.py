from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
)

_TOOL_CATEGORIES: dict[str, str] = {}


class MondayIntegration(RemoteMcpIntegration):
    id: str = "monday"
    name: str = "monday.com"
    description: str = "Work management and team collaboration platform"
    docs_url: str = (
        "https://support.monday.com/hc/en-us/articles/28515034903314-monday-Platform-MCP"
    )
    url: str = "https://mcp.monday.com/sse"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
