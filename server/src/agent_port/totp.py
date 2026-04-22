"""TOTP (authenticator app) primitives.

Secrets and recovery codes live on the User row. Re-enabling a previously
configured account does not generate a new secret — the stored one is reused.
"""

import base64
import hashlib
import hmac
import io
import json
import secrets

import pyotp
import qrcode

from agent_port.models.user import User

ISSUER = "AgentPort"
RECOVERY_CODE_COUNT = 10


def generate_secret() -> str:
    """Return a fresh base32 TOTP secret."""
    return pyotp.random_base32()


def generate_recovery_codes() -> list[str]:
    """Return a list of human-friendly one-time recovery codes (plaintext)."""
    # Two 5-char groups, lowercase hex, joined by a dash. ~40 bits of entropy.
    return [
        f"{secrets.token_hex(3)[:5]}-{secrets.token_hex(3)[:5]}" for _ in range(RECOVERY_CODE_COUNT)
    ]


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def hash_recovery_codes(codes: list[str]) -> str:
    """Hash each recovery code with SHA-256 and serialise to JSON.

    Recovery codes are server-generated high-entropy random tokens, so a slow
    KDF (bcrypt) buys nothing and costs ~2s of setup latency. A single SHA-256
    is the standard choice for random token storage."""
    return json.dumps([_hash_code(c) for c in codes])


def otpauth_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER)


def qr_data_url(uri: str) -> str:
    """Render the otpauth URI as a PNG data URL."""
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def _normalise_code(code: str) -> str:
    return code.replace(" ", "").replace("-", "").strip()


def verify_totp_code(secret: str, code: str) -> bool:
    """Validate a 6-digit TOTP code. Accepts a +/-1 window for clock drift."""
    normalised = _normalise_code(code)
    if not normalised.isdigit() or len(normalised) != 6:
        return False
    return pyotp.TOTP(secret).verify(normalised, valid_window=1)


def consume_recovery_code(user: User, code: str) -> bool:
    """If ``code`` matches one of the user's unused recovery codes, burn it and
    return True. Persists the updated list back onto the user object (caller
    must commit the session)."""
    if not user.totp_recovery_codes_hash_json:
        return False
    normalised = code.strip().lower().replace(" ", "")
    try:
        hashes: list[str] = json.loads(user.totp_recovery_codes_hash_json)
    except json.JSONDecodeError:
        return False
    candidate = _hash_code(normalised)
    for idx, h in enumerate(hashes):
        if hmac.compare_digest(candidate, h):
            hashes.pop(idx)
            user.totp_recovery_codes_hash_json = json.dumps(hashes)
            return True
    return False


def verify_second_factor(user: User, code: str | None) -> bool:
    """Verify either a TOTP code or a recovery code. Mutates ``user`` to burn
    the recovery code on success (caller commits)."""
    if not code:
        return False
    stripped = code.strip()
    # TOTP codes are all digits (optionally with spaces). Anything else is a
    # recovery code attempt.
    if _normalise_code(stripped).isdigit() and user.totp_secret:
        if verify_totp_code(user.totp_secret, stripped):
            return True
    return consume_recovery_code(user, stripped)
