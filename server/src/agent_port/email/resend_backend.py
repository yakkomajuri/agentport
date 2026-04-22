import logging

import resend

from agent_port.email.backend import EmailBackend

logger = logging.getLogger(__name__)


class ResendBackend(EmailBackend):
    def __init__(self, api_key: str, from_address: str) -> None:
        self.from_address = from_address
        resend.api_key = api_key

    def send(self, to: str, subject: str, html: str) -> None:
        resend.Emails.send(
            {
                "from": self.from_address,
                "to": [to],
                "subject": subject,
                "html": html,
            }
        )
        logger.info("Email sent to %s: %s", to, subject)
