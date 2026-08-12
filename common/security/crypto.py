"""At-rest secret encryption and URI masking utilities (hubs.md §3.4)."""

import base64
import hashlib
import urllib.parse
from functools import lru_cache
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from common.config import settings


class SecretDecryptionError(RuntimeError):
    """Raised when decryption of an encrypted secret fails (e.g. invalid key or corrupted payload)."""

    pass


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """Build the Fernet instance from DATASTORE_ENCRYPTION_KEY, falling back to a
    key derived from JWT_SECRET_KEY when unset (non-production only).
    """
    raw_key = getattr(settings, "DATASTORE_ENCRYPTION_KEY", "") or ""
    if not raw_key:
        secret = getattr(settings, "JWT_SECRET_KEY", "default-secret") or "default-secret"
        raw_key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest()).decode("utf-8")

    try:
        key_bytes = raw_key.encode("utf-8")
        return Fernet(key_bytes)
    except Exception:
        derived = base64.urlsafe_b64encode(hashlib.sha256(raw_key.encode("utf-8")).digest())
        return Fernet(derived)


def encrypt_secret(plain_text: Optional[str]) -> Optional[str]:
    """Return the Fernet ciphertext string, or None when `plain_text` is None or empty."""
    if not plain_text:
        return None
    fernet = _get_fernet()
    return fernet.encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_secret(cipher_text: Optional[str]) -> Optional[str]:
    """Decrypt Fernet ciphertext; return None on None/empty input and raise SecretDecryptionError on InvalidToken."""
    if not cipher_text:
        return None
    fernet = _get_fernet()
    try:
        return fernet.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except (InvalidToken, Exception) as err:
        raise SecretDecryptionError("Failed to decrypt secret payload.") from err


def mask_connection_uri(uri: str) -> str:
    """Mask credentials and sensitive query parameter values in a connection URI.
    Returns literal '***' on parse failure (fail closed).
    """
    if not uri or not isinstance(uri, str):
        return "***"
    try:
        parts = urllib.parse.urlsplit(uri)
        if not parts.scheme and "://" not in uri and not uri.startswith("sqlite"):
            # Check if URI could be invalid
            pass
        netloc = parts.netloc
        if "@" in netloc:
            userinfo, hostport = netloc.rsplit("@", 1)
            if ":" in userinfo:
                username = userinfo.split(":", 1)[0]
                userinfo = f"{username}:***"
            else:
                userinfo = "***"
            netloc = f"{userinfo}@{hostport}"

        query = parts.query
        if query:
            params = urllib.parse.parse_qs(query, keep_blank_values=True)
            masked_params = []
            sensitive_keys = {"password", "api_key", "token", "secret"}
            for key, val_list in params.items():
                if key.lower() in sensitive_keys:
                    for _ in val_list:
                        masked_params.append((key, "***"))
                else:
                    for v in val_list:
                        masked_params.append((key, v))
            query = urllib.parse.urlencode(masked_params, safe="*")

        return urllib.parse.urlunsplit((parts.scheme, netloc, parts.path, query, parts.fragment))
    except Exception:
        return "***"


import json as _json


def encrypt_credential_payload(data: dict) -> str:
    """Serialize `data` to JSON then Fernet-encrypt it.

    Returns a non-None base64 ciphertext string. Raises ValueError if `data`
    is not JSON-serialisable.

    Usage::
        ct = encrypt_credential_payload({"password": "hunter2", "ssl_cert": "..."})
        row.encrypted_secret_payload = ct
    """
    plain_text = _json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    result = encrypt_secret(plain_text)
    if result is None:
        raise ValueError("encrypt_credential_payload: encrypt_secret returned None for non-empty payload")
    return result


def decrypt_credential_payload(cipher_text: str) -> dict:
    """Decrypt a Fernet ciphertext string and parse the JSON body.

    Returns the original dict. Raises SecretDecryptionError on bad key/token,
    and ValueError if the decrypted text is not valid JSON.

    Usage::
        payload = decrypt_credential_payload(row.encrypted_secret_payload)
        password = payload["password"]
    """
    plain_text = decrypt_secret(cipher_text)  # raises SecretDecryptionError on failure
    if plain_text is None:
        raise ValueError("decrypt_credential_payload: decrypted payload is None")
    try:
        return _json.loads(plain_text)
    except _json.JSONDecodeError as exc:
        raise ValueError(f"decrypt_credential_payload: decrypted text is not valid JSON: {exc}") from exc
