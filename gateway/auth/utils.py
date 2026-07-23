"""JWT utility functions for token creation, verification, and session hashing."""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from common.config.settings import get_settings


def get_jwt_settings():
    settings = get_settings()
    return (
        getattr(settings, "JWT_SECRET_KEY", "contained-secret-key-change-in-production"),
        getattr(settings, "JWT_ALGORITHM", "HS256"),
        getattr(settings, "JWT_EXPIRY_HOURS", 24),
    )


def hash_token(token: str) -> str:
    """Hash a JWT token using SHA-256 for secure DB storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(
    user_id: str,
    email: str,
    role: str,
    expires_hours: Optional[int] = None,
) -> str:
    """Generate a signed JWT access token."""
    secret_key, algorithm, default_expiry = get_jwt_settings()
    expiry_hours = expires_hours if expires_hours is not None else default_expiry

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=expiry_hours)

    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }

    token = jwt.encode(payload, secret_key, algorithm=algorithm)
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


def verify_access_token(token: str) -> Dict[str, Any]:
    """Decode and verify a JWT access token.

    Raises jwt.PyJWTError if token is invalid or expired.
    """
    secret_key, algorithm, _ = get_jwt_settings()
    payload = jwt.decode(token, secret_key, algorithms=[algorithm])
    return payload
