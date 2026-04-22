from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
)

_TOOL_CATEGORIES: dict[str, str] = {
    # Analytics
    "Run-Query": "Analytics",
    "Get-Query-Schema": "Analytics",
    "Get-Report": "Analytics",
    # Dashboards
    "Create-Dashboard": "Dashboards",
    "List-Dashboards": "Dashboards",
    "Get-Dashboard": "Dashboards",
    "Update-Dashboard": "Dashboards",
    "Duplicate-Dashboard": "Dashboards",
    "Delete-Dashboard": "Dashboards",
    # Discovery
    "Get-Projects": "Discovery",
    "Get-Events": "Discovery",
    "Get-Property-Names": "Discovery",
    "Get-Property-Values": "Discovery",
    "Get-Event-Details": "Discovery",
    "Get-Issues": "Discovery",
    "Get-Lexicon-URL": "Discovery",
    # Data Management
    "Edit-Event": "Data Management",
    "Edit-Property": "Data Management",
    "Create-Tag": "Data Management",
    "Rename-Tag": "Data Management",
    "Delete-Tag": "Data Management",
    "Dismiss-Issues": "Data Management",
    # Session Replays
    "Get-User-Replays-Data": "Session Replays",
}


class MixpanelIntegration(RemoteMcpIntegration):
    id: str = "mixpanel"
    name: str = "Mixpanel"
    description: str = "Product analytics, funnels, and user engagement"
    docs_url: str = "https://docs.mixpanel.com/docs/mcp"
    url: str = "https://mcp.mixpanel.com/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
