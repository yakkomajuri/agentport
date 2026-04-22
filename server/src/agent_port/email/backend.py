import abc
import logging

logger = logging.getLogger(__name__)


class EmailBackend(abc.ABC):
    @abc.abstractmethod
    def send(self, to: str, subject: str, html: str) -> None: ...
