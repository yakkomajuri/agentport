from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
)

_TOOL_CATEGORIES: dict[str, str] = {
    # Analytics
    "getRelevantQuestions": "Analytics",
    "getAnswer": "Analytics",
    # Liveboards
    "createLiveboard": "Liveboards",
    # Data Sources
    "getDataSourceSuggestions": "Data Sources",
    # Connectivity
    "ping": "Connectivity",
}


class ThoughtSpotIntegration(RemoteMcpIntegration):
    id: str = "thoughtspot"
    name: str = "ThoughtSpot"
    description: str = "AI-powered business intelligence and analytics"
    docs_url: str = "https://developers.thoughtspot.com/docs/mcp-server"
    url: str = "https://agent.thoughtspot.app/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
