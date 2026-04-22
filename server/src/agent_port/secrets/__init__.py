from agent_port.config import settings
from agent_port.secrets.base import SecretsBackend, StoredSecret
from agent_port.secrets.db import DBSecretsBackend


def _build_backend() -> SecretsBackend:
    backend = settings.secrets_backend
    if backend == "db":
        return DBSecretsBackend()
    if backend == "db_kms":
        from agent_port.secrets.kms import DBKMSSecretsBackend

        return DBKMSSecretsBackend(
            key_id=settings.secrets_kms_key_id,
            region=settings.secrets_kms_region or None,
        )
    raise ValueError(f"Unknown SECRETS_BACKEND '{backend}'. Supported: db, db_kms")


secrets_backend: SecretsBackend = _build_backend()

__all__ = ["SecretsBackend", "StoredSecret", "secrets_backend"]
