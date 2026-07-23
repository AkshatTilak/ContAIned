"""FastAPI dependencies for user context and Role-Based Access Control (RBAC)."""

import logging
from typing import Any, Callable, Dict, Optional, Sequence

from common.config.settings import get_settings
from common.clients.postgres import get_async_db
from fastapi import HTTPException, Request, status

get_db = get_async_db

logger = logging.getLogger("gateway.auth.dependencies")

# Role Hierarchy: admin > editor > viewer
ROLE_HIERARCHY = {
    "admin": 3,
    "editor": 2,
    "viewer": 1,
}


async def get_current_user(request: Request) -> Dict[str, Any]:
    """Retrieve authenticated user from request state."""
    settings = get_settings()

    # Fallback for when AUTH_ENABLED is False
    if not getattr(settings, "AUTH_ENABLED", False):
        return {
            "id": "local-admin-id",
            "sub": "local-admin-id",
            "email": "admin@contained.local",
            "role": "admin",
            "display_name": "Local Admin",
        }

    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
        )
    return user


async def get_optional_user(request: Request) -> Optional[Dict[str, Any]]:
    """Retrieve optional user from request state (returns None if unauthenticated)."""
    settings = get_settings()
    if not getattr(settings, "AUTH_ENABLED", False):
        return {
            "id": "local-admin-id",
            "sub": "local-admin-id",
            "email": "admin@contained.local",
            "role": "admin",
        }

    return getattr(request.state, "user", None)


def require_role(*allowed_roles: str) -> Callable:
    """Dependency factory requiring the authenticated user to possess one of the allowed roles.

    Supports role hierarchy where higher roles inherit permissions of lower roles.
    Usage: Depends(require_role("admin", "editor"))
    """

    async def role_checker(request: Request) -> Dict[str, Any]:
        user = await get_current_user(request)
        user_role = user.get("role", "viewer")

        if "admin" in allowed_roles and user_role == "admin":
            return user

        if user_role in allowed_roles:
            return user

        # Check hierarchy: if required is viewer/editor and user is admin, allow
        user_level = ROLE_HIERARCHY.get(user_role, 0)
        min_required_level = min(
            [ROLE_HIERARCHY.get(r, 99) for r in allowed_roles], default=99
        )

        if user_level >= min_required_level:
            return user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions. Role '{user_role}' is not authorized.",
        )

    return role_checker
