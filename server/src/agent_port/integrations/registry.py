from agent_port.integrations.bundled.amplitude import AmplitudeIntegration
from agent_port.integrations.bundled.apify import ApifyIntegration
from agent_port.integrations.bundled.asana import AsanaIntegration
from agent_port.integrations.bundled.atlassian import AtlassianIntegration
from agent_port.integrations.bundled.attio import AttioIntegration
from agent_port.integrations.bundled.axiom import AxiomIntegration
from agent_port.integrations.bundled.calendly import CalendlyIntegration
from agent_port.integrations.bundled.close import CloseIntegration
from agent_port.integrations.bundled.cloudflare import CloudflareIntegration
from agent_port.integrations.bundled.cloudinary import CloudinaryIntegration
from agent_port.integrations.bundled.contentful import ContentfulIntegration
from agent_port.integrations.bundled.datadog import DatadogIntegration
from agent_port.integrations.bundled.egnyte import EgnyteIntegration
from agent_port.integrations.bundled.exa import ExaIntegration
from agent_port.integrations.bundled.fireflies import FirefliesIntegration
from agent_port.integrations.bundled.github import GitHubIntegration
from agent_port.integrations.bundled.gmail import GmailIntegration
from agent_port.integrations.bundled.google_calendar import GoogleCalendarIntegration
from agent_port.integrations.bundled.granola import GranolaIntegration
from agent_port.integrations.bundled.huggingface import HuggingFaceIntegration
from agent_port.integrations.bundled.intercom import IntercomIntegration
from agent_port.integrations.bundled.launchdarkly import LaunchDarklyIntegration
from agent_port.integrations.bundled.linear import LinearIntegration
from agent_port.integrations.bundled.mercury import MercuryIntegration
from agent_port.integrations.bundled.mixpanel import MixpanelIntegration
from agent_port.integrations.bundled.monday import MondayIntegration
from agent_port.integrations.bundled.neon import NeonIntegration
from agent_port.integrations.bundled.netlify import NetlifyIntegration
from agent_port.integrations.bundled.notion import NotionIntegration
from agent_port.integrations.bundled.posthog import PostHogIntegration
from agent_port.integrations.bundled.prisma import PrismaIntegration
from agent_port.integrations.bundled.ramp import RampIntegration
from agent_port.integrations.bundled.render import RenderIntegration
from agent_port.integrations.bundled.resend import ResendIntegration
from agent_port.integrations.bundled.sanity import SanityIntegration
from agent_port.integrations.bundled.semgrep import SemgrepIntegration
from agent_port.integrations.bundled.sentry import SentryIntegration
from agent_port.integrations.bundled.slack import SlackIntegration
from agent_port.integrations.bundled.square import SquareIntegration
from agent_port.integrations.bundled.stripe import StripeIntegration
from agent_port.integrations.bundled.stytch import StytchIntegration
from agent_port.integrations.bundled.supabase import SupabaseIntegration
from agent_port.integrations.bundled.tally import TallyIntegration
from agent_port.integrations.bundled.telnyx import TelnyxIntegration
from agent_port.integrations.bundled.thoughtspot import ThoughtSpotIntegration
from agent_port.integrations.bundled.vercel import VercelIntegration
from agent_port.integrations.bundled.webflow import WebflowIntegration
from agent_port.integrations.bundled.wix import WixIntegration
from agent_port.integrations.bundled.zapier import ZapierIntegration
from agent_port.integrations.types import (
    Integration,
    OAuthAuth,
    RemoteMcpIntegration,
    TokenAuth,
)

_INTEGRATIONS: dict[str, Integration] = {
    i.id: i
    for i in [
        AmplitudeIntegration(),
        ApifyIntegration(),
        AsanaIntegration(),
        AtlassianIntegration(),
        AttioIntegration(),
        AxiomIntegration(),
        CalendlyIntegration(),
        CloseIntegration(),
        CloudflareIntegration(),
        CloudinaryIntegration(),
        ContentfulIntegration(),
        DatadogIntegration(),
        EgnyteIntegration(),
        ExaIntegration(),
        FirefliesIntegration(),
        GitHubIntegration(),
        GranolaIntegration(),
        GmailIntegration(),
        GoogleCalendarIntegration(),
        HuggingFaceIntegration(),
        IntercomIntegration(),
        LaunchDarklyIntegration(),
        LinearIntegration(),
        MercuryIntegration(),
        MixpanelIntegration(),
        MondayIntegration(),
        NeonIntegration(),
        NetlifyIntegration(),
        NotionIntegration(),
        PostHogIntegration(),
        PrismaIntegration(),
        RampIntegration(),
        RenderIntegration(),
        ResendIntegration(),
        SanityIntegration(),
        SemgrepIntegration(),
        SentryIntegration(),
        SlackIntegration(),
        SquareIntegration(),
        StripeIntegration(),
        StytchIntegration(),
        SupabaseIntegration(),
        TallyIntegration(),
        TelnyxIntegration(),
        ThoughtSpotIntegration(),
        VercelIntegration(),
        WebflowIntegration(),
        WixIntegration(),
        ZapierIntegration(),
    ]
}


CUSTOM_PREFIX = "custom_"


def _custom_row_to_integration(row) -> RemoteMcpIntegration:
    from agent_port.integrations.types import AuthMethod

    auth: list[AuthMethod] = []
    if row.auth_method == "token":
        auth.append(
            TokenAuth(
                method="token",
                label="API token",
                header=row.token_header,
                format=row.token_format,
            )
        )
    elif row.auth_method == "oauth":
        # No provider set → install will fall through to MCP discovery + DCR
        # against the user's URL.
        auth.append(OAuthAuth(method="oauth"))

    return RemoteMcpIntegration(
        id=row.integration_id,
        name=row.name,
        description=row.description,
        url=row.url,
        auth=auth,
    )


def _load_custom_row(integration_id: str, org_id) -> RemoteMcpIntegration | None:
    from sqlmodel import Session, select

    from agent_port.db import engine
    from agent_port.models.custom_mcp_integration import CustomMcpIntegration

    with Session(engine) as session:
        row = session.exec(  # noqa: S608
            select(CustomMcpIntegration)
            .where(CustomMcpIntegration.org_id == org_id)
            .where(CustomMcpIntegration.integration_id == integration_id)
        ).first()
        if not row:
            return None
        return _custom_row_to_integration(row)


def _load_custom_rows_for_org(org_id) -> list[RemoteMcpIntegration]:
    from sqlmodel import Session, select

    from agent_port.db import engine
    from agent_port.models.custom_mcp_integration import CustomMcpIntegration

    with Session(engine) as session:
        rows = session.exec(  # noqa: S608
            select(CustomMcpIntegration).where(CustomMcpIntegration.org_id == org_id)
        ).all()
        return [_custom_row_to_integration(r) for r in rows]


def get(integration_id: str, org_id=None) -> Integration | None:
    """Look up an integration by id.

    Bundled integrations are always available. Custom (user-defined) integrations
    require an org_id; without it, ids beginning with custom_ return None.
    """
    if integration_id in _INTEGRATIONS:
        return _INTEGRATIONS[integration_id]
    if org_id is not None and integration_id.startswith(CUSTOM_PREFIX):
        return _load_custom_row(integration_id, org_id)
    return None


def list_all(org_id=None) -> list[Integration]:
    bundled = list(_INTEGRATIONS.values())
    if org_id is None:
        return bundled
    return bundled + _load_custom_rows_for_org(org_id)
