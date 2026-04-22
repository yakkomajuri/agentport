from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
    TokenAuth,
)

_TOOL_CATEGORIES: dict[str, str] = {
    # Actions
    "actions-get-all": "Actions",
    "action-create": "Actions",
    "action-get": "Actions",
    "action-update": "Actions",
    "action-delete": "Actions",
    # Activity logs
    "activity-logs-list": "Activity logs",
    # Alerts
    "alerts-list": "Alerts",
    "alert-get": "Alerts",
    "alert-create": "Alerts",
    "alert-update": "Alerts",
    "alert-delete": "Alerts",
    "alert-simulate": "Alerts",
    # Annotations
    "annotations-list": "Annotations",
    "annotation-create": "Annotations",
    "annotation-retrieve": "Annotations",
    "annotations-partial-update": "Annotations",
    "annotation-delete": "Annotations",
    # Cohorts
    "cohorts-list": "Cohorts",
    "cohorts-create": "Cohorts",
    "cohorts-retrieve": "Cohorts",
    "cohorts-partial-update": "Cohorts",
    "cohorts-add-persons-to-static-cohort-partial-update": "Cohorts",
    "cohorts-rm-person-from-static-cohort-partial-update": "Cohorts",
    # Dashboards
    "dashboards-get-all": "Dashboards",
    "dashboard-create": "Dashboards",
    "dashboard-get": "Dashboards",
    "dashboard-update": "Dashboards",
    "dashboard-delete": "Dashboards",
    "dashboard-reorder-tiles": "Dashboards",
    # Data warehouse
    "view-list": "Data warehouse",
    "view-create": "Data warehouse",
    "view-get": "Data warehouse",
    "view-update": "Data warehouse",
    "view-delete": "Data warehouse",
    "view-materialize": "Data warehouse",
    "view-unmaterialize": "Data warehouse",
    "view-run": "Data warehouse",
    "view-run-history": "Data warehouse",
    # Debug
    "debug-mcp-ui-apps": "Debug",
    # Documentation
    "docs-search": "Documentation",
    # Early access features
    "early-access-feature-list": "Early access features",
    "early-access-feature-create": "Early access features",
    "early-access-feature-retrieve": "Early access features",
    "early-access-feature-partial-update": "Early access features",
    "early-access-feature-destroy": "Early access features",
    # Endpoints
    "endpoints-get-all": "Endpoints",
    "endpoint-get": "Endpoints",
    "endpoint-create": "Endpoints",
    "endpoint-update": "Endpoints",
    "endpoint-delete": "Endpoints",
    "endpoint-run": "Endpoints",
    "endpoint-versions": "Endpoints",
    "endpoint-materialization-status": "Endpoints",
    "endpoint-openapi-spec": "Endpoints",
    # Error tracking
    "error-tracking-issues-list": "Error tracking",
    "error-tracking-issues-retrieve": "Error tracking",
    "error-tracking-issues-partial-update": "Error tracking",
    "error-tracking-issues-merge-create": "Error tracking",
    "query-error-tracking-issues": "Error tracking",
    # Events & properties
    "event-definitions-list": "Events & properties",
    "event-definition-update": "Events & properties",
    "properties-list": "Events & properties",
    # Experiments
    "experiment-get-all": "Experiments",
    "experiment-create": "Experiments",
    "experiment-get": "Experiments",
    "experiment-update": "Experiments",
    "experiment-delete": "Experiments",
    "experiment-results-get": "Experiments",
    # Feature flags
    "feature-flag-get-all": "Feature flags",
    "feature-flag-get-definition": "Feature flags",
    "create-feature-flag": "Feature flags",
    "update-feature-flag": "Feature flags",
    "delete-feature-flag": "Feature flags",
    "feature-flags-activity-retrieve": "Feature flags",
    "feature-flags-dependent-flags-retrieve": "Feature flags",
    "feature-flags-status-retrieve": "Feature flags",
    "feature-flags-evaluation-reasons-retrieve": "Feature flags",
    "feature-flags-user-blast-radius-create": "Feature flags",
    "feature-flags-copy-flags-create": "Feature flags",
    "scheduled-changes-list": "Feature flags",
    "scheduled-changes-get": "Feature flags",
    "scheduled-changes-create": "Feature flags",
    "scheduled-changes-update": "Feature flags",
    "scheduled-changes-delete": "Feature flags",
    # Functions (CDP)
    "cdp-functions-list": "Functions",
    "cdp-functions-create": "Functions",
    "cdp-functions-retrieve": "Functions",
    "cdp-functions-partial-update": "Functions",
    "cdp-functions-delete": "Functions",
    "cdp-functions-invocations-create": "Functions",
    "cdp-functions-rearrange-partial-update": "Functions",
    "cdp-function-templates-list": "Function templates",
    "cdp-function-templates-retrieve": "Function templates",
    # Insights & analytics
    "insights-get-all": "Insights",
    "insight-create-from-query": "Insights",
    "insight-get": "Insights",
    "insight-query": "Insights",
    "insight-update": "Insights",
    "insight-delete": "Insights",
    "query-run": "Insights",
    "query-generate-hogql-from-question": "Insights",
    # Integrations
    "integrations-list": "Integrations",
    "integration-get": "Integrations",
    "integration-delete": "Integrations",
    # LLM analytics
    "evaluations-get": "LLM analytics",
    "evaluation-get": "LLM analytics",
    "evaluation-create": "LLM analytics",
    "evaluation-update": "LLM analytics",
    "evaluation-delete": "LLM analytics",
    "evaluation-run": "LLM analytics",
    "evaluation-test-hog": "LLM analytics",
    "get-llm-total-costs-for-project": "LLM analytics",
    "llm-analytics-clustering-jobs-list": "LLM analytics",
    "llm-analytics-clustering-jobs-retrieve": "LLM analytics",
    "llm-analytics-evaluation-summary-create": "LLM analytics",
    "llm-analytics-sentiment-create": "LLM analytics",
    "llm-analytics-summarization-create": "LLM analytics",
    # Logs
    "logs-query": "Logs",
    "logs-list-attributes": "Logs",
    "logs-list-attribute-values": "Logs",
    # Notebooks
    "notebooks-list": "Notebooks",
    "notebooks-create": "Notebooks",
    "notebooks-retrieve": "Notebooks",
    "notebooks-partial-update": "Notebooks",
    "notebooks-destroy": "Notebooks",
    # Organization & project management
    "organization-details-get": "Organization & project",
    "organizations-get": "Organization & project",
    "projects-get": "Organization & project",
    "switch-organization": "Organization & project",
    "switch-project": "Organization & project",
    # Persons
    "persons-list": "Persons",
    "persons-retrieve": "Persons",
    "persons-property-delete": "Persons",
    "persons-property-set": "Persons",
    "persons-bulk-delete": "Persons",
    "persons-cohorts-retrieve": "Persons",
    "persons-values-retrieve": "Persons",
    # Prompts
    "prompt-list": "Prompts",
    "prompt-get": "Prompts",
    "prompt-create": "Prompts",
    "prompt-update": "Prompts",
    "prompt-duplicate": "Prompts",
    # Reverse proxy
    "proxy-list": "Reverse proxy",
    "proxy-get": "Reverse proxy",
    "proxy-create": "Reverse proxy",
    "proxy-retry": "Reverse proxy",
    "proxy-delete": "Reverse proxy",
    # Search
    "entity-search": "Search",
    # Surveys
    "surveys-get-all": "Surveys",
    "survey-create": "Surveys",
    "survey-get": "Surveys",
    "survey-update": "Surveys",
    "survey-delete": "Surveys",
    "survey-stats": "Surveys",
    "surveys-global-stats": "Surveys",
    # Workflows
    "workflows-list": "Workflows",
    "workflows-get": "Workflows",
}


class PostHogIntegration(RemoteMcpIntegration):
    id: str = "posthog"
    name: str = "PostHog"
    description: str = "Product analytics and feature flags"
    docs_url: str = "https://posthog.com/docs/model-context-protocol"
    url: str = "https://mcp.posthog.com/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
            TokenAuth(
                method="token",
                label="PostHog Personal API Key",
                header="Authorization",
                format="Bearer {token}",
            ),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
