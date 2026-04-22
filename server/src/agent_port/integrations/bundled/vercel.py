from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
    TokenAuth,
)

_TOOL_CATEGORIES: dict[str, str] = {
    # Documentation
    "search_documentation": "Documentation",
    # Project management
    "list_teams": "Project management",
    "list_projects": "Project management",
    "get_project": "Project management",
    # Deployments
    "list_deployments": "Deployments",
    "get_deployment": "Deployments",
    "get_deployment_build_logs": "Deployments",
    "get_runtime_logs": "Deployments",
    # Domain management
    "check_domain_availability_and_price": "Domain management",
    "buy_domain": "Domain management",
    # Access
    "get_access_to_vercel_url": "Access",
    "web_fetch_vercel_url": "Access",
    # CLI
    "use_vercel_cli": "CLI",
    "deploy_to_vercel": "CLI",
}


class VercelIntegration(RemoteMcpIntegration):
    id: str = "vercel"
    name: str = "Vercel"
    description: str = "Frontend deployment platform and developer cloud"
    docs_url: str = "https://vercel.com/docs/agent-resources/vercel-mcp"
    url: str = "https://mcp.vercel.com/"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
            TokenAuth(
                method="token",
                label="Vercel Personal Access Token",
                header="Authorization",
                format="Bearer {token}",
            ),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
