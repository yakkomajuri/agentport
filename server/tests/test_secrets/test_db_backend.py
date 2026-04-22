from agent_port.models.secret import Secret
from agent_port.secrets.db import DBSecretsBackend


def test_store_returns_secret_payload():
    backend = DBSecretsBackend()
    stored = backend.store("k", "my-secret")
    assert stored.value == "my-secret"
    assert stored.encrypted_data_key is None
    assert stored.kms_key_id is None


def test_retrieve_returns_stored_value():
    backend = DBSecretsBackend()
    secret = Secret(kind="test", storage_backend="db", value="my-secret", value_hash="h")
    assert backend.retrieve(secret) == "my-secret"


def test_retrieve_none():
    backend = DBSecretsBackend()
    secret = Secret(kind="test", storage_backend="db", value=None, value_hash="h")
    assert backend.retrieve(secret) is None


def test_delete_is_noop():
    backend = DBSecretsBackend()
    secret = Secret(kind="test", storage_backend="db", value=None, value_hash="h")
    backend.delete(secret)  # should not raise
