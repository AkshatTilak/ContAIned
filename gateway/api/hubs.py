"""Hub, Membership, and Link Management REST API Routes (hubs.md §5.1)."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from common.clients.postgres import get_async_db
from common.config.settings import get_settings
from common.constants.roles import (
    HUB_ROLE_CONTRIBUTOR,
    HUB_ROLE_MAINTAINER,
    HUB_ROLE_OWNER,
    HUB_ROLE_VIEWER,
    PLATFORM_ROLE_ADMIN,
    hub_role_satisfies,
    is_link_direction_allowed,
)
from common.models.database import AuditLog, HubLink, User
from common.schemas.hubs import (
    HubCreate,
    HubLinkCreate,
    HubLinkRead,
    HubMemberCreate,
    HubMemberRead,
    HubRead,
    HubSummary,
    HubUpdate,
)
from common.services.hub_repository import (
    DuplicateSlugError,
    HubNotEmptyError,
    LastOwnerError,
    archive_hub,
    count_owners,
    create_hub,
    create_link,
    delete_hub_if_empty,
    get_hub_by_slug,
    get_link,
    get_membership,
    list_hubs_for_user,
    list_links,
    list_members,
    remove_member,
    update_hub,
    upsert_member,
)
from common.services.hub_resolver import validate_link_creation
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from gateway.auth.dependencies import get_current_user
from gateway.auth.hub_context import HubContext, require_hub
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/hubs", tags=["hubs"])
logger = logging.getLogger("gateway.api.hubs")


class TransferOwnershipPayload(BaseModel):
    new_owner_user_id: str
    keep_previous_owner: Optional[bool] = False


class MemberRoleUpdatePayload(BaseModel):
    hub_role: str


class LinkUpdatePayload(BaseModel):
    access_level: str


async def _log_audit_event(
    session: AsyncSession,
    *,
    hub_id: Optional[str],
    actor_user_id: Optional[str],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    summary: Optional[str] = None,
    before_json: Optional[Dict[str, Any]] = None,
    after_json: Optional[Dict[str, Any]] = None,
) -> None:
    audit = AuditLog(
        id=str(uuid.uuid4()),
        hub_id=hub_id,
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        summary=summary,
        before_json=before_json,
        after_json=after_json,
        created_at=datetime.now(timezone.utc),
    )
    session.add(audit)


# --- Hub Collection Routes ---


@router.get("", response_model=List[HubSummary])
async def list_hubs(
    hub_type: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    include_archived: bool = Query(False),
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """List hubs accessible to current user (or all hubs for platform admin)."""
    user_id = user.get("sub") or user.get("id", "")
    is_admin = user.get("platform_role") == PLATFORM_ROLE_ADMIN

    results = await list_hubs_for_user(
        db,
        user_id=user_id,
        is_platform_admin=is_admin,
        hub_type=hub_type,
        include_archived=include_archived,
    )
    if q:
        q_lower = q.lower()
        results = [(h, r) for h, r in results if q_lower in h.name.lower() or q_lower in h.slug.lower()]

    return [
        HubSummary(
            id=h.id,
            slug=h.slug,
            name=h.name,
            hub_type=h.hub_type,
            description=h.description,
            accent=h.accent,
            icon=h.icon,
            owner_id=h.owner_id,
            is_archived=h.is_archived,
            created_at=h.created_at,
            updated_at=h.updated_at,
            my_role=r,
        )
        for h, r in results
    ]


@router.post("", response_model=HubRead, status_code=status.HTTP_201_CREATED)
async def create_new_hub(
    payload: HubCreate,
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new typed Hub. Creator becomes initial owner."""
    settings = get_settings()
    user_id = user.get("sub") or user.get("id", "")
    is_admin = user.get("platform_role") == PLATFORM_ROLE_ADMIN

    if not is_admin and not getattr(settings, "ALLOW_MEMBER_HUB_CREATION", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform policy disallows member hub creation",
        )

    try:
        hub = await create_hub(
            db,
            data=payload,
            owner_id=user_id,
        )
        await _log_audit_event(
            db,
            hub_id=hub.id,
            actor_user_id=user_id,
            action="create",
            resource_type="hub",
            resource_id=hub.id,
            summary=f"Created {hub.hub_type} hub '{hub.name}'",
            after_json={"id": hub.id, "slug": hub.slug, "hub_type": hub.hub_type},
        )
        await db.commit()
        return hub
    except DuplicateSlugError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Slug '{payload.slug}' is already taken for hub_type '{payload.hub_type}'",
            headers={"X-Error-Code": "HUB_SLUG_TAKEN"},
        )


