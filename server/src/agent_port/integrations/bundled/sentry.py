from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
    TokenAuth,
)

_TOOL_CATEGORIES: dict[str, str] = {
    # Organizations & projects
    "whoami": "Organizations & projects",
    "find_organizations": "Organizations & projects",
    "find_teams": "Organizations & projects",
    "find_projects": "Organizations & projects",
    "create_team": "Organizations & projects",
    "create_project": "Organizations & projects",
    "update_project": "Organizations & projects",
    # Issues
    "get_issue_details": "Issues",
    "get_issue_tag_values": "Issues",
    "update_issue": "Issues",
    "search_issues": "Issues",
    "list_issues": "Issues",
    "analyze_issue_with_seer": "Issues",
    # Events
    "search_events": "Events",
    "list_events": "Events",
    "search_issue_events": "Events",
    "list_issue_events": "Events",
    "get_event_attachment": "Events",
    # Traces & performance
    "get_trace_details": "Traces & performance",
    "get_replay_details": "Traces & performance",
    "get_profile_details": "Traces & performance",
    # Releases
    "find_releases": "Releases",
    # DSNs
    "create_dsn": "DSNs",
    "find_dsns": "DSNs",
    # Documentation
    "search_docs": "Documentation",
    "get_doc": "Documentation",
    # Resources
    "get_sentry_resource": "Resources",
    # Agent
    "use_sentry": "Agent",
}


class SentryIntegration(RemoteMcpIntegration):
    id: str = "sentry"
    name: str = "Sentry"
    description: str = "Error tracking and performance monitoring"
    docs_url: str = "https://mcp.sentry.dev/"
    url: str = "https://mcp.sentry.dev/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
            TokenAuth(
                method="token",
                label="Sentry Auth Token",
                header="Authorization",
                format="Bearer {token}",
            ),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
