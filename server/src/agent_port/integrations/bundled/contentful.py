from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
)

_TOOL_CATEGORIES: dict[str, str] = {
    # AI Actions
    "create_ai_action": "AI Actions",
    "delete_ai_action": "AI Actions",
    "get_ai_action": "AI Actions",
    "get_ai_action_invocation": "AI Actions",
    "invoke_ai_action": "AI Actions",
    "list_ai_actions": "AI Actions",
    "publish_ai_action": "AI Actions",
    "unpublish_ai_action": "AI Actions",
    "update_ai_action": "AI Actions",
    # Assets
    "delete_asset": "Assets",
    "get_asset": "Assets",
    "list_assets": "Assets",
    "publish_asset": "Assets",
    "unpublish_asset": "Assets",
    "update_asset": "Assets",
    "upload_asset": "Assets",
    # Content Types
    "create_content_type": "Content Types",
    "delete_content_type": "Content Types",
    "get_content_type": "Content Types",
    "list_content_types": "Content Types",
    "publish_content_type": "Content Types",
    "unpublish_content_type": "Content Types",
    "update_content_type": "Content Types",
    # Context
    "get_initial_context": "Context",
    # Entries
    "create_entry": "Entries",
    "delete_entry": "Entries",
    "get_entry": "Entries",
    "publish_entry": "Entries",
    "search_entries": "Entries",
    "unpublish_entry": "Entries",
    "update_entry": "Entries",
    # Environments
    "create_environment": "Environments",
    "delete_environment": "Environments",
    "list_environments": "Environments",
    # Locales
    "create_locale": "Locales",
    "delete_locale": "Locales",
    "get_locale": "Locales",
    "list_locales": "Locales",
    "update_locale": "Locales",
    # Spaces
    "get_space": "Spaces",
    "list_spaces": "Spaces",
    # Tags
    "create_tag": "Tags",
    "list_tags": "Tags",
}


class ContentfulIntegration(RemoteMcpIntegration):
    id: str = "contentful"
    name: str = "Contentful"
    description: str = "Headless CMS and content platform"
    docs_url: str = "https://www.contentful.com/developers/docs/tools/mcp-server/"
    url: str = "https://mcp.contentful.com/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