@router.get("/slug-available")
async def check_slug_available(
    hub_type: str = Query(...),
    slug: str = Query(...),
    db: AsyncSession = Depends(get_async_db),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Check if a slug is available for a given hub_type."""
    existing = await get_hub_by_slug(db, hub_type=hub_type, slug=slug)
    available = existing is None
    suggestion = f"{slug}-1" if not available else slug
    return {"available": available, "suggestion": suggestion}


@router.get("/{hub_id}", response_model=HubRead)
async def get_hub_detail(
    ctx: HubContext = Depends(require_hub(min_role=HUB_ROLE_VIEWER)),
):
    """Fetch hub metadata by ID."""
    return ctx.hub


@router.patch("/{hub_id}", response_model=HubRead)
async def update_hub_metadata(
    payload: HubUpdate,
    ctx: HubContext = Depends(require_hub(min_role=HUB_ROLE_MAINTAINER)),
    db: AsyncSession = Depends(get_async_db),
):
    """Update hub metadata (name, slug, description, accent, icon, settings)."""
    # Verify slug locking on ingestion hubs with datastores
    if payload.slug is not None and payload.slug != ctx.hub.slug:
        if ctx.hub.hub_type == "ingestion":
            bindings = ctx.hub.datastore_bindings
            if bindings:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Ingestion hub slug is locked while datastore bindings exist",
                    headers={"X-Error-Code": "HUB_SLUG_LOCKED"},
                )

    try:
        updated = await update_hub(
            db,
            hub_id=ctx.hub_id,
            data=payload,
        )
        await _log_audit_event(
            db,
            hub_id=ctx.hub_id,
            actor_user_id=ctx.user_id,
            action="update",
            resource_type="hub",
            resource_id=ctx.hub_id,
            summary=f"Updated hub '{ctx.hub_id}' metadata",
        )
        await db.commit()
        return updated
    except DuplicateSlugError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Slug '{payload.slug}' is already taken",
            headers={"X-Error-Code": "HUB_SLUG_TAKEN"},
        )


@router.post("/{hub_id}/archive", response_model=HubRead)
async def archive_hub_endpoint(
    ctx: HubContext = Depends(require_hub(min_role=HUB_ROLE_OWNER)),
    db: AsyncSession = Depends(get_async_db),
):
    """Archive a hub."""
    hub = await archive_hub(db, hub_id=ctx.hub_id)
    await _log_audit_event(
        db,
        hub_id=ctx.hub_id,
        actor_user_id=ctx.user_id,
        action="archive",
        resource_type="hub",
        resource_id=ctx.hub_id,
        summary=f"Archived hub '{ctx.hub_id}'",
    )
    await db.commit()
    return hub


@router.post("/{hub_id}/unarchive", response_model=HubRead)
async def unarchive_hub_endpoint(
    ctx: HubContext = Depends(require_hub(min_role=HUB_ROLE_OWNER, allow_archived=True)),
    db: AsyncSession = Depends(get_async_db),
):
    """Unarchive an archived hub."""
    ctx.hub.is_archived = False
    await _log_audit_event(
        db,
        hub_id=ctx.hub_id,
        actor_user_id=ctx.user_id,
        action="unarchive",
        resource_type="hub",
        resource_id=ctx.hub_id,
        summary=f"Unarchived hub '{ctx.hub_id}'",
    )
    await db.commit()
    await db.refresh(ctx.hub)
    return ctx.hub


@router.delete("/{hub_id}", status_code=status.HTTP_24_NO_CONTENT if hasattr(status, "HTTP_24_NO_CONTENT") else status.HTTP_204_NO_CONTENT)
async def delete_empty_hub(
    ctx: HubContext = Depends(require_hub(min_role=HUB_ROLE_OWNER)),
    db: AsyncSession = Depends(get_async_db),
):
    """Hard-delete a hub if and only if it has zero non-membership resources."""
    try:
        await delete_hub_if_empty(db, hub_id=ctx.hub_id)
        await _log_audit_event(
            db,
            hub_id=ctx.hub_id,
            actor_user_id=ctx.user_id,
            action="delete",
            resource_type="hub",
            resource_id=ctx.hub_id,
            summary=f"Deleted empty hub '{ctx.hub_id}'",
        )
        await db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HubNotEmptyError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
            headers={"X-Error-Code": "HUB_NOT_EMPTY"},
        )


# --- Membership Routes ---


@router.get("/{hub_id}/members", response_model=List[HubMemberRead])
async def list_hub_members(
    ctx: HubContext = Depends(require_hub(min_role=HUB_ROLE_VIEWER)),
    db: AsyncSession = Depends(get_async_db),
):
    """List members of a hub."""
    members = await list_members(db, hub_id=ctx.hub_id)
    return members


@router.post("/{hub_id}/members", response_model=HubMemberRead, status_code=status.HTTP_201_CREATED)
async def add_hub_member(
    payload: HubMemberCreate,
    ctx: HubContext = Depends(require_hub(min_role=HUB_ROLE_MAINTAINER)),
    db: AsyncSession = Depends(get_async_db),
):
    """Add a member to the hub."""
    if payload.hub_role == HUB_ROLE_OWNER and ctx.hub_role != HUB_ROLE_OWNER and not ctx.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only hub owners or platform admins can assign the owner role",
            headers={"X-Error-Code": "CANNOT_GRANT_OWNER"},
        )

    # Resolve user
    user_stmt = select(User).where(User.id == payload.user_id)
    target_user = (await db.execute(user_stmt)).scalar_one_or_none()
    if target_user is None or not target_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Check if already member
    existing = await get_membership(db, hub_id=ctx.hub_id, user_id=payload.user_id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User '{payload.user_id}' is already a member of hub '{ctx.hub_id}'",
            headers={"X-Error-Code": "ALREADY_MEMBER"},
        )

    member = await upsert_member(
        db,
        hub_id=ctx.hub_id,
        user_id=payload.user_id,
        hub_role=payload.hub_role,
        invited_by=ctx.user_id,
    )
    await _log_audit_event(
        db,
        hub_id=ctx.hub_id,
        actor_user_id=ctx.user_id,
        action="create",
        resource_type="hub_member",
        resource_id=member.id,
        summary=f"Added member {payload.user_id} with role '{payload.hub_role}'",
    )
    await db.commit()
    return member


@router.patch("/{hub_id}/members/{user_id}", response_model=HubMemberRead)
async def update_member_role(
    user_id: str,
    payload: MemberRoleUpdatePayload,
    ctx: HubContext = Depends(require_hub(min_role=HUB_ROLE_MAINTAINER)),
    db: AsyncSession = Depends(get_async_db),
):
    """Update role for an existing hub member."""
    existing = await get_membership(db, hub_id=ctx.hub_id, user_id=user_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )

    if payload.hub_role == HUB_ROLE_OWNER and ctx.hub_role != HUB_ROLE_OWNER and not ctx.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only hub owners or platform admins can assign the owner role",
            headers={"X-Error-Code": "CANNOT_GRANT_OWNER"},
        )

    # Last owner demotion protection
    if existing.hub_role == HUB_ROLE_OWNER and payload.hub_role != HUB_ROLE_OWNER:
        owner_cnt = await count_owners(db, hub_id=ctx.hub_id)
        if owner_cnt <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A hub must retain at least one owner",
                headers={"X-Error-Code": "LAST_OWNER"},
            )

    member = await upsert_member(
        db,
        hub_id=ctx.hub_id,
        user_id=user_id,
        hub_role=payload.hub_role,
        invited_by=ctx.user_id,
    )
    await _log_audit_event(
        db,
        hub_id=ctx.hub_id,
        actor_user_id=ctx.user_id,
        action="update",
        resource_type="hub_member",
        resource_id=member.id,
        summary=f"Updated role for member {user_id} to '{payload.hub_role}'",
    )
    await db.commit()
    return member


@router.delete("/{hub_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_hub_member(
    user_id: str,
    ctx: HubContext = Depends(require_hub(min_role=HUB_ROLE_VIEWER)),
    db: AsyncSession = Depends(get_async_db),
):
    """Remove a member from the hub. Maintainer required unless user is removing self."""
    is_self = user_id == ctx.user_id
    if not is_self and not hub_role_satisfies(ctx.hub_role, HUB_ROLE_MAINTAINER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient hub role to remove members",
        )

    existing = await get_membership(db, hub_id=ctx.hub_id, user_id=user_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )

    if existing.hub_role == HUB_ROLE_OWNER:
        owner_cnt = await count_owners(db, hub_id=ctx.hub_id)
        if owner_cnt <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A hub must retain at least one owner",
                headers={"X-Error-Code": "LAST_OWNER"},
            )

    try:
        await remove_member(db, hub_id=ctx.hub_id, user_id=user_id)
        await _log_audit_event(
            db,
            hub_id=ctx.hub_id,
            actor_user_id=ctx.user_id,
            action="delete",
            resource_type="hub_member",
            resource_id=existing.id,
            summary=f"Removed member {user_id}",
        )
        await db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except LastOwnerError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A hub must retain at least one owner",
            headers={"X-Error-Code": "LAST_OWNER"},
        )


@router.post("/{hub_id}/transfer-ownership", response_model=HubRead)
async def transfer_ownership(
    payload: TransferOwnershipPayload,
    ctx: HubContext = Depends(require_hub(min_role=HUB_ROLE_OWNER)),
    db: AsyncSession = Depends(get_async_db),
):
    """Transfer hub ownership to another active member."""
    if payload.new_owner_user_id == ctx.user_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot transfer ownership to yourself",
        )

    target_user = (await db.execute(select(User).where(User.id == payload.new_owner_user_id))).scalar_one_or_none()
    if target_user is None or target_user.status != "active":

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target user for ownership transfer not found",
        )

    # Ensure target user is owner
    await upsert_member(
        db,
        hub_id=ctx.hub_id,
        user_id=payload.new_owner_user_id,
        hub_role=HUB_ROLE_OWNER,
        invited_by=ctx.user_id,
    )
    ctx.hub.owner_id = payload.new_owner_user_id

    # Demote previous owner unless keep_previous_owner is True
    if not payload.keep_previous_owner:
        await upsert_member(
            db,
            hub_id=ctx.hub_id,
            user_id=ctx.user_id,
            hub_role=HUB_ROLE_MAINTAINER,
            invited_by=ctx.user_id,
        )

    await _log_audit_event(
        db,
        hub_id=ctx.hub_id,
        actor_user_id=ctx.user_id,
        action="transfer",
        resource_type="hub",
        resource_id=ctx.hub_id,
        summary=f"Transferred ownership from {ctx.user_id} to {payload.new_owner_user_id}",
    )
    await db.commit()
    await db.refresh(ctx.hub)
    return ctx.hub


# --- Link Routes ---


@router.get("/{hub_id}/links", response_model=List[HubLinkRead])
async def list_hub_links(
    direction: str = Query("outgoing"),
    ctx: HubContext = Depends(require_hub(min_role=HUB_ROLE_VIEWER)),
    db: AsyncSession = Depends(get_async_db),
):
    """List cross-hub links for a hub."""
    links = await list_links(db, hub_id=ctx.hub_id, direction=direction)
    return links


@router.get("/{hub_id}/linkable-targets")
async def list_linkable_targets(
    access_level: str = Query("read"),
    ctx: HubContext = Depends(require_hub(min_role=HUB_ROLE_VIEWER)),
    db: AsyncSession = Depends(get_async_db),
):
    """List hubs the caller can legally link to from this hub."""
    user_id = ctx.user_id
    is_admin = ctx.is_platform_admin

    all_user_hubs = await list_hubs_for_user(db, user_id=user_id, is_platform_admin=is_admin)
    linkable = []
    for h in all_user_hubs:
        if h.id == ctx.hub_id:
            continue
        if is_link_direction_allowed(ctx.hub.hub_type, h.hub_type):
            mem = await get_membership(db, hub_id=h.id, user_id=user_id)
            if is_admin or (mem and hub_role_satisfies(mem.hub_role, HUB_ROLE_CONTRIBUTOR)):
                linkable.append({"id": h.id, "name": h.name, "slug": h.slug, "hub_type": h.hub_type})
    return linkable


@router.post("/{hub_id}/links", response_model=HubLinkRead, status_code=status.HTTP_201_CREATED)
async def create_hub_link(
    payload: HubLinkCreate,
    ctx: HubContext = Depends(require_hub(min_role=HUB_ROLE_MAINTAINER)),
    db: AsyncSession = Depends(get_async_db),
):
    """Create a cross-hub link from this hub to a target hub."""
    await validate_link_creation(
        db,
        source_hub_id=ctx.hub_id,
        target_hub_id=payload.target_hub_id,
        access_level=payload.access_level,
        actor_user_id=ctx.user_id,
        is_platform_admin=ctx.is_platform_admin,
    )

    existing = await get_link(db, source_hub_id=ctx.hub_id, target_hub_id=payload.target_hub_id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Link from '{ctx.hub_id}' to '{payload.target_hub_id}' already exists",
            headers={"X-Error-Code": "LINK_ALREADY_EXISTS"},
        )

    link = await create_link(
        db,
        source_hub_id=ctx.hub_id,
        target_hub_id=payload.target_hub_id,
        access_level=payload.access_level,
        created_by=ctx.user_id,
    )
    await _log_audit_event(
        db,
        hub_id=ctx.hub_id,
        actor_user_id=ctx.user_id,
        action="link",
        resource_type="hub_link",
        resource_id=link.id,
        summary=f"Created link to hub '{payload.target_hub_id}' with access '{payload.access_level}'",
    )
    await db.commit()
    return link


@router.patch("/{hub_id}/links/{link_id}", response_model=HubLinkRead)
async def update_hub_link(
    link_id: str,
    payload: LinkUpdatePayload,
    ctx: HubContext = Depends(require_hub(min_role=HUB_ROLE_MAINTAINER)),
    db: AsyncSession = Depends(get_async_db),
):
    """Update access level of an existing hub link."""
    link_stmt = select(HubLink).where(HubLink.id == link_id, HubLink.source_hub_id == ctx.hub_id)
    link = (await db.execute(link_stmt)).scalar_one_or_none()
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hub link not found",
        )

    link.access_level = payload.access_level
    await _log_audit_event(
        db,
        hub_id=ctx.hub_id,
        actor_user_id=ctx.user_id,
        action="update",
        resource_type="hub_link",
        resource_id=link.id,
        summary=f"Updated link '{link_id}' access level to '{payload.access_level}'",
    )
    await db.commit()
    await db.refresh(link)
    return link


@router.delete("/{hub_id}/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hub_link(
    link_id: str,
    ctx: HubContext = Depends(require_hub(min_role=HUB_ROLE_MAINTAINER)),
    db: AsyncSession = Depends(get_async_db),
):
    """Revoke a cross-hub link."""
    link_stmt = select(HubLink).where(HubLink.id == link_id, HubLink.source_hub_id == ctx.hub_id)
    link = (await db.execute(link_stmt)).scalar_one_or_none()
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hub link not found",
        )

    await db.delete(link)
    await _log_audit_event(
        db,
        hub_id=ctx.hub_id,
        actor_user_id=ctx.user_id,
        action="unlink",
        resource_type="hub_link",
        resource_id=link_id,
        summary=f"Revoked link '{link_id}'",
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
