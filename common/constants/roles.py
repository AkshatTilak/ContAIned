"""Canonical platform role and hub role constants and helpers (hubs.md §4.1)."""

from typing import Final, Optional, Any
from common.models.hub_enums import (
    HUB_TYPE_INGESTION,
    HUB_TYPE_AGENT,
    HUB_TYPE_WORKFLOW,
    HUB_TYPE_EVAL,
    HUB_TYPES,
    HUB_ROLE_OWNER,
    HUB_ROLE_MAINTAINER,
    HUB_ROLE_CONTRIBUTOR,
    HUB_ROLE_VIEWER,
    HUB_ROLES,
    HUB_ROLE_ORDER,
    LINK_ACCESS_ORDER,
    LINK_ACCESS_READ,
    LINK_ACCESS_USE,
    hub_role_rank,
    hub_role_satisfies,
    link_access_satisfies,
    is_link_direction_allowed,
)

PLATFORM_ROLE_ADMIN: Final = "admin"
PLATFORM_ROLE_MEMBER: Final = "member"
PLATFORM_ROLES: Final[tuple[str, ...]] = (PLATFORM_ROLE_ADMIN, PLATFORM_ROLE_MEMBER)

V5_TO_V6_PLATFORM_ROLE: Final[dict[str, str]] = {
    "admin": PLATFORM_ROLE_ADMIN,
    "editor": PLATFORM_ROLE_MEMBER,
    "viewer": PLATFORM_ROLE_MEMBER,
}


def is_platform_admin(user: Optional[dict[str, Any]]) -> bool:
    """Return True if user has the platform admin role."""
    if not user:
        return False
    role = user.get("platform_role") or user.get("role")
    return role == PLATFORM_ROLE_ADMIN

