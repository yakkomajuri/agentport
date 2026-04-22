from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
    TokenAuth,
)

_TOOL_CATEGORIES: dict[str, str] = {}


class SupabaseIntegration(RemoteMcpIntegration):
    id: str = "supabase"
    name: str = "Supabase"
    description: str = "Open-source database and backend platform"
    docs_url: str = "https://supabase.com/docs/guides/getting-started/mcp"
    url: str = "https://mcp.supabase.com/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
            TokenAuth(
                method="token",
                label="Supabase Access Token",
                header="Authorization",
                format="Bearer {token}",
            ),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
