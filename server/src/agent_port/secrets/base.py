from abc import ABC, abstractmethod
from dataclasses import dataclass

from agent_port.models.secret import Secret


@dataclass
class StoredSecret:
    value: str | None
    encrypted_data_key: str | None
    kms_key_id: str | None


class SecretsBackend(ABC):
    """Abstract interface for storing and retrieving durable secret payloads."""

    @abstractmethod
    def store(self, ref: str, value: str) -> StoredSecret:
        """Persist *value* and return backend-specific storage metadata."""
        ...

    @abstractmethod
    def retrieve(self, secret: Secret) -> str | None:
        """Return the plaintext secret for the given record."""
        ...

    @abstractmethod
    def delete(self, secret: Secret) -> None:
        """Remove the secret from the backend."""
        ...
