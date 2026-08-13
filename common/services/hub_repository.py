"""Hub Repository Layer — Structurally hub-scoped data access helpers (hubs.md §3, §4.2, §5.3)."""

from datetime import datetime
from typing import Optional, TypeVar, Sequence
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.database import Hub, HubMember, HubLink, DatastoreBinding, AuditLog, Base
from common.models.hub_enums import is_link_direction_allowed, HUB_ROLE_OWNER
from common.schemas.hubs import HubCreate, HubUpdate

T = TypeVar("T", bound=Base)


class HubRepositoryError(Exception):
    """Base exception for hub repository errors."""
    pass


class HubNotFoundError(HubRepositoryError):
    """Raised when a requested hub does not exist."""
    pass


class HubArchivedError(HubRepositoryError):
    """Raised when attempting a mutating action on an archived hub."""
    pass


class HubNotEmptyError(HubRepositoryError):
    """Raised when attempting to delete a hub that still owns resources."""
    pass


class LastOwnerError(HubRepositoryError):
    """Raised when attempting to remove or demote the last owner of a hub."""
    pass


class DuplicateSlugError(HubRepositoryError):
    """Raised when creating or updating a hub with a slug that already exists for its type."""
    pass


class InvalidLinkDirectionError(HubRepositoryError):
    """Raised when attempting to create a hub link that violates the direction matrix."""
    pass


# ---------------------------------------------------------------------------
# Hub Operations
# ---------------------------------------------------------------------------

async def get_hub(session: AsyncSession, hub_id: str) -> Optional[Hub]:
    """Fetch a Hub by primary key. Returns None for soft-deleted hubs."""
    stmt = select(Hub).where(Hub.id == hub_id, Hub.is_deleted.is_(False))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_hub_by_slug(session: AsyncSession, *, hub_type: str, slug: str) -> Optional[Hub]:
    """Fetch a Hub by hub_type and slug."""
    stmt = select(Hub).where(Hub.hub_type == hub_type, Hub.slug == slug.lower())
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_hubs_for_user(
    session: AsyncSession,
    *,
    user_id: str,
    hub_type: Optional[str] = None,
    include_archived: bool = False,
    is_platform_admin: bool = False,
) -> list[tuple[Hub, str]]:
    """List hubs accessible to a user alongside their effective hub_role."""
    if is_platform_admin:
        stmt = select(Hub)
        stmt = stmt.where(Hub.is_deleted.is_(False))
        if hub_type:
            stmt = stmt.where(Hub.hub_type == hub_type)
        if not include_archived:
            stmt = stmt.where(Hub.is_archived.is_(False))
        stmt = stmt.order_by(Hub.name.asc())
        result = await session.execute(stmt)
        return [(hub, HUB_ROLE_OWNER) for hub in result.scalars().all()]

    stmt = (
        select(Hub, HubMember.hub_role)
        .join(HubMember, HubMember.hub_id == Hub.id)
        .where(HubMember.user_id == user_id)
        .where(Hub.is_deleted.is_(False))
    )
    if hub_type:
        stmt = stmt.where(Hub.hub_type == hub_type)
    if not include_archived:
        stmt = stmt.where(Hub.is_archived.is_(False))
    stmt = stmt.order_by(Hub.name.asc())
    result = await session.execute(stmt)
    return [(row[0], row[1]) for row in result.all()]


async def create_hub(session: AsyncSession, *, data: HubCreate, owner_id: str) -> Hub:
    """Create a new Hub and enroll the owner as HubMember(role='owner') in one transaction."""
    existing = await get_hub_by_slug(session, hub_type=data.hub_type, slug=data.slug)
    if existing:
        raise DuplicateSlugError(f"Hub with slug '{data.slug}' already exists for type '{data.hub_type}'.")

    hub = Hub(
        name=data.name,
        hub_type=data.hub_type,
        slug=data.slug.lower(),
        description=data.description,
        accent=data.accent,
        icon=data.icon,
        settings_json=data.settings_json,
        owner_id=owner_id,
    )
    session.add(hub)
    await session.flush()

    member = HubMember(
        hub_id=hub.id,
        user_id=owner_id,
        hub_role=HUB_ROLE_OWNER,
        invited_by=None,
    )
    session.add(member)
    await session.flush()

    if getattr(data, "initial_links", None):
        for link_item in data.initial_links:
            try:
                await create_link(
                    session,
                    source_hub_id=hub.id,
                    target_hub_id=link_item.target_hub_id,
                    access_level=link_item.access_level,
                    created_by=owner_id,
                )
            except Exception as e:
                logger.warning("Failed to create initial link to %s: %s", link_item.target_hub_id, e)

    return hub


