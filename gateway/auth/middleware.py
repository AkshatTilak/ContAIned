"""Authentication ASGI middleware for JWT and API Key request validation."""

import logging
from typing import List

from common.config.settings import get_settings
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from gateway.auth.resolver import (
    LOCAL_ADMIN_USER,
    extract_credentials,
    resolve_api_key_user,
    resolve_jwt_user,
)

logger = logging.getLogger("gateway.auth.middleware")

# Endpoints exempt from mandatory authentication
WHITELIST_PREFIXES: List[str] = [
    "/auth/login",
    "/auth/register",
    "/auth/forgot-password",
    "/auth/reset-password",
    "/auth/invite",
    "/auth/callback",
    "/health",
    "/api/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/favicon.ico",
    "/static",
    "/v1",            # External API routes handled by APIKeyMiddleware (S5-07)
    "/qdrant",        # Infrastructure proxy iframe route (direct mount)
    "/neo4j",         # Infrastructure proxy iframe route (direct mount)
    "/api/qdrant",    # Infrastructure proxy iframe route (legacy)
    "/api/neo4j",     # Infrastructure proxy iframe route (legacy)
    "/dashboard",     # Qdrant dashboard static assets route
    "/collections",   # Qdrant dashboard collections API proxy route
    "/telemetry",     # Qdrant dashboard telemetry API proxy route
    "/api/telemetry", # Telemetry WebSocket and SSE streaming route
    "/cluster",       # Qdrant dashboard cluster API proxy route
    "/aliases",       # Qdrant dashboard aliases API proxy route
]


class AuthMiddleware(BaseHTTPMiddleware):
    """ASGI Middleware to validate JWT tokens and API keys on incoming requests."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        settings = get_settings()

        # If authentication is disabled globally, inject local admin user
        if not getattr(settings, "AUTH_ENABLED", False):
            request.state.user = LOCAL_ADMIN_USER
            return await call_next(request)

        # Bypass OPTIONS requests (CORS preflights)
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        is_exempt = any(path.startswith(prefix) for prefix in WHITELIST_PREFIXES)

        token, raw_api_key = extract_credentials(request)

        # 1. API Key Authentication (Headers: X-API-Key or Bearer: sk-...)
        if raw_api_key:
            if path.startswith("/v1"):
                return await call_next(request)

            api_user = await resolve_api_key_user(request, raw_api_key)
            if api_user:
                request.state.user = api_user
                request.state.api_key = raw_api_key
                return await call_next(request)
            elif is_exempt:
                return await call_next(request)

            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or inactive API key"},
            )

        # 2. JWT Token Authentication
        if token:
            jwt_user, error_response = await resolve_jwt_user(request, token)
            if error_response and not is_exempt:
                return error_response
            if jwt_user:
                request.state.user = jwt_user
                request.state.token = token
            return await call_next(request)

        # 3. No Credentials Provided
        if is_exempt:
            return await call_next(request)

        return JSONResponse(
            status_code=401,
            content={"detail": "Missing authentication credentials"},
        )
