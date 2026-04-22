from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
    TokenAuth,
)

_TOOL_CATEGORIES: dict[str, str] = {}


class HuggingFaceIntegration(RemoteMcpIntegration):
    id: str = "huggingface"
    name: str = "Hugging Face"
    description: str = "AI model hub for machine learning and data science"
    docs_url: str = "https://huggingface.co/docs/hub/en/hf-mcp-server"
    url: str = "https://huggingface.co/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
            TokenAuth(
                method="token",
                label="Hugging Face Access Token",
                header="Authorization",
                format="Bearer {token}",
            ),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
