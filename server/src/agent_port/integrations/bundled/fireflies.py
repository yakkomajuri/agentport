from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
    TokenAuth,
)

_TOOL_CATEGORIES: dict[str, str] = {}


class FirefliesIntegration(RemoteMcpIntegration):
    id: str = "fireflies"
    name: str = "Fireflies"
    description: str = "AI meeting transcription and notes"
    docs_url: str = "https://docs.fireflies.ai/getting-started/mcp-configuration"
    url: str = "https://api.fireflies.ai/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
            TokenAuth(
                method="token",
                label="Fireflies API Key",
                header="Authorization",
                format="Bearer {token}",
            ),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
