from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
    TokenAuth,
)

_TOOL_CATEGORIES: dict[str, str] = {}


class TallyIntegration(RemoteMcpIntegration):
    id: str = "tally"
    name: str = "Tally"
    description: str = "Beautiful forms that work like a doc"
    docs_url: str = "https://developers.tally.so/api-reference/mcp"
    url: str = "https://api.tally.so/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
            TokenAuth(
                method="token",
                label="Tally API Key",
                header="Authorization",
                format="Bearer {token}",
            ),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
