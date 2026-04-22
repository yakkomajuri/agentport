from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
)

_TOOL_CATEGORIES: dict[str, str] = {
    # Discovery
    "search": "Discovery",
    "get_from_url": "Discovery",
    "get_context": "Discovery",
    "get_project_context": "Discovery",
    # Analytics
    "get_charts": "Analytics",
    "query_chart": "Analytics",
    "query_charts": "Analytics",
    "query_amplitude_data": "Analytics",
    "render_chart": "Analytics",
    "save_chart_edits": "Analytics",
    # Dashboards
    "get_dashboard": "Dashboards",
    "create_dashboard": "Dashboards",
    "edit_dashboard": "Dashboards",
    # Cohorts
    "get_cohorts": "Cohorts",
    "create_cohort": "Cohorts",
    # Users & events
    "get_users": "Users & events",
    "get_event_properties": "Users & events",
    # Session Replay
    "get_session_replays": "Session Replay",
    "list_session_replays": "Session Replay",
    "get_session_replay_events": "Session Replay",
    # Experiments
    "get_experiments": "Experiments",
    "query_experiment": "Experiments",
    "create_experiment": "Experiments",
    "update_experiment": "Experiments",
    # Feature Flags
    "get_flags": "Feature Flags",
    "create_flags": "Feature Flags",
    "update_flag": "Feature Flags",
    "get_deployments": "Feature Flags",
    # Notebooks
    "create_notebook": "Notebooks",
    "edit_notebook": "Notebooks",
    # Metrics
    "create_metric": "Metrics",
    # Feedback
    "get_feedback_insights": "Feedback",
    "get_feedback_comments": "Feedback",
    "get_feedback_mentions": "Feedback",
    "get_feedback_sources": "Feedback",
    "get_feedback_trends": "Feedback",
    # Agent Analytics
    "get_agent_results": "Agent Analytics",
    "query_agent_analytics_metrics": "Agent Analytics",
    "query_agent_analytics_sessions": "Agent Analytics",
    "query_agent_analytics_spans": "Agent Analytics",
    "get_agent_analytics_conversation": "Agent Analytics",
    "search_agent_analytics_conversations": "Agent Analytics",
    "get_agent_analytics_schema": "Agent Analytics",
}


class AmplitudeIntegration(RemoteMcpIntegration):
    id: str = "amplitude"
    name: str = "Amplitude"
    description: str = "Product analytics, behavioral insights, and experimentation"
    docs_url: str = "https://amplitude.com/docs/amplitude-ai/amplitude-mcp"
    url: str = "https://mcp.amplitude.com/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
