from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
)

_TOOL_CATEGORIES: dict[str, str] = {}


class GranolaIntegration(RemoteMcpIntegration):
    id: str = "granola"
    name: str = "Granola"
    description: str = "AI-powered meeting notes and transcripts"
    docs_url: str = "https://www.granola.ai/blog/granola-mcp"
    url: str = "https://mcp.granola.ai/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
