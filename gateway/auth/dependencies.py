"""FastAPI dependencies for user context and Platform Role-Based Access Control (RBAC)."""

import logging
from typing import Any, Callable, Dict, Optional

from common.config.settings import get_settings
from common.clients.postgres import get_async_db
from common.constants.roles import (
    PLATFORM_ROLES,
    PLATFORM_ROLE_ADMIN,
    PLATFORM_ROLE_MEMBER,
)
from fastapi import HTTPException, Request, status

get_db = get_async_db

logger = logging.getLogger("gateway.auth.dependencies")


async def get_current_user(request: Request) -> Dict[str, Any]:
    """Retrieve authenticated user from request state."""
    user = getattr(request.state, "user", None)
    if user:
        return user

    settings = get_settings()

    # Fallback for when AUTH_ENABLED is False
    if not getattr(settings, "AUTH_ENABLED", False):
        return {
            "id": "local-admin-id",
            "sub": "local-admin-id",
            "email": "admin@contained.local",
            "platform_role": PLATFORM_ROLE_ADMIN,
            "display_name": "Local Admin",
        }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication credentials were not provided",
    )


async def get_optional_user(request: Request) -> Optional[Dict[str, Any]]:
    """Retrieve optional user from request state (returns None if unauthenticated)."""
    user = getattr(request.state, "user", None)
    if user:
        return user

    settings = get_settings()
    if not getattr(settings, "AUTH_ENABLED", False):
        return {
            "id": "local-admin-id",
            "sub": "local-admin-id",
            "email": "admin@contained.local",
            "platform_role": PLATFORM_ROLE_ADMIN,
        }

    return None


def require_role(*allowed_roles: str) -> Callable:
    """Platform-level RBAC only. Hub-scoped routes MUST use require_hub() (hubs.md §5.2)."""
    unknown = set(allowed_roles) - set(PLATFORM_ROLES)
    if unknown:
        raise ValueError(f"Unknown platform role(s): {sorted(unknown)}. Valid: {PLATFORM_ROLES}")

    async def role_checker(request: Request) -> Dict[str, Any]:
        user = await get_current_user(request)
        role = user.get("platform_role", user.get("role", PLATFORM_ROLE_MEMBER))

        if role == PLATFORM_ROLE_ADMIN or role in allowed_roles:
            return user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient platform permissions. Role '{role}' is not authorized.",
        )

    return role_checker


require_platform_role = require_role
require_platform_admin = require_role(PLATFORM_ROLE_ADMIN)

