"""Cross-Hub Resolver & Link Enforcement Service (hubs.md §5.4).

Provides execution-time cross-hub resource resolution, non-transitivity enforcement,
and dual-hub authorization validation for hub links.
"""

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from common.constants.roles import (
    HUB_ROLE_CONTRIBUTOR,
    HUB_ROLE_MAINTAINER,
    hub_role_satisfies,
    is_link_direction_allowed,
    link_access_satisfies,
)
from common.models.database import (
    AgentDefinition,
    DatastoreBinding,
    EvalTestSuite,
    ExternalCredential,
    HubLink,
    WorkflowDefinition,
)
from common.services.hub_repository import get_hub, get_link, get_membership
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("common.services.hub_resolver")

RESOURCE_TYPE_MODELS: Dict[str, Any] = {
    "collection": DatastoreBinding,
    "agent": AgentDefinition,
    "workflow": WorkflowDefinition,
    "eval_suite": EvalTestSuite,
    "credential": ExternalCredential,
}

RESOURCE_TYPE_HUB_TYPE: Dict[str, str] = {
    "collection": "ingestion",
    "agent": "agent",
    "workflow": "workflow",
    "eval_suite": "eval",
    "credential": "workflow",
}

HUB_LINK_REQUIRED = "HUB_LINK_REQUIRED"
HUB_LINK_REVOKED = "HUB_LINK_REVOKED"
HUB_LINK_INSUFFICIENT = "HUB_LINK_INSUFFICIENT"


