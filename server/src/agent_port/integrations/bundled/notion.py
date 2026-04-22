from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
)

_TOOL_CATEGORIES: dict[str, str] = {}


class NotionIntegration(RemoteMcpIntegration):
    id: str = "notion"
    name: str = "Notion"
    description: str = "All-in-one workspace for notes, docs, and project management"
    docs_url: str = "https://developers.notion.com/docs/mcp"
    url: str = "https://mcp.notion.com/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
