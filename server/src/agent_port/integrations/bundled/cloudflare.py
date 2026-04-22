from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
    TokenAuth,
)

_TOOL_CATEGORIES: dict[str, str] = {
    # Accounts
    "accounts_list": "Accounts",
    "set_active_account": "Accounts",
    # Workers
    "workers_list": "Workers",
    "workers_get_worker": "Workers",
    "workers_get_worker_code": "Workers",
    # KV
    "kv_namespaces_list": "KV",
    "kv_namespace_create": "KV",
    "kv_namespace_delete": "KV",
    "kv_namespace_get": "KV",
    "kv_namespace_update": "KV",
    # R2
    "r2_buckets_list": "R2",
    "r2_bucket_create": "R2",
    "r2_bucket_get": "R2",
    "r2_bucket_delete": "R2",
    "r2_bucket_cors_get": "R2",
    "r2_bucket_cors_update": "R2",
    "r2_bucket_cors_delete": "R2",
    "r2_bucket_domains_list": "R2",
    "r2_bucket_domains_get": "R2",
    "r2_bucket_domains_create": "R2",
    "r2_bucket_domains_delete": "R2",
    "r2_bucket_domains_update": "R2",
    "r2_bucket_event_notifications_get": "R2",
    "r2_bucket_event_notifications_update": "R2",
    "r2_bucket_event_notifications_delete": "R2",
    "r2_bucket_locks_get": "R2",
    "r2_bucket_locks_update": "R2",
    "r2_bucket_temporary_credentials_create": "R2",
    "r2_metrics_list": "R2",
    "r2_sippy_get": "R2",
    "r2_sippy_update": "R2",
    "r2_sippy_delete": "R2",
    # D1
    "d1_databases_list": "D1",
    "d1_database_create": "D1",
    "d1_database_delete": "D1",
    "d1_database_get": "D1",
    "d1_database_query": "D1",
    # Hyperdrive
    "hyperdrive_configs_list": "Hyperdrive",
    "hyperdrive_config_create": "Hyperdrive",
    "hyperdrive_config_delete": "Hyperdrive",
    "hyperdrive_config_get": "Hyperdrive",
    "hyperdrive_config_edit": "Hyperdrive",
    # Documentation
    "search_cloudflare_documentation": "Documentation",
    "migrate_pages_to_workers_guide": "Documentation",
}


class CloudflareIntegration(RemoteMcpIntegration):
    id: str = "cloudflare"
    name: str = "Cloudflare"
    description: str = "Workers, KV, R2, D1, and developer platform"
    docs_url: str = "https://github.com/cloudflare/mcp-server-cloudflare"
    url: str = "https://bindings.mcp.cloudflare.com/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
            TokenAuth(
                method="token",
                label="Cloudflare API Token",
                header="Authorization",
                format="Bearer {token}",
            ),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
