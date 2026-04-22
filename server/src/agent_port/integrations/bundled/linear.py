from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
    TokenAuth,
)

_TOOL_CATEGORIES: dict[str, str] = {
    # Issues
    "linear_create_issues": "Issues",
    "linear_search_issues": "Issues",
    "linear_get_issue": "Issues",
    "linear_update_issue": "Issues",
    "linear_delete_issue": "Issues",
    # Comments
    "linear_create_comment": "Comments",
    # Projects
    "linear_list_projects": "Projects",
    "linear_create_project": "Projects",
    "linear_update_project": "Projects",
    # Teams
    "linear_list_teams": "Teams",
    # Cycles
    "linear_list_cycles": "Cycles",
    # Labels
    "linear_list_labels": "Labels",
    # Users
    "linear_get_user": "Users",
    "linear_get_viewer": "Users",
}


class LinearIntegration(RemoteMcpIntegration):
    id: str = "linear"
    name: str = "Linear"
    description: str = "Issue tracking and project management"
    docs_url: str = "https://linear.app/docs/mcp"
    url: str = "https://mcp.linear.app/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
            TokenAuth(
                method="token",
                label="Linear API Key",
                header="Authorization",
                format="Bearer {token}",
            ),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
