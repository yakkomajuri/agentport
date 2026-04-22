from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
    TokenAuth,
)

_TOOL_CATEGORIES: dict[str, str] = {}


class NeonIntegration(RemoteMcpIntegration):
    id: str = "neon"
    name: str = "Neon"
    description: str = "Serverless Postgres database platform"
    docs_url: str = "https://neon.com/docs/ai/neon-mcp-server"
    url: str = "https://mcp.neon.tech/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
            TokenAuth(
                method="token",
                label="Neon API Key",
                header="Authorization",
                format="Bearer {token}",
            ),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