async def update_hub(session: AsyncSession, *, hub_id: str, data: HubUpdate) -> Hub:
    """Update a Hub's metadata."""
    hub = await get_hub(session, hub_id)
    if not hub:
        raise HubNotFoundError(f"Hub '{hub_id}' not found.")

    if data.slug and data.slug.lower() != hub.slug:
        existing = await get_hub_by_slug(session, hub_type=hub.hub_type, slug=data.slug)
        if existing and existing.id != hub_id:
            raise DuplicateSlugError(f"Hub slug '{data.slug}' is already taken for type '{hub.hub_type}'.")
        hub.slug = data.slug.lower()

    if data.name is not None:
        hub.name = data.name
    if data.description is not None:
        hub.description = data.description
    if data.accent is not None:
        hub.accent = data.accent
    if data.icon is not None:
        hub.icon = data.icon
    if data.settings_json is not None:
        hub.settings_json = data.settings_json

    await session.flush()
    return hub


async def archive_hub(session: AsyncSession, *, hub_id: str, archived: bool) -> Hub:
    """Archive or unarchive a Hub."""
    hub = await get_hub(session, hub_id)
    if not hub:
        raise HubNotFoundError(f"Hub '{hub_id}' not found.")
    hub.is_archived = archived
    await session.flush()
    return hub


async def delete_hub_if_empty(session: AsyncSession, *, hub_id: str, force: bool = False) -> None:
    """Delete a Hub. If force=True, marks is_deleted=True even if non-membership resources exist."""
    hub = await get_hub(session, hub_id)
    if not hub:
        raise HubNotFoundError(f"Hub '{hub_id}' not found.")

    if not force:
        counts = {}
        total_resources = 0
        for m in Base.registry.mappers:
            cls = m.class_
            if cls in (Hub, HubMember, AuditLog, HubLink):
                continue
            if hasattr(cls, "hub_id"):
                stmt = select(func.count()).select_from(cls).where(cls.hub_id == hub_id)
                if hasattr(cls, "is_deleted"):
                    stmt = stmt.where(cls.is_deleted == False)
                cnt = (await session.execute(stmt)).scalar() or 0
                if cnt > 0:
                    counts[getattr(cls, "__tablename__", str(cls))] = cnt
                    total_resources += cnt

        if total_resources > 0:
            raise HubNotEmptyError(f"Cannot delete hub '{hub_id}': it still owns {total_resources} resources ({counts}).")

    hub.is_deleted = True
    hub.deleted_at = datetime.utcnow()
    await session.flush()


# ---------------------------------------------------------------------------
# Membership Operations
# ---------------------------------------------------------------------------

