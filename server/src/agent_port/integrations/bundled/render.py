from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    RemoteMcpIntegration,
    TokenAuth,
)

_TOOL_CATEGORIES: dict[str, str] = {
    # Workspaces
    "list_workspaces": "Workspaces",
    "set_workspace": "Workspaces",
    "get_workspace": "Workspaces",
    # Services
    "create_web_service": "Services",
    "create_static_site": "Services",
    "create_cron_job": "Services",
    "create_postgres": "Services",
    "create_key_value": "Services",
    "list_services": "Services",
    "get_service": "Services",
    "update_service_env_vars": "Services",
    # Deploys
    "list_deploys": "Deploys",
    "get_deploy": "Deploys",
    # Logs
    "list_logs": "Logs",
    "list_log_label_values": "Logs",
    # Metrics
    "get_cpu_usage": "Metrics",
    "get_memory_usage": "Metrics",
    "get_instance_count": "Metrics",
    "get_connection_count": "Metrics",
    "get_response_metrics": "Metrics",
    "get_response_times": "Metrics",
    "get_bandwidth": "Metrics",
    # Postgres
    "create_database": "Postgres",
    "list_databases": "Postgres",
    "get_database": "Postgres",
    "run_sql_query": "Postgres",
    # Key Value
    "create_kv_instance": "Key Value",
    "list_kv_instances": "Key Value",
    "get_kv_instance": "Key Value",
}


class RenderIntegration(RemoteMcpIntegration):
    id: str = "render"
    name: str = "Render"
    description: str = "Cloud hosting, deployments, and infrastructure"
    docs_url: str = "https://render.com/docs/mcp-server"
    url: str = "https://mcp.render.com/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            TokenAuth(
                method="token",
                label="Render API Key",
                header="Authorization",
                format="Bearer {token}",
            ),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
