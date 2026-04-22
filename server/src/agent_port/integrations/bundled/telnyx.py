from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
    TokenAuth,
)

_TOOL_CATEGORIES: dict[str, str] = {
    # Assistants
    "create_assistant": "Assistants",
    "list_assistants": "Assistants",
    "get_assistant": "Assistants",
    "update_assistant": "Assistants",
    "delete_assistant": "Assistants",
    "get_assistant_texml": "Assistants",
    # Call Control
    "make_call": "Call Control",
    "hangup_call": "Call Control",
    "transfer_call": "Call Control",
    "play_audio": "Call Control",
    "stop_audio": "Call Control",
    "send_dtmf": "Call Control",
    "speak_text": "Call Control",
    # Messaging
    "send_message": "Messaging",
    "get_message": "Messaging",
    # WhatsApp
    "send_whatsapp_message": "WhatsApp",
    "list_wabas": "WhatsApp",
    "list_message_templates": "WhatsApp",
    "create_message_template": "WhatsApp",
    "get_template_details": "WhatsApp",
    "list_whatsapp_numbers": "WhatsApp",
    "get_business_profile": "WhatsApp",
    "update_business_profile": "WhatsApp",
    # Phone Numbers
    "list_phone_numbers": "Phone Numbers",
    "buy_phone_number": "Phone Numbers",
    "update_phone_number": "Phone Numbers",
    "list_available_phone_numbers": "Phone Numbers",
    # Connections
    "list_connections": "Connections",
    "get_connection": "Connections",
    "update_connection": "Connections",
    # Cloud Storage
    "create_bucket": "Cloud Storage",
    "list_buckets": "Cloud Storage",
    "upload_file": "Cloud Storage",
    "download_file": "Cloud Storage",
    "list_objects": "Cloud Storage",
    "delete_object": "Cloud Storage",
    "get_bucket_location": "Cloud Storage",
    # Embeddings
    "list_embedded_buckets": "Embeddings",
    "scrape_and_embed_url": "Embeddings",
    "create_embeddings": "Embeddings",
    # Secrets
    "list_secrets": "Secrets",
    "create_secret": "Secrets",
    "delete_secret": "Secrets",
}


class TelnyxIntegration(RemoteMcpIntegration):
    id: str = "telnyx"
    name: str = "Telnyx"
    description: str = "Communications APIs for SMS, voice, and phone numbers"
    docs_url: str = "https://developers.telnyx.com/development/mcp/local-mcp"
    url: str = "https://api.telnyx.com/v2/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
            TokenAuth(
                method="token",
                label="Telnyx API Key",
                header="Authorization",
                format="Bearer {token}",
            ),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
