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
    platform_role: str = "member",
    expires_hours: Optional[int] = None,
    **kwargs: Any,
) -> str:
    """Generate a signed JWT access token."""
    secret_key, algorithm, default_expiry = get_jwt_settings()
    expiry_hours = expires_hours if expires_hours is not None else default_expiry

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=expiry_hours)

    role_val = kwargs.get("role") or platform_role

    payload = {
        "sub": user_id,
        "email": email,
        "platform_role": role_val,
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


def normalize_email(email: str) -> str:
    """Normalize email address by trimming whitespace and lowercasing."""
    if not email:
        return ""
    return email.strip().lower()


def client_ip(request: Any) -> Optional[str]:
    """Extract client IP address from X-Forwarded-For (first hop if TRUST_PROXY_HEADERS enabled) or request.client.host."""
    import ipaddress
    settings = get_settings()
    ip_str: Optional[str] = None

    if getattr(settings, "TRUST_PROXY_HEADERS", False) and request.headers:
        x_forwarded_for = request.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            ip_str = x_forwarded_for.split(",")[0].strip()

    if not ip_str and hasattr(request, "client") and request.client:
        ip_str = request.client.host

    if ip_str:
        try:
            ipaddress.ip_address(ip_str)
            return ip_str[:45]
        except ValueError:
            return None
    return None


async def revoke_sessions(
    db: Any,
    user_id: str,
    *,
    keep_token_hash: Optional[str] = None,
) -> int:
    """Revoke user session records in DB. Returns count of deleted sessions."""
    from sqlalchemy import delete
    from common.models.database import UserSession

    stmt = delete(UserSession).where(UserSession.user_id == user_id)
    if keep_token_hash:
        stmt = stmt.where(UserSession.token_hash != keep_token_hash)

    res = await db.execute(stmt)
    return res.rowcount if hasattr(res, "rowcount") else 0

