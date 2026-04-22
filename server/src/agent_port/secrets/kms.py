import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from agent_port.models.secret import Secret
from agent_port.secrets.base import SecretsBackend, StoredSecret


class DBKMSSecretsBackend(SecretsBackend):
    """Store ciphertext in the database and protect data keys with AWS KMS."""

    def __init__(self, key_id: str, region: str | None = None) -> None:
        if not key_id:
            raise RuntimeError("SECRETS_KMS_KEY_ID is required when SECRETS_BACKEND=db_kms")
        try:
            import boto3
        except ImportError:
            raise RuntimeError(
                "boto3 is required for the db_kms secrets backend. "
                "Install it with: uv sync --extra aws"
            )
        kwargs: dict = {}
        if region:
            kwargs["region_name"] = region
        self._client = boto3.client("kms", **kwargs)
        self._key_id = key_id

    def store(self, ref: str, value: str) -> StoredSecret:
        response = self._client.generate_data_key(KeyId=self._key_id, KeySpec="AES_256")
        plaintext_key = response["Plaintext"]
        encrypted_data_key = base64.b64encode(response["CiphertextBlob"]).decode()
        nonce = os.urandom(12)
        ciphertext = AESGCM(plaintext_key).encrypt(nonce, value.encode(), None)
        payload = base64.b64encode(nonce + ciphertext).decode()
        return StoredSecret(
            value=payload,
            encrypted_data_key=encrypted_data_key,
            kms_key_id=self._key_id,
        )

    def retrieve(self, secret: Secret) -> str | None:
        if not secret.value or not secret.encrypted_data_key:
            return None
        response = self._client.decrypt(CiphertextBlob=base64.b64decode(secret.encrypted_data_key))
        plaintext_key = response["Plaintext"]
        payload = base64.b64decode(secret.value)
        nonce = payload[:12]
        ciphertext = payload[12:]
        plaintext = AESGCM(plaintext_key).decrypt(nonce, ciphertext, None)
        return plaintext.decode()

    def delete(self, secret: Secret) -> None:
        pass
