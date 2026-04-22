from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
    TokenAuth,
)

_TOOL_CATEGORIES: dict[str, str] = {
    # Dashboards
    "createDashboard": "Dashboards",
    "deleteDashboard": "Dashboards",
    "exportDashboard": "Dashboards",
    "getDashboard": "Dashboards",
    "listDashboards": "Dashboards",
    "updateDashboard": "Dashboards",
    # Datasets
    "getDatasetSchema": "Datasets",
    "listDatasets": "Datasets",
    # Metrics
    "getMetricTagValues": "Metrics",
    "listMetricTags": "Metrics",
    "listMetrics": "Metrics",
    "searchMetrics": "Metrics",
    "queryMetrics": "Metrics",
    # Queries
    "queryApl": "Queries",
    "getSavedQueries": "Queries",
    # Monitors
    "getMonitors": "Monitors",
    "getMonitorsHistory": "Monitors",
}


class AxiomIntegration(RemoteMcpIntegration):
    id: str = "axiom"
    name: str = "Axiom"
    description: str = "Observability, log management, and data analytics"
    docs_url: str = "https://axiom.co/docs/console/intelligence/mcp-server"
    url: str = "https://mcp.axiom.co/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
            TokenAuth(
                method="token",
                label="Axiom Personal Access Token",
                header="Authorization",
                format="Bearer {token}",
            ),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
