"""
ParamX Hunter - Security Utilities
Encryption at rest for sensitive fields (auth configs, cookies, tokens)
and secrets management helpers.
"""

import base64
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from backend.config import settings

# ── Encryption at Rest ──────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """
    Derive a Fernet key from SECRET_KEY.
    In production, use a dedicated KMS-managed key (AWS KMS, GCP KMS, Vault).
    """
    key_material = settings.SECRET_KEY.encode()
    # Fernet requires 32 url-safe base64-encoded bytes
    padded = key_material.ljust(32, b"0")[:32]
    fernet_key = base64.urlsafe_b64encode(padded)
    return Fernet(fernet_key)


def encrypt_value(value: str) -> str:
    """Encrypt a string value for storage (e.g., target auth tokens)."""
    if not value:
        return value
    f = _get_fernet()
    return f.encrypt(value.encode()).decode()


def decrypt_value(token: str) -> str:
    """Decrypt a previously encrypted string."""
    if not token:
        return token
    f = _get_fernet()
    try:
        return f.decrypt(token.encode()).decode()
    except InvalidToken:
        # Value was not encrypted (legacy/plaintext) — return as-is
        return token


def encrypt_dict_values(data: dict, sensitive_keys: set[str] | None = None) -> dict:
    """
    Encrypt values of sensitive keys within a dict (e.g., auth_config).
    Keys matching SENSITIVE_KEY_PATTERNS are encrypted automatically.
    """
    sensitive_keys = sensitive_keys or SENSITIVE_KEY_PATTERNS
    result = {}
    for k, v in data.items():
        if isinstance(v, str) and any(s in k.lower() for s in sensitive_keys):
            result[k] = {"__encrypted__": True, "value": encrypt_value(v)}
        else:
            result[k] = v
    return result


def decrypt_dict_values(data: dict) -> dict:
    result = {}
    for k, v in data.items():
        if isinstance(v, dict) and v.get("__encrypted__"):
            result[k] = decrypt_value(v["value"])
        else:
            result[k] = v
    return result


SENSITIVE_KEY_PATTERNS = {
    "password",
    "secret",
    "token",
    "key",
    "credential",
    "auth",
    "session",
}


def mask_sensitive_value(name: str, value: str | None) -> str | None:
    """Mask a sensitive value for display (e.g., in API responses)."""
    if value is None:
        return None
    if any(p in name.lower() for p in SENSITIVE_KEY_PATTERNS):
        if len(value) <= 8:
            return "***"
        return f"{value[:4]}...{value[-4:]}"
    return value


# ── Secrets Generation ─────────────────────────────────────────────────────────


def generate_secret_key(length: int = 32) -> str:
    """Generate a cryptographically secure random secret key."""
    import secrets

    return secrets.token_urlsafe(length)


def generate_api_key(prefix: str = "px") -> str:
    """Generate a ParamX Hunter API key (for programmatic access)."""
    import secrets

    return f"{prefix}_{secrets.token_hex(24)}"
