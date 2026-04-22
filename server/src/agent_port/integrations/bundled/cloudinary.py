from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
)

_TOOL_CATEGORIES: dict[str, str] = {}


class CloudinaryIntegration(RemoteMcpIntegration):
    id: str = "cloudinary"
    name: str = "Cloudinary"
    description: str = "Media management, image and video optimization platform"
    docs_url: str = "https://cloudinary.com/documentation/cloudinary_llm_mcp"
    url: str = "https://asset-management.mcp.cloudinary.com/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
