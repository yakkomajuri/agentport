from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
    TokenAuth,
)

_TOOL_CATEGORIES: dict[str, str] = {
    # Core
    "search_datadog_events": "Core",
    "get_datadog_incident": "Core",
    "get_datadog_metric": "Core",
    "get_datadog_metric_context": "Core",
    "search_datadog_monitors": "Core",
    "get_datadog_trace": "Core",
    "search_datadog_dashboards": "Core",
    "get_datadog_notebook": "Core",
    "search_datadog_notebooks": "Core",
    "search_datadog_hosts": "Core",
    "search_datadog_incidents": "Core",
    "search_datadog_metrics": "Core",
    "search_datadog_services": "Core",
    "search_datadog_service_dependencies": "Core",
    "search_datadog_spans": "Core",
    "analyze_datadog_logs": "Core",
    "search_datadog_logs": "Core",
    "search_datadog_rum_events": "Core",
    "create_datadog_notebook": "Core",
    "edit_datadog_notebook": "Core",
    # Alerting
    "validate_datadog_monitor": "Alerting",
    "get_datadog_monitor_templates": "Alerting",
    "search_datadog_monitor_groups": "Alerting",
    # APM
    "apm_search_spans": "APM",
    "apm_explore_trace": "APM",
    "apm_trace_summary": "APM",
    "apm_trace_comparison": "APM",
    "apm_analyze_trace_metrics": "APM",
    "apm_discover_span_tags": "APM",
    "apm_get_primary_tag_keys": "APM",
    "apm_search_watchdog_stories": "APM",
    "apm_get_watchdog_story": "APM",
    "apm_search_change_stories": "APM",
    "apm_latency_bottleneck_analysis": "APM",
    "apm_latency_tag_analysis": "APM",
    "apm_search_recommendations": "APM",
    "apm_get_recommendation": "APM",
    "apm_investigation_methodology": "APM",
    # Cases
    "search_datadog_cases": "Cases",
    "get_datadog_case": "Cases",
    "create_datadog_case": "Cases",
    "update_datadog_case": "Cases",
    "add_comment_to_datadog_case": "Cases",
    "link_jira_issue_to_datadog_case": "Cases",
    "list_datadog_case_projects": "Cases",
    "get_datadog_case_project": "Cases",
    "search_datadog_users": "Cases",
    # Database monitoring
    "search_datadog_dbm_plans": "Database monitoring",
    "search_datadog_dbm_samples": "Database monitoring",
    # DDSQL
    "ddsql_get_spec": "DDSQL",
    "ddsql_schema_search_tables": "DDSQL",
    "ddsql_schema_get_table_columns": "DDSQL",
    "ddsql_schema_search_unstructured_fields": "DDSQL",
    "ddsql_run_query": "DDSQL",
    "ddsql_create_link": "DDSQL",
    # Error tracking
    "search_datadog_error_tracking_issues": "Error tracking",
    "get_datadog_error_tracking_issue": "Error tracking",
    # Feature flags
    "list_datadog_feature_flags": "Feature flags",
    "get_datadog_feature_flag": "Feature flags",
    "create_datadog_feature_flag": "Feature flags",
    "list_datadog_feature_flag_environments": "Feature flags",
    "list_datadog_feature_flag_allocations": "Feature flags",
    "update_datadog_feature_flag_environment": "Feature flags",
    "check_datadog_flag_implementation": "Feature flags",
    "sync_datadog_feature_flag_allocations": "Feature flags",
    # Networks
    "analyze_cloud_network_monitoring": "Networks",
    "search_ndm_devices": "Networks",
    "get_ndm_device": "Networks",
    "search_ndm_interfaces": "Networks",
    # Onboarding
    "browser_onboarding": "Onboarding",
    "devices_onboarding": "Onboarding",
    "kubernetes_onboarding": "Onboarding",
    "llm_observability_onboarding": "Onboarding",
    "test_optimization_onboarding": "Onboarding",
    "serverless_onboarding": "Onboarding",
    "source_map_uploads": "Onboarding",
    # Security
    "datadog_secrets_scan": "Security",
    "search_datadog_security_signals": "Security",
    "security_findings_schema": "Security",
    "analyze_security_findings": "Security",
    "search_security_findings": "Security",
    # Software delivery
    "search_datadog_ci_pipeline_events": "Software delivery",
    "aggregate_datadog_ci_pipeline_events": "Software delivery",
    "get_datadog_flaky_tests": "Software delivery",
    "aggregate_datadog_test_events": "Software delivery",
    "search_datadog_test_events": "Software delivery",
    "get_datadog_code_coverage_branch_summary": "Software delivery",
    "get_datadog_code_coverage_commit_summary": "Software delivery",
    # Synthetics
    "get_synthetics_tests": "Synthetics",
    "edit_synthetics_tests": "Synthetics",
    "synthetics_test_wizard": "Synthetics",
    # Workflows
    "list_datadog_workflows": "Workflows",
    "get_datadog_workflow": "Workflows",
    "execute_datadog_workflow": "Workflows",
    "get_datadog_workflow_instance": "Workflows",
    "update_datadog_workflow_with_agent_trigger": "Workflows",
}


class DatadogIntegration(RemoteMcpIntegration):
    id: str = "datadog"
    name: str = "Datadog"
    description: str = "Cloud monitoring, observability, and security platform"
    docs_url: str = "https://docs.datadoghq.com/bits_ai/mcp_server/"
    url: str = "https://mcp.datadoghq.com/api/unstable/mcp-server/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
            TokenAuth(
                method="token",
                label="Datadog API Key",
                header="DD_API_KEY",
                format="{token}",
            ),
            TokenAuth(
                method="token",
                label="Datadog Application Key",
                header="DD_APPLICATION_KEY",
                format="{token}",
            ),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
