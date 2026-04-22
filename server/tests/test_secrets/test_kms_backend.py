import base64
import sys
from unittest.mock import MagicMock, patch

import pytest

from agent_port.models.secret import Secret
from agent_port.secrets.kms import DBKMSSecretsBackend


@pytest.fixture()
def kms_backend():
    mock_client = MagicMock()
    mock_boto3 = MagicMock()
    mock_boto3.client.return_value = mock_client

    with patch.dict(sys.modules, {"boto3": mock_boto3}):
        backend = DBKMSSecretsBackend(key_id="kms-key", region="us-east-1")

    yield backend, mock_client


def test_store_encrypts_secret(kms_backend):
    backend, client = kms_backend
    plaintext_key = b"k" * 32
    client.generate_data_key.return_value = {
        "Plaintext": plaintext_key,
        "CiphertextBlob": b"encrypted-key",
    }

    stored = backend.store("my/key", "secret-value")

    client.generate_data_key.assert_called_once_with(KeyId="kms-key", KeySpec="AES_256")
    assert stored.value is not None
    assert stored.encrypted_data_key == base64.b64encode(b"encrypted-key").decode()
    assert stored.kms_key_id == "kms-key"


def test_retrieve_decrypts_secret(kms_backend):
    backend, client = kms_backend
    plaintext_key = b"k" * 32
    client.generate_data_key.return_value = {
        "Plaintext": plaintext_key,
        "CiphertextBlob": b"encrypted-key",
    }
    stored = backend.store("my/key", "secret-value")
    client.decrypt.return_value = {"Plaintext": plaintext_key}
    secret = Secret(
        kind="test",
        storage_backend="db_kms",
        value=stored.value,
        encrypted_data_key=stored.encrypted_data_key,
        kms_key_id="kms-key",
        value_hash="h",
    )

    result = backend.retrieve(secret)

    assert result == "secret-value"
    client.decrypt.assert_called_once_with(CiphertextBlob=b"encrypted-key")


def test_retrieve_none_without_payload(kms_backend):
    backend, _ = kms_backend
    secret = Secret(
        kind="test",
        storage_backend="db_kms",
        value=None,
        encrypted_data_key=None,
        kms_key_id="kms-key",
        value_hash="h",
    )

    assert backend.retrieve(secret) is None


def test_import_error_without_boto3():
    with patch.dict(sys.modules, {"boto3": None}):
        with pytest.raises(RuntimeError, match="boto3 is required"):
            DBKMSSecretsBackend(key_id="kms-key")
