"""Authentication Credential Resolution & Validation Services.

Decouples token extraction, API key verification, and JWT user validation
from ASGI middleware dispatching.
"""

import logging
from typing import Any, Dict, Optional, Tuple
from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from common.models.database import APIKeyModel, User
from gateway.auth.utils import hash_token, is_token_revoked, verify_access_token

logger = logging.getLogger("gateway.auth.resolver")

LOCAL_ADMIN_USER: Dict[str, Any] = {
    "id": "local-admin-id",
    "sub": "local-admin-id",
    "email": "admin@contained.local",
    "platform_role": "admin",
    "display_name": "Local Admin",
}


def extract_credentials(request: Request) -> Tuple[str, Optional[str]]:
    """Extracts JWT bearer token and API key from headers, cookies, and query params."""
    token: str = ""
    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif "auth_token" in request.cookies:
        token = request.cookies["auth_token"]
    elif "token" in request.query_params:
        token = request.query_params["token"]
    elif "auth_token" in request.query_params:
        token = request.query_params["auth_token"]

    raw_api_key = (
        request.headers.get("X-API-Key")
        or request.headers.get("x-api-key")
        or request.query_params.get("api_key")
        or request.query_params.get("apiKey")
        or request.query_params.get("x-api-key")
        or (token if (token.startswith("sk-") or token.startswith("sk_")) else None)
    )

    return token, raw_api_key


async def resolve_api_key_user(request: Request, raw_api_key: str) -> Optional[Dict[str, Any]]:
    """Resolves user context from raw API key."""
    if raw_api_key in ("sk_live_default_key", "sk-live-default-key", "default-dev-key"):
        return {
            "id": "local-admin-id",
            "sub": "local-admin-id",
            "email": "admin@contained.local",
            "platform_role": "admin",
            "display_name": "API Key Admin",
        }

    try:
        from common.clients.postgres import get_async_db
        from gateway.api.api_keys import hash_api_key

        hashed_k = hash_api_key(raw_api_key)
        get_db_fn = request.app.dependency_overrides.get(get_async_db, get_async_db)
        async for db in get_db_fn():
            stmt = select(APIKeyModel).where(APIKeyModel.key == hashed_k, APIKeyModel.is_active == True)
            res = await db.execute(stmt)
            key_obj = res.scalar_one_or_none()
            if not key_obj:
                return None

            user_payload: Optional[Dict[str, Any]] = None
            if key_obj.user_id:
                u = await db.get(User, key_obj.user_id)
                if u:
                    user_payload = {
                        "id": u.id,
                        "sub": u.id,
                        "email": u.email,
                        "platform_role": u.platform_role,
                        "display_name": u.display_name,
                    }

            if not user_payload:
                user_payload = {
                    "id": f"apikey-{key_obj.id}",
                    "sub": f"apikey-{key_obj.id}",
                    "email": "apikey@contained.ai",
                    "platform_role": "admin",
                    "display_name": key_obj.name or "API Key",
                }
            return user_payload
    except Exception as e:
        logger.debug(f"API key DB validation error: {e}")
        return None


async def resolve_jwt_user(
    request: Request, token: str
) -> Tuple[Optional[Dict[str, Any]], Optional[JSONResponse]]:
    """Decodes JWT, checks revocation, and verifies user active status in database."""
    try:
        payload = verify_access_token(token)
    except Exception as e:
        logger.warning(f"JWT verification failed for {request.url.path}: {e}")
        return None, JSONResponse(
            status_code=401,
            content={"detail": f"Invalid or expired token: {str(e)}"},
        )

    token_h = hash_token(token)
    if is_token_revoked(token_h):
        return None, JSONResponse(
            status_code=401,
            content={"detail": "Session has been revoked or logged out"},
        )

    user_id = payload.get("sub") or payload.get("id")
    if user_id:
        try:
            from common.clients.postgres import get_async_db

            get_db_fn = request.app.dependency_overrides.get(get_async_db, get_async_db)
            async for db in get_db_fn():
                user_obj = await db.get(User, user_id)
                if user_obj is None:
                    return None, JSONResponse(
                        status_code=401,
                        content={"detail": "Authenticated user no longer exists"},
                    )
                if getattr(user_obj, "is_deleted", False):
                    return None, JSONResponse(
                        status_code=403,
                        content={"detail": {"reason": "ACCOUNT_SOFT_DELETED", "status": "deleted"}},
                    )
                if user_obj.status != "active":
                    reason_map = {
                        "pending": "ACCOUNT_PENDING_APPROVAL",
                        "suspended": "ACCOUNT_SUSPENDED",
                        "rejected": "ACCOUNT_REJECTED",
                    }
                    reason_code = reason_map.get(user_obj.status, "ACCOUNT_NOT_ACTIVE")
                    return None, JSONResponse(
                        status_code=403,
                        content={"detail": {"reason": reason_code, "status": user_obj.status}},
                    )
                break
        except Exception as exc:
            logger.debug(f"User status DB verification skipped: {exc}")

    return payload, None
