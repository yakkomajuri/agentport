from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
)

_TOOL_CATEGORIES: dict[str, str] = {
    # Feature Flags
    "create-flag": "Feature Flags",
    "get-flag": "Feature Flags",
    "list-flags": "Feature Flags",
    "toggle-flag": "Feature Flags",
    "update-flag-settings": "Feature Flags",
    "update-targeting-rules": "Feature Flags",
    "update-rollout": "Feature Flags",
    # Contexts
    "get-context-details": "Contexts",
    # Metrics
    "list-metrics": "Metrics",
}


class LaunchDarklyIntegration(RemoteMcpIntegration):
    id: str = "launchdarkly"
    name: str = "LaunchDarkly"
    description: str = "Feature flags, feature management, and experimentation"
    docs_url: str = "https://launchdarkly.com/docs/home/getting-started/mcp-hosted"
    url: str = "https://mcp.launchdarkly.com/mcp/fm"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
