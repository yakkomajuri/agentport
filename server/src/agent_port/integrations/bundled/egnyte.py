from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
    TokenAuth,
)

_TOOL_CATEGORIES: dict[str, str] = {
    # Search
    "search": "Search",
    "advanced_search": "Search",
    # Files
    "fetch": "Files",
    "download_file_by_path": "Files",
    "download_file_by_id": "Files",
    "upload_file": "Files",
    "set_file_metadata": "Files",
    # Folders
    "list_filesystem_by_path": "Folders",
    "create_folder": "Folders",
    # AI
    "ask_document": "AI",
    "summarize_document": "AI",
    "ask_copilot": "AI",
    # Knowledge Base
    "ask_knowledge_base": "Knowledge Base",
    "list_knowledge_bases": "Knowledge Base",
    # Projects
    "list_projects": "Projects",
    # Comments
    "list_comments": "Comments",
    "get_comment": "Comments",
    "create_comment": "Comments",
    # Links
    "list_links": "Links",
    "get_link_details": "Links",
    "create_link": "Links",
}


class EgnyteIntegration(RemoteMcpIntegration):
    id: str = "egnyte"
    name: str = "Egnyte"
    description: str = "Enterprise content management and governance"
    docs_url: str = "https://developers.egnyte.com/docs/Remote_MCP_Server"
    url: str = "https://mcp-server.egnyte.com/sse"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
            TokenAuth(
                method="token",
                label="Egnyte API Key",
                header="Authorization",
                format="Bearer {token}",
            ),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
