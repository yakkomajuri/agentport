import logging

from agent_port.email.backend import EmailBackend

logger = logging.getLogger(__name__)

_backend: EmailBackend | None = None


def _get_backend() -> EmailBackend | None:
    global _backend
    if _backend is not None:
        return _backend

    from agent_port.config import settings

    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set — emails will not be sent")
        return None

    from agent_port.email.resend_backend import ResendBackend

    _backend = ResendBackend(
        api_key=settings.resend_api_key,
        from_address=settings.email_from,
    )
    return _backend


def send_email(to: str, subject: str, html: str) -> None:
    backend = _get_backend()
    if backend is None:
        logger.warning("No email backend configured — skipping email to %s: %s", to, subject)
        return
    try:
        backend.send(to, subject, html)
    except Exception:
        logger.exception("Failed to send email to %s: %s", to, subject)
