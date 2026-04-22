from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
)

_TOOL_CATEGORIES: dict[str, str] = {
    # Projects
    "createProject": "Projects",
    "listProjects": "Projects",
    # SDK Configuration
    "getConsumerSDKConfig": "SDK Configuration",
    "updateConsumerSDKConfig": "SDK Configuration",
    "getB2BSDKConfig": "SDK Configuration",
    "updateB2BSDKConfig": "SDK Configuration",
    # Public Tokens
    "getAllPublicTokens": "Public Tokens",
    "createPublicToken": "Public Tokens",
    "deletePublicToken": "Public Tokens",
    # Redirect URLs
    "getAllRedirectURLs": "Redirect URLs",
    "createRedirectURLs": "Redirect URLs",
    "deleteRedirectURL": "Redirect URLs",
    # Secrets
    "createSecret": "Secrets",
    "getSecret": "Secrets",
    "getAllSecrets": "Secrets",
    "deleteSecret": "Secrets",
    # Email Templates
    "getAllEmailTemplates": "Email Templates",
    "getEmailTemplate": "Email Templates",
    "createEmailTemplate": "Email Templates",
    "updateEmailTemplate": "Email Templates",
    "deleteEmailTemplate": "Email Templates",
}


class StytchIntegration(RemoteMcpIntegration):
    id: str = "stytch"
    name: str = "Stytch"
    description: str = "Authentication, identity, and user management"
    docs_url: str = "https://stytch.com/docs/workspace-management/stytch-mcp"
    url: str = "https://mcp.stytch.dev/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
