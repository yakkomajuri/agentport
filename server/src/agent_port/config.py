from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv(override=True)


class Settings(BaseSettings):
    dev: bool = False
    database_url: str = "sqlite:///agent_port.db"
    base_url: str = "http://localhost:4747"
    oauth_callback_url: str = "http://localhost:4747/api/auth/callback"
    is_self_hosted: bool = False
    is_cloud: bool = False
    block_signups: bool = False
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7
    # Separate, deliberately short TTL for admin-to-user impersonation tokens.
    # A stolen impersonation bearer grants full account access until this
    # window expires, so keep it under an hour.
    impersonation_ttl_minutes: int = 30
    ui_base_url: str = "http://localhost:5173"
    approval_expiry_minutes: int = 10
    # Long-poll budget for agentport__await_approval. Kept under the typical
    # MCP client 300s request timeout so the agent gets a graceful "still
    # pending" response and can loop back in without the client disconnecting.
    approval_long_poll_timeout_seconds: int = 240

    # Email
    resend_api_key: str = ""
    email_from: str = "noreply@example.com"
    skip_email_verification: bool = False

    # PostHog
    posthog_project_token: str = ""
    posthog_host: str = "https://us.i.posthog.com"

    # Google sign-in (login with Google for the agent-port UI). Completely
    # independent from the Google integration's OAuth credentials.
    google_login_client_id: str = ""
    google_login_client_secret: str = ""

    # Secrets backend: "db" (default) or "db_kms".
    secrets_backend: str = "db"
    # AWS KMS options (only used when secrets_backend = "db_kms").
    secrets_kms_key_id: str = ""
    secrets_kms_region: str = ""

    # Stripe billing (cloud only — self-hosted installs leave stripe_api_key empty).
    stripe_api_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_plus: str = ""
    enterprise_contact_email: str = "sales@skaldlabs.io"

    def billing_enabled(self) -> bool:
        return self.is_cloud and bool(self.stripe_api_key) and bool(self.stripe_price_plus)

    def get_oauth_credentials(self, provider: str) -> tuple[str, str] | None:
        """Look up OAuth client_id and client_secret for a provider."""
        import os

        prefix = f"OAUTH_{provider.upper()}_"
        client_id = os.environ.get(f"{prefix}CLIENT_ID", "")
        client_secret = os.environ.get(f"{prefix}CLIENT_SECRET", "")
        if client_id and client_secret:
            return client_id, client_secret
        return None


settings = Settings()
