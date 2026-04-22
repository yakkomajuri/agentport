import atexit

from posthog import Posthog

from agent_port.config import settings

posthog_client = Posthog(
    project_api_key=settings.posthog_project_token,
    host=settings.posthog_host,
    enable_exception_autocapture=True,
)

atexit.register(posthog_client.shutdown)
