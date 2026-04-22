from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
    TokenAuth,
)

_TOOL_CATEGORIES: dict[str, str] = {
    # Search
    "search": "Search",
    "lead_search": "Search",
    "activity_search": "Search",
    "paginate_search": "Search",
    # Leads
    "fetch_lead": "Leads",
    "create_lead": "Leads",
    "update_lead": "Leads",
    "delete_lead": "Leads",
    "create_address": "Leads",
    "delete_address": "Leads",
    # Lead statuses
    "fetch_lead_status": "Lead Statuses",
    "find_lead_statuses": "Lead Statuses",
    "create_lead_status": "Lead Statuses",
    "update_lead_status": "Lead Statuses",
    "delete_lead_status": "Lead Statuses",
    # Contacts
    "fetch_contact": "Contacts",
    "create_contact": "Contacts",
    "update_contact": "Contacts",
    "delete_contact": "Contacts",
    # Opportunities
    "fetch_opportunity": "Opportunities",
    "find_opportunities": "Opportunities",
    "create_opportunity": "Opportunities",
    "update_opportunity": "Opportunities",
    "delete_opportunity": "Opportunities",
    "fetch_opportunity_status": "Opportunities",
    "create_opportunity_status_tool": "Opportunities",
    "update_opportunity_status_tool": "Opportunities",
    "delete_opportunity_status_tool": "Opportunities",
    # Pipelines
    "fetch_pipeline_and_opportunity_statuses": "Pipelines",
    "find_pipelines_and_opportunity_statuses": "Pipelines",
    "create_pipeline": "Pipelines",
    "update_pipeline": "Pipelines",
    "delete_pipeline": "Pipelines",
    # Tasks
    "create_task": "Tasks",
    # Activities
    "find_custom_activities": "Activities",
    "find_call_outcomes": "Activities",
    "find_meeting_outcomes": "Activities",
    # Email
    "fetch_email_template": "Email",
    "find_email_templates": "Email",
    "create_email_template": "Email",
    "update_email_template": "Email",
    "delete_email_template": "Email",
    # SMS
    "fetch_sms_template": "SMS",
    "find_sms_templates": "SMS",
    "create_sms_template": "SMS",
    "update_sms_template": "SMS",
    "delete_sms_template": "SMS",
    # Smart Views
    "fetch_lead_smart_view": "Smart Views",
    "find_lead_smart_views": "Smart Views",
    "update_lead_smart_view": "Smart Views",
    "delete_lead_smart_view": "Smart Views",
    # Workflows
    "find_workflows": "Workflows",
    "create_workflow": "Workflows",
    # Custom Fields
    "find_lead_custom_fields": "Custom Fields",
    # Users
    "org_info": "Users",
    "org_users": "Users",
    "find_groups": "Users",
    # Reports
    "aggregation": "Reports",
    "get_fields": "Reports",
    # Documentation
    "close_product_knowledge_search": "Documentation",
    # Scheduling
    "find_scheduling_links": "Scheduling",
    # AI Agents
    "find_agent_configs": "AI Agents",
    # Forms
    "find_forms": "Forms",
    # General
    "fetch": "General",
}


class CloseIntegration(RemoteMcpIntegration):
    id: str = "close"
    name: str = "Close"
    description: str = "Sales CRM and communication platform"
    docs_url: str = "https://help.close.com/docs/mcp-server"
    url: str = "https://mcp.close.com/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
            TokenAuth(
                method="token",
                label="Close API Key",
                header="Authorization",
                format="Bearer {token}",
            ),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
