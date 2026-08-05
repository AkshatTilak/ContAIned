import logging
import secrets
from datetime import datetime, timedelta, timezone

from typing import Any, Dict

import jwt
from fastapi import HTTPException, status

try:
    from authlib.integrations.starlette_client import OAuth
    oauth = OAuth()
except ImportError:
    oauth = None

from common.config.settings import get_settings
from gateway.auth.utils import get_jwt_settings

logger = logging.getLogger("gateway.auth.providers")


def build_state(payload: Dict[str, Any]) -> str:
    """Build a signed, timestamped JWT state string for OAuth flows."""
    secret_key, algorithm, _ = get_jwt_settings()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    exp = now + timedelta(minutes=10)

    data = dict(payload)
    data.setdefault("nonce", secrets.token_urlsafe(16))
    data["iat"] = int(now.timestamp())
    data["exp"] = int(exp.timestamp())

    token = jwt.encode(data, secret_key, algorithm=algorithm)
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


def parse_state(state: str) -> Dict[str, Any]:
    """Parse and verify a signed OAuth state string.

    Raises HTTPException(400) if state is invalid, expired, or tampered.
    """
    if not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        )
    secret_key, algorithm, _ = get_jwt_settings()
    try:
        payload = jwt.decode(state, secret_key, algorithms=[algorithm])
        return payload
    except jwt.PyJWTError as e:
        logger.warning(f"OAuth state validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        )


def init_oauth():
    """Register Google and GitHub OAuth providers with Authlib."""
    if oauth is None:
        logger.warning("Authlib is not installed. OAuth providers disabled.")
        return
    settings = get_settings()

    google_client_id = getattr(settings, "GOOGLE_CLIENT_ID", None)
    google_client_secret = getattr(settings, "GOOGLE_CLIENT_SECRET", None)

    if google_client_id and google_client_secret:
        try:
            oauth.register(
                name="google",
                client_id=google_client_id,
                client_secret=google_client_secret,
                server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
                client_kwargs={
                    "scope": "openid email profile",
                },
            )
            logger.info("Google OAuth provider registered")
        except Exception as e:
            logger.warning(f"Failed to register Google OAuth provider: {e}")

    github_client_id = getattr(settings, "GITHUB_CLIENT_ID", None)
    github_client_secret = getattr(settings, "GITHUB_CLIENT_SECRET", None)

    if github_client_id and github_client_secret:
        try:
            oauth.register(
                name="github",
                client_id=github_client_id,
                client_secret=github_client_secret,
                authorize_url="https://github.com/login/oauth/authorize",
                access_token_url="https://github.com/login/oauth/access_token",
                api_base_url="https://api.github.com/",
                client_kwargs={"scope": "read:user user:email"},
            )
            logger.info("GitHub OAuth provider registered")
        except Exception as e:
            logger.warning(f"Failed to register GitHub OAuth provider: {e}")