class HubLinkError(Exception):
    """Exception raised when cross-hub link resolution or authorization fails."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        source_hub_id: str,
        target_hub_id: Optional[str] = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.source_hub_id = source_hub_id
        self.target_hub_id = target_hub_id


async def resolve_linked(
    session: AsyncSession,
    source_hub_id: str,
    target_resource_type: str,
    target_resource_id: str,
    *,
    required_access: str = "read",
    link_cache: Optional[Dict[Tuple[str, str], Optional[HubLink]]] = None,
) -> Any:
    """Load the target resource, then assert a hub_link exists from source_hub_id to target's hub_id
    with sufficient access_level. Raises HubLinkError (403 on wire) otherwise.
    Strictly non-transitive (single-hop only).
    """
    model_cls = RESOURCE_TYPE_MODELS.get(target_resource_type)
    if model_cls is None:
        raise ValueError(f"Unknown target_resource_type: '{target_resource_type}'. Valid: {list(RESOURCE_TYPE_MODELS.keys())}")

    # hub-resolver: allowlisted unscoped read by primary key
    stmt = select(model_cls).where(model_cls.id == target_resource_id)
    res = await session.execute(stmt)
    row = res.scalar_one_or_none()

    if row is None:
        raise HubLinkError(
            HUB_LINK_REQUIRED,
            f"Resource '{target_resource_id}' not found or inaccessible",
            source_hub_id=source_hub_id,
        )

    target_hub_id = getattr(row, "hub_id", None)
    if not target_hub_id:
        raise HubLinkError(
            HUB_LINK_REQUIRED,
            f"Resource '{target_resource_id}' has no associated hub",
            source_hub_id=source_hub_id,
        )

    # Same-hub fast path
    if target_hub_id == source_hub_id:
        return row

    source_hub = await get_hub(session, source_hub_id)
    target_hub = await get_hub(session, target_hub_id)

    if source_hub is None or target_hub is None:
        raise HubLinkError(
            HUB_LINK_REQUIRED,
            "Hub not found",
            source_hub_id=source_hub_id,
            target_hub_id=target_hub_id,
        )

    # Validate allowed direction matrix
    if not is_link_direction_allowed(source_hub.hub_type, target_hub.hub_type):
        raise HubLinkError(
            HUB_LINK_REQUIRED,
            f"Link direction from '{source_hub.hub_type}' to '{target_hub.hub_type}' is not permitted",
            source_hub_id=source_hub_id,
            target_hub_id=target_hub_id,
        )

    # Per-request / per-run link caching
    cache_key = (source_hub_id, target_hub_id)
    if link_cache is not None and cache_key in link_cache:
        link = link_cache[cache_key]
    else:
        link = await get_link(session, source_hub_id=source_hub_id, target_hub_id=target_hub_id)
        if link_cache is not None:
            link_cache[cache_key] = link

    if link is None:
        raise HubLinkError(
            HUB_LINK_REVOKED,
            f"Required link from hub '{source_hub_id}' to hub '{target_hub_id}' was revoked or missing",
            source_hub_id=source_hub_id,
            target_hub_id=target_hub_id,
        )

    if not link_access_satisfies(link.access_level, required_access):
        raise HubLinkError(
            HUB_LINK_INSUFFICIENT,
            f"Link access level '{link.access_level}' does not satisfy required '{required_access}'",
            source_hub_id=source_hub_id,
            target_hub_id=target_hub_id,
        )

    return row


async def resolve_linked_many(
    session: AsyncSession,
    source_hub_id: str,
    target_resource_type: str,
    target_resource_ids: Sequence[str],
    *,
    required_access: str = "read",
    link_cache: Optional[Dict[Tuple[str, str], Optional[HubLink]]] = None,
) -> Dict[str, Any]:
    """Batch resolve multiple resources of the same type linked to source_hub_id."""
    results: Dict[str, Any] = {}
    for res_id in target_resource_ids:
        row = await resolve_linked(
            session,
            source_hub_id,
            target_resource_type,
            res_id,
            required_access=required_access,
            link_cache=link_cache,
        )
        results[res_id] = row
    return results


async def assert_link(
    session: AsyncSession,
    *,
    source_hub_id: str,
    target_hub_id: str,
    required_access: str = "read",
) -> HubLink:
    """Assert that a valid link exists from source_hub_id to target_hub_id with required_access."""
    if source_hub_id == target_hub_id:
        raise ValueError("Self-link assertion is invalid")

    source_hub = await get_hub(session, source_hub_id)
    target_hub = await get_hub(session, target_hub_id)

    if source_hub is None or target_hub is None:
        raise HubLinkError(
            HUB_LINK_REQUIRED,
            "Hub not found",
            source_hub_id=source_hub_id,
            target_hub_id=target_hub_id,
        )

    if not is_link_direction_allowed(source_hub.hub_type, target_hub.hub_type):
        raise HubLinkError(
            HUB_LINK_REQUIRED,
            f"Link direction from '{source_hub.hub_type}' to '{target_hub.hub_type}' is not permitted",
            source_hub_id=source_hub_id,
            target_hub_id=target_hub_id,
        )

    link = await get_link(session, source_hub_id=source_hub_id, target_hub_id=target_hub_id)
    if link is None:
        raise HubLinkError(
            HUB_LINK_REVOKED,
            f"Required link from hub '{source_hub_id}' to hub '{target_hub_id}' was revoked or missing",
            source_hub_id=source_hub_id,
            target_hub_id=target_hub_id,
        )

    if not link_access_satisfies(link.access_level, required_access):
        raise HubLinkError(
            HUB_LINK_INSUFFICIENT,
            f"Link access level '{link.access_level}' does not satisfy required '{required_access}'",
            source_hub_id=source_hub_id,
            target_hub_id=target_hub_id,
        )

    return link


async def list_linked_hub_ids(
    session: AsyncSession,
    *,
    source_hub_id: str,
    target_hub_type: str,
    required_access: str = "read",
) -> List[str]:
    """Returns target hub IDs linked from source_hub_id matching target_hub_type and required_access."""
    from common.models.database import Hub
    stmt = (
        select(HubLink.target_hub_id)
        .join(Hub, HubLink.target_hub_id == Hub.id)
        .where(
            HubLink.source_hub_id == source_hub_id,
            Hub.hub_type == target_hub_type,
        )
    )
    res = await session.execute(stmt)
    links = (await session.execute(
        select(HubLink).where(HubLink.source_hub_id == source_hub_id)
    )).scalars().all()

    valid_target_ids: List[str] = []
    for l in links:
        t_hub = await get_hub(session, l.target_hub_id)
        if t_hub and t_hub.hub_type == target_hub_type and link_access_satisfies(l.access_level, required_access):
            valid_target_ids.append(l.target_hub_id)
    return valid_target_ids


async def validate_link_creation(
    session: AsyncSession,
    *,
    source_hub_id: str,
    target_hub_id: str,
    access_level: str,
    actor_user_id: str,
    is_platform_admin: bool,
) -> None:
    """Validate link creation: self-linking (422), direction validity (422), dual-hub authorization (43/403)."""
    if source_hub_id == target_hub_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Self-linking is not allowed (source_hub_id == target_hub_id)",
        )

    source_hub = await get_hub(session, source_hub_id)
    target_hub = await get_hub(session, target_hub_id)

    if source_hub is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source hub '{source_hub_id}' not found",
        )
    if target_hub is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target hub '{target_hub_id}' not found",
        )

    if not is_link_direction_allowed(source_hub.hub_type, target_hub.hub_type):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Link direction from '{source_hub.hub_type}' to '{target_hub.hub_type}' is not permitted",
        )

    if not is_platform_admin:
        source_mem = await get_membership(session, hub_id=source_hub_id, user_id=actor_user_id)
        target_mem = await get_membership(session, hub_id=target_hub_id, user_id=actor_user_id)

        if not source_mem or not hub_role_satisfies(source_mem.hub_role, HUB_ROLE_MAINTAINER):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Dual-hub authorization required: actor must be maintainer or owner on source hub",
            )

        if not target_mem or not hub_role_satisfies(target_mem.hub_role, HUB_ROLE_CONTRIBUTOR):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Dual-hub authorization required: actor must be contributor or higher on target hub",
            )
