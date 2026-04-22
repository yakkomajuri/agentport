from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
    TokenAuth,
)

_TOOL_CATEGORIES: dict[str, str] = {
    # Documents
    "create_documents_from_json": "Documents",
    "create_documents_from_markdown": "Documents",
    "create_version": "Documents",
    "query_documents": "Documents",
    "get_document": "Documents",
    "patch_document_from_json": "Documents",
    "patch_document_from_markdown": "Documents",
    "publish_documents": "Documents",
    "unpublish_documents": "Documents",
    "discard_drafts": "Documents",
    "version_replace_document": "Documents",
    "version_discard": "Documents",
    "version_unpublish_document": "Documents",
    # Schema
    "get_schema": "Schema",
    "list_workspace_schemas": "Schema",
    "deploy_schema": "Schema",
    # Releases
    "create_release": "Releases",
    "list_releases": "Releases",
    # Media
    "generate_image": "Media",
    "transform_image": "Media",
    # Search
    "semantic_search": "Search",
    "list_embeddings_indices": "Search",
    "search_docs": "Search",
    "read_docs": "Search",
    # Projects
    "list_organizations": "Projects",
    "list_projects": "Projects",
    "get_project_studios": "Projects",
    "create_project": "Projects",
    "add_cors_origin": "Projects",
    "whoami": "Projects",
    "list_datasets": "Projects",
    "create_dataset": "Projects",
    "update_dataset": "Projects",
    # Migrations
    "migration_guide": "Migrations",
    # Rules
    "list_sanity_rules": "Rules",
    "get_sanity_rules": "Rules",
}


class SanityIntegration(RemoteMcpIntegration):
    id: str = "sanity"
    name: str = "Sanity"
    description: str = "Headless CMS for structured content"
    docs_url: str = "https://www.sanity.io/docs/ai/mcp-server"
    url: str = "https://mcp.sanity.io"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
            TokenAuth(
                method="token",
                label="Sanity API Token",
                header="Authorization",
                format="Bearer {token}",
            ),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
