"""Resend custom integration: email API for transactional and marketing email.

Implements all tools from the Resend MCP server (https://github.com/resend/resend-mcp)
as a CustomIntegration with direct REST API calls.
"""

from typing import Union

import httpx
from pydantic import Field

from agent_port.integrations.bundled.resend.audiences import TOOLS as _AUDIENCE_TOOLS
from agent_port.integrations.bundled.resend.automations import TOOLS as _AUTOMATION_TOOLS
from agent_port.integrations.bundled.resend.broadcasts import TOOLS as _BROADCAST_TOOLS
from agent_port.integrations.bundled.resend.contacts import TOOLS as _CONTACT_TOOLS
from agent_port.integrations.bundled.resend.domains import TOOLS as _DOMAIN_TOOLS
from agent_port.integrations.bundled.resend.emails import TOOLS as _EMAIL_TOOLS
from agent_port.integrations.bundled.resend.management import TOOLS as _MANAGEMENT_TOOLS
from agent_port.integrations.bundled.resend.templates import TOOLS as _TEMPLATE_TOOLS
from agent_port.integrations.types import (
    ApiTool,
    AuthMethod,
    CustomIntegration,
    CustomTool,
    TokenAuth,
)

_ALL_TOOLS: list[Union[ApiTool, CustomTool]] = [
    *_EMAIL_TOOLS,
    *_BROADCAST_TOOLS,
    *_CONTACT_TOOLS,
    *_DOMAIN_TOOLS,
    *_TEMPLATE_TOOLS,
    *_AUDIENCE_TOOLS,
    *_AUTOMATION_TOOLS,
    *_MANAGEMENT_TOOLS,
]

_TOOL_CATEGORIES: dict[str, str] = {
    # Emails
    "send_email": "Emails",
    "send_batch_emails": "Emails",
    "list_emails": "Emails",
    "get_email": "Emails",
    "cancel_email": "Emails",
    "update_email": "Emails",
    "list_received_emails": "Emails",
    "get_received_email": "Emails",
    "list_received_email_attachments": "Emails",
    "get_received_email_attachment": "Emails",
    "list_sent_email_attachments": "Emails",
    "get_sent_email_attachment": "Emails",
    # Broadcasts
    "create_broadcast": "Broadcasts",
    "send_broadcast": "Broadcasts",
    "list_broadcasts": "Broadcasts",
    "get_broadcast": "Broadcasts",
    "update_broadcast": "Broadcasts",
    "remove_broadcast": "Broadcasts",
    "compose_broadcast": "Broadcasts",
    # Contacts
    "create_contact": "Contacts",
    "list_contacts": "Contacts",
    "get_contact": "Contacts",
    "update_contact": "Contacts",
    "remove_contact": "Contacts",
    "add_contact_to_segment": "Contacts",
    "remove_contact_from_segment": "Contacts",
    "list_contact_segments": "Contacts",
    "list_contact_topics": "Contacts",
    "update_contact_topics": "Contacts",
    # Domains
    "create_domain": "Domains",
    "list_domains": "Domains",
    "get_domain": "Domains",
    "update_domain": "Domains",
    "remove_domain": "Domains",
    "verify_domain": "Domains",
    # Templates
    "create_template": "Templates",
    "list_templates": "Templates",
    "get_template": "Templates",
    "update_template": "Templates",
    "remove_template": "Templates",
    "compose_template": "Templates",
    "publish_template": "Templates",
    "duplicate_template": "Templates",
    # Segments
    "create_segment": "Segments",
    "list_segments": "Segments",
    "get_segment": "Segments",
    "remove_segment": "Segments",
    # Contact Properties
    "create_contact_property": "Contact Properties",
    "list_contact_properties": "Contact Properties",
    "get_contact_property": "Contact Properties",
    "update_contact_property": "Contact Properties",
    "remove_contact_property": "Contact Properties",
    # Topics
    "create_topic": "Topics",
    "list_topics": "Topics",
    "get_topic": "Topics",
    "update_topic": "Topics",
    "remove_topic": "Topics",
    # Automations
    "create_automation": "Automations",
    "update_automation": "Automations",
    "get_automation": "Automations",
    "remove_automation": "Automations",
    "get_automation_runs": "Automations",
    # Events
    "send_event": "Events",
    "manage_events": "Events",
    # API Keys
    "create_api_key": "API Keys",
    "list_api_keys": "API Keys",
    "remove_api_key": "API Keys",
    # Webhooks
    "create_webhook": "Webhooks",
    "list_webhooks": "Webhooks",
    "get_webhook": "Webhooks",
    "update_webhook": "Webhooks",
    "remove_webhook": "Webhooks",
    # Logs
    "list_logs": "Logs",
    "get_log": "Logs",
    # Editor
    "get_tiptap_json_content": "Editor",
    "connect_to_editor": "Editor",
    "disconnect_from_editor": "Editor",
}


class ResendIntegration(CustomIntegration):
    id: str = "resend"
    name: str = "Resend"
    description: str = "Email API for transactional and marketing email"
    docs_url: str = "https://resend.com/docs/api-reference"
    base_url: str = "https://api.resend.com"
    auth: list[AuthMethod] = Field(
        default=[
            TokenAuth(
                method="token",
                label="Resend API Key",
                header="Authorization",
                format="Bearer {token}",
            ),
        ]
    )
    tools: list[Union[ApiTool, CustomTool]] = Field(default=_ALL_TOOLS)
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)

    async def validate_auth(self, token: str) -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                "https://api.resend.com/domains",
                headers={"Authorization": f"Bearer {token}"},
            )
        if r.status_code in (401, 403):
            raise ValueError("Resend rejected the API key")
        if r.status_code >= 400:
            raise ValueError(f"Resend returned {r.status_code}: {r.text[:200]}")
