from agent_port.models.secret import Secret
from agent_port.secrets.base import SecretsBackend, StoredSecret


class DBSecretsBackend(SecretsBackend):
    """Secrets stay in the Secret.value column."""

    def store(self, ref: str, value: str) -> StoredSecret:
        return StoredSecret(value=value, encrypted_data_key=None, kms_key_id=None)

    def retrieve(self, secret: Secret) -> str | None:
        return secret.value

    def delete(self, secret: Secret) -> None:
        pass
