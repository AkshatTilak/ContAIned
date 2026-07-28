"""HubContext dependency and require_hub factory for route authorization (hubs.md §5.2).

Failure Semantics Table (Security Control - Anti-Enumeration):
+------------------------------------+--------+------------------------+
| Condition                          | Status | detail                 |
+------------------------------------+--------+------------------------+
| Hub does not exist                 | 404    | Hub not found          |
| Caller not member & not admin      | 404    | Hub not found          |
| Hub type mismatch                  | 404    | Hub not found          |
| Member role < min_role             | 403    | Insufficient hub role  |
| Hub archived on mutating method    | 409    | Hub is archived        |
+------------------------------------+--------+------------------------+
"""

import logging
from dataclasses import dataclass
from typing import Annotated, Any, Awaitable, Callable, Dict, Optional, Set

from common.clients.postgres import get_async_db
from common.constants.roles import (
    HUB_ROLES,
    HUB_ROLE_OWNER,
    HUB_ROLE_VIEWER,
    HUB_TYPES,
    hub_role_satisfies,
    is_platform_admin,
)
from common.models.database import Hub
from common.services.hub_repository import get_hub, get_membership
from fastapi import Depends, HTTPException, Path, Request, status
from gateway.auth.dependencies import get_current_user
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("gateway.auth.hub_context")

MUTATING_METHODS: Set[str] = frozenset({"POST", "PUT", "PATCH", "DELETE"})


@dataclass(frozen=True)
class HubContext:
    """Frozen context object representing resolved hub tenancy for a request."""

    hub: Hub
    user: Dict[str, Any]
    hub_role: str
    is_platform_admin: bool

    @property
    def hub_id(self) -> str:
        return self.hub.id

    @property
    def user_id(self) -> str:
        return self.user.get("sub") or self.user.get("id", "")

    def require(self, min_role: str) -> None:
        """Secondary in-handler check for endpoints with per-verb role requirements."""
        if not hub_role_satisfies(self.hub_role, min_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient hub role",
            )


def require_hub(
    *,
    hub_type: Optional[str] = None,
    min_role: str = HUB_ROLE_VIEWER,
    allow_archived: bool = False,
) -> Callable[..., Awaitable[HubContext]]:
    """Resolves {hub_id} from path, asserts hub exists, is not archived, matches `hub_type`,
    and caller's effective role >= `min_role`.
    """
    if hub_type is not None and hub_type not in HUB_TYPES:
        raise ValueError(f"Unknown hub_type: '{hub_type}'. Valid: {HUB_TYPES}")
    if min_role not in HUB_ROLES:
        raise ValueError(f"Unknown min_role: '{min_role}'. Valid: {HUB_ROLES}")

    async def dependency(
        request: Request,
        hub_id: str = Path(...),
        session: AsyncSession = Depends(get_async_db),
    ) -> HubContext:
        user = await get_current_user(request)

        # Per-request resolution caching
        cache = getattr(request.state, "_hub_resolved_cache", None)
        if cache is None:
            cache = {}
            request.state._hub_resolved_cache = cache

        if hub_id in cache:
            hub, membership = cache[hub_id]
        else:
            hub = await get_hub(session, hub_id)
            if hub is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Hub not found",
                )
            user_id = user.get("sub") or user.get("id", "")
            membership = await get_membership(session, hub_id=hub_id, user_id=user_id)
            cache[hub_id] = (hub, membership)

        if hub is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hub not found",
            )

        is_admin = is_platform_admin(user)

        # Non-members receive 404 (never 403) to prevent hub ID enumeration
        if not is_admin and membership is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hub not found",
            )

        effective_role = HUB_ROLE_OWNER if is_admin else membership.hub_role

        # Type mismatch returns 404
        if hub_type is not None and hub.hub_type != hub_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hub not found",
            )

        # Archival check on mutating methods
        if hub.is_archived and request.method in MUTATING_METHODS and not allow_archived:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Hub is archived",
            )

        # Role requirement check
        if not hub_role_satisfies(effective_role, min_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient hub role",
            )

        return HubContext(
            hub=hub,
            user=user,
            hub_role=effective_role,
            is_platform_admin=is_admin,
        )

    return dependency


def RequireIngestionHub(min_role: str = HUB_ROLE_VIEWER) -> Any:
    return Depends(require_hub(hub_type="ingestion", min_role=min_role))


def RequireAgentHub(min_role: str = HUB_ROLE_VIEWER) -> Any:
    return Depends(require_hub(hub_type="agent", min_role=min_role))


def RequireWorkflowHub(min_role: str = HUB_ROLE_VIEWER) -> Any:
    return Depends(require_hub(hub_type="workflow", min_role=min_role))


def RequireEvalHub(min_role: str = HUB_ROLE_VIEWER) -> Any:
    return Depends(require_hub(hub_type="eval", min_role=min_role))


def RequireHub(min_role: str = HUB_ROLE_VIEWER) -> Any:
    return Depends(require_hub(min_role=min_role))


HubCtx = Annotated[HubContext, Depends(require_hub())]
