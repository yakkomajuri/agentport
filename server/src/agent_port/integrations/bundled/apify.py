from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
    TokenAuth,
)

_TOOL_CATEGORIES: dict[str, str] = {
    # Actor Discovery
    "search-actors": "Actor Discovery",
    "fetch-actor-details": "Actor Discovery",
    "add-actor": "Actor Discovery",
    # Documentation
    "search-apify-docs": "Documentation",
    "fetch-apify-docs": "Documentation",
    # Actor Management
    "call-actor": "Actor Management",
    "get-actor-run": "Actor Management",
    "get-actor-run-list": "Actor Management",
    "get-actor-log": "Actor Management",
    "get-actor-output": "Actor Management",
    # Data Access
    "get-dataset": "Data Access",
    "get-dataset-items": "Data Access",
    "get-dataset-schema": "Data Access",
    "get-dataset-list": "Data Access",
    "get-key-value-store": "Data Access",
    "get-key-value-store-keys": "Data Access",
    "get-key-value-store-record": "Data Access",
    "get-key-value-store-list": "Data Access",
    # Web Browsing
    "apify/rag-web-browser": "Web Browsing",
}


class ApifyIntegration(RemoteMcpIntegration):
    id: str = "apify"
    name: str = "Apify"
    description: str = "Web scraping, data extraction, and browser automation"
    docs_url: str = "https://docs.apify.com/platform/integrations/mcp"
    url: str = "https://mcp.apify.com"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
            TokenAuth(
                method="token",
                label="Apify API Token",
                header="Authorization",
                format="Bearer {token}",
            ),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
