"""OAuth2 providers registry (Google & GitHub) using Authlib."""

import logging
from authlib.integrations.starlette_client import OAuth
from common.config.settings import get_settings

logger = logging.getLogger("gateway.auth.providers")

oauth = OAuth()


def init_oauth():
    """Register Google and GitHub OAuth providers with Authlib."""
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
                client_kwargs={"scope": "openid email profile"},
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
