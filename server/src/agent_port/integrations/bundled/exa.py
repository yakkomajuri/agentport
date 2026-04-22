from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    RemoteMcpIntegration,
    TokenAuth,
)

_TOOL_CATEGORIES: dict[str, str] = {
    # Search
    "web_search_exa": "Search",
    "web_search_advanced_exa": "Search",
    # Content
    "web_fetch_exa": "Content",
    # Deprecated – Search
    "get_code_context_exa": "Search",
    "company_research_exa": "Search",
    "people_search_exa": "Search",
    "linkedin_search_exa": "Search",
    "deep_search_exa": "Search",
    # Deprecated – Content
    "crawling_exa": "Content",
    # Deprecated – Research
    "deep_researcher_start": "Research",
    "deep_researcher_check": "Research",
}


class ExaIntegration(RemoteMcpIntegration):
    id: str = "exa"
    name: str = "Exa"
    description: str = "AI-powered web search and content retrieval"
    docs_url: str = "https://exa.ai/docs/reference/exa-mcp"
    url: str = "https://mcp.exa.ai/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            TokenAuth(
                method="token",
                label="Exa API Key",
                header="x-api-key",
                format="{token}",
            ),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