async def get_membership(session: AsyncSession, *, hub_id: str, user_id: str) -> Optional[HubMember]:
    """Fetch a user's HubMember record for a hub."""
    stmt = select(HubMember).where(HubMember.hub_id == hub_id, HubMember.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_members(session: AsyncSession, *, hub_id: str) -> list[HubMember]:
    """List all members of a hub."""
    stmt = select(HubMember).where(HubMember.hub_id == hub_id).order_by(HubMember.created_at.asc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_owners(session: AsyncSession, *, hub_id: str) -> int:
    """Count the number of owners for a hub."""
    stmt = select(func.count()).select_from(HubMember).where(HubMember.hub_id == hub_id, HubMember.hub_role == HUB_ROLE_OWNER)
    return (await session.execute(stmt)).scalar() or 0


async def upsert_member(
    session: AsyncSession,
    *,
    hub_id: str,
    user_id: str,
    hub_role: str,
    invited_by: Optional[str] = None,
) -> HubMember:
    """Add or update a member's role in a hub."""
    member = await get_membership(session, hub_id=hub_id, user_id=user_id)
    if member:
        if member.hub_role == HUB_ROLE_OWNER and hub_role != HUB_ROLE_OWNER:
            owners = await count_owners(session, hub_id=hub_id)
            if owners <= 1:
                raise LastOwnerError(f"Cannot demote user '{user_id}': they are the last owner of hub '{hub_id}'.")
        member.hub_role = hub_role
    else:
        member = HubMember(
            hub_id=hub_id,
            user_id=user_id,
            hub_role=hub_role,
            invited_by=invited_by,
        )
        session.add(member)

    await session.flush()
    return member


async def remove_member(session: AsyncSession, *, hub_id: str, user_id: str) -> None:
    """Remove a member from a hub."""
    member = await get_membership(session, hub_id=hub_id, user_id=user_id)
    if not member:
        return

    if member.hub_role == HUB_ROLE_OWNER:
        owners = await count_owners(session, hub_id=hub_id)
        if owners <= 1:
            raise LastOwnerError(f"Cannot remove user '{user_id}': they are the last owner of hub '{hub_id}'.")

    await session.delete(member)
    await session.flush()


# ---------------------------------------------------------------------------
# Link Operations
# ---------------------------------------------------------------------------

async def list_links(session: AsyncSession, *, source_hub_id: str) -> list[HubLink]:
    """List outgoing links from a source hub."""
    stmt = select(HubLink).where(HubLink.source_hub_id == source_hub_id).order_by(HubLink.created_at.asc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_link(session: AsyncSession, *, source_hub_id: str, target_hub_id: str) -> Optional[HubLink]:
    """Fetch a specific HubLink."""
    stmt = select(HubLink).where(HubLink.source_hub_id == source_hub_id, HubLink.target_hub_id == target_hub_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_link(
    session: AsyncSession,
    *,
    source_hub_id: str,
    target_hub_id: str,
    access_level: str = "read",
    created_by: Optional[str] = None,
) -> HubLink:
    """Create a new HubLink after validating direction allowed."""
    source_hub = await get_hub(session, source_hub_id)
    target_hub = await get_hub(session, target_hub_id)
    if not source_hub or not target_hub:
        raise HubNotFoundError("Source or target hub not found.")

    if not is_link_direction_allowed(source_hub.hub_type, target_hub.hub_type):
        raise InvalidLinkDirectionError(
            f"Link from '{source_hub.hub_type}' to '{target_hub.hub_type}' is not allowed."
        )

    link = await get_link(session, source_hub_id=source_hub_id, target_hub_id=target_hub_id)
    if link:
        link.access_level = access_level
    else:
        link = HubLink(
            source_hub_id=source_hub_id,
            target_hub_id=target_hub_id,
            access_level=access_level,
            created_by=created_by,
        )
        session.add(link)

    await session.flush()
    return link


# ---------------------------------------------------------------------------
# Datastore Binding Operations
# ---------------------------------------------------------------------------

async def list_bindings(session: AsyncSession, *, hub_id: str) -> list[DatastoreBinding]:
    """List datastore bindings owned by a hub."""
    stmt = select(DatastoreBinding).where(DatastoreBinding.hub_id == hub_id).order_by(DatastoreBinding.name.asc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Structurally Hub-Scoped Accessors
# ---------------------------------------------------------------------------

async def get_scoped(session: AsyncSession, model: type[T], *, hub_id: str, resource_id: str) -> Optional[T]:
    """Fetch a hub-scoped row by resource_id AND hub_id.

    Returns None when the row belongs to another hub (preventing IDOR).
    Raises TypeError if model is not marked with `__hub_scoped__ = True`.
    """
    if not getattr(model, "__hub_scoped__", False):
        raise TypeError(f"Model '{model.__name__}' is not hub-scoped; use a plain query.")

    stmt = select(model).where(model.id == resource_id, model.hub_id == hub_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_scoped(
    session: AsyncSession,
    model: type[T],
    *,
    hub_id: str,
    limit: int = 50,
    offset: int = 0,
    order_by=None,
    extra_filters: Sequence = (),
) -> list[T]:
    """List rows for a hub-scoped model filtered by hub_id."""
    if not getattr(model, "__hub_scoped__", False):
        raise TypeError(f"Model '{model.__name__}' is not hub-scoped; use a plain query.")

    stmt = select(model).where(model.hub_id == hub_id)
    for extra_filter in extra_filters:
        stmt = stmt.where(extra_filter)

    if order_by is not None:
        stmt = stmt.order_by(order_by)
    elif hasattr(model, "created_at"):
        stmt = stmt.order_by(model.created_at.desc())

    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())
