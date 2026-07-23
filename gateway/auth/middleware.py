"""Authentication ASGI middleware for JWT validation."""

import logging
from typing import List

from common.config.settings import get_settings
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from gateway.auth.utils import hash_token, verify_access_token
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger("gateway.auth.middleware")

# Endpoints exempt from JWT validation
WHITELIST_PREFIXES: List[str] = [
    "/auth/login",
    "/auth/callback",
    "/health",
    "/api/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/favicon.ico",
    "/static",
    "/v1",  # External API routes use API key authentication (S5-07)
]


class AuthMiddleware(BaseHTTPMiddleware):
    """ASGI Middleware to validate JWT tokens on incoming requests."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        settings = get_settings()

        # If authentication is disabled globally, skip middleware processing
        if not getattr(settings, "AUTH_ENABLED", False):
            request.state.user = {
                "sub": "local-admin-id",
                "email": "admin@contained.local",
                "role": "admin",
            }
            return await call_next(request)

        path = request.url.path

        # Skip exempt endpoints
        for prefix in WHITELIST_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Extract token from Authorization header or cookie
        token: str = ""
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif "auth_token" in request.cookies:
            token = request.cookies["auth_token"]

        if not token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing authentication credentials"},
            )

        try:
            payload = verify_access_token(token)
            request.state.user = payload
            request.state.token = token
        except Exception as e:
            logger.warning(f"JWT validation failed for {path}: {e}")
            return JSONResponse(
                status_code=401,
                content={"detail": f"Invalid or expired token: {str(e)}"},
            )

        return await call_next(request)
