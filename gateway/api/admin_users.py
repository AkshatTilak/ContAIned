"""Platform Admin Console API (user lifecycle, invites, audit logs) — S6-03f.

All endpoints require platform_role = "admin" and write immutable audit log rows.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.clients.postgres import get_async_db
from common.constants.roles import (
    HUB_ROLES,
    PLATFORM_ROLES,
    PLATFORM_ROLE_ADMIN,
    PLATFORM_ROLE_MEMBER,
)
from common.models.database import (
    AuditLog,
    Hub,
    HubMember,
    User,
    UserIdentity,
    UserInvite,
)
from common.observability.limiter import limiter
from common.schemas.hubs import AuditLogRead
from common.services.audit import client_ip, record_audit
from gateway.auth.dependencies import get_current_user, require_platform_admin
from gateway.auth.utils import revoke_sessions

from gateway.auth.invites import (
    InviteResult,
    create_invites,
    resend_invite,
    revoke_invite,
)
from gateway.services.mailer import send_template

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_platform_admin)],
)


# --- Schemas ---

class IdentityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    provider: str
    provider_id: str
    email: str
    created_at: datetime
    last_used_at: Optional[datetime] = None


class HubMembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hub_id: str
    hub_name: Optional[str] = None
    hub_type: Optional[str] = None
    hub_role: str
    created_at: datetime


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    platform_role: str = PLATFORM_ROLE_MEMBER
    status: str = "pending"
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    last_login: Optional[datetime] = None
    identities: List[IdentityResponse] = Field(default_factory=list)
    hub_memberships: List[HubMembershipResponse] = Field(default_factory=list)


class UserDetailResponse(UserResponse):
    recent_audit_logs: List[AuditLogRead] = Field(default_factory=list)


class UserListResponse(BaseModel):
    items: List[UserResponse]
    total: int
    limit: int
    offset: int


class PendingUserListResponse(BaseModel):
    items: List[UserResponse]
    count: int


class UserUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    platform_role: Optional[str] = None

    @field_validator("platform_role")
    @classmethod
    def validate_platform_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in PLATFORM_ROLES:
            raise ValueError(f"platform_role must be one of: {', '.join(PLATFORM_ROLES)}")
        return v


class HubGrantInput(BaseModel):
    hub_id: str
    hub_role: str


class ApproveUserRequest(BaseModel):
    platform_role: Optional[str] = None
    hub_grants: Optional[List[HubGrantInput]] = None


class RejectUserRequest(BaseModel):
    reason: Optional[str] = None


class CreateInviteRequest(BaseModel):
    emails: List[EmailStr]
    platform_role: str = PLATFORM_ROLE_MEMBER
    hub_grants: Optional[List[Dict[str, str]]] = Field(default_factory=list)
    ttl_hours: Optional[int] = None


class InviteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    platform_role: str
    hub_grants_json: List[Dict[str, Any]] = Field(default_factory=list)
    invited_by: str
    status: str
    expires_at: datetime
    accepted_at: Optional[datetime] = None
    accepted_user_id: Optional[str] = None
    resend_count: int = 0
    last_sent_at: Optional[datetime] = None
    created_at: datetime


class InviteListResponse(BaseModel):
    items: List[InviteResponse]
    total: int
    limit: int
    offset: int


class AuditLogListResponse(BaseModel):
    items: List[AuditLogRead]
    total: int
    limit: int
    offset: int


# --- Guardrail Helpers ---

def assert_not_self(actor_id: str, target_id: str, action: str) -> None:
    """409 ACTION_ON_SELF for demote / suspend / reject / delete."""
    if actor_id == target_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot {action} your own platform account",
            headers={"X-Error-Code": "ACTION_ON_SELF"},
        )


async def assert_admin_floor(db: AsyncSession, target_id: str) -> None:
    """409 LAST_ACTIVE_ADMIN if change would leave zero users with platform_role='admin' AND status='active'."""
    stmt = (
        select(func.count(User.id))
        .where(
            User.platform_role == PLATFORM_ROLE_ADMIN,
            User.status == "active",
            User.id != target_id,
        )
        .with_for_update()
    )
    res = await db.execute(stmt)
    admin_count = res.scalar() or 0

    if admin_count < 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Operation would leave zero active platform admins",
            headers={"X-Error-Code": "LAST_ACTIVE_ADMIN"},
        )


async def write_audit(
    db: AsyncSession,
    *,
    actor_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    summary: str,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None,
    hub_id: Optional[str] = None,
) -> None:
    """Append one audit_log row to the transaction."""
    ip_addr = client_ip(request) if request else None
    await record_audit(
        db,
        action=action,
        resource_type=resource_type,
        hub_id=hub_id,
        actor_user_id=actor_id,
        resource_id=resource_id,
        summary=summary,
        before=before,
        after=after,
        ip_address=ip_addr,
    )


async def _enrich_user_response(db: AsyncSession, user: User) -> UserResponse:
    """Build UserResponse with populated identities and hub memberships."""
    # Identities
    id_stmt = select(UserIdentity).where(UserIdentity.user_id == user.id)
    identities = (await db.execute(id_stmt)).scalars().all()

    # Hub memberships with Hub details
    hm_stmt = (
        select(HubMember, Hub.name, Hub.hub_type)
        .join(Hub, Hub.id == HubMember.hub_id)
        .where(HubMember.user_id == user.id)
    )
    hm_res = await db.execute(hm_stmt)
    hub_memberships = []
    for member, hub_name, hub_type in hm_res.all():
        hub_memberships.append(
            HubMembershipResponse(
                hub_id=member.hub_id,
                hub_name=hub_name,
                hub_type=hub_type,
                hub_role=member.hub_role,
                created_at=member.created_at,
            )
        )

    resp_data = UserResponse.model_validate(user)
    resp_data.identities = [IdentityResponse.model_validate(i) for i in identities]
    resp_data.hub_memberships = hub_memberships
    return resp_data


# --- User Management Endpoints ---

@router.get("/users", response_model=UserListResponse)
async def list_users(
    status_filter: Optional[str] = Query(None, alias="status"),
    platform_role: Optional[str] = Query(None),
    hub_id: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    include_deleted: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_db),
):
    """List platform users with pagination and filtering."""
    stmt = select(User)

    if not include_deleted:
        stmt = stmt.where(User.is_deleted == False)

    if status_filter:
        stmt = stmt.where(User.status == status_filter)
    if platform_role:
        stmt = stmt.where(User.platform_role == platform_role)
    if hub_id:
        subq = select(HubMember.user_id).where(HubMember.hub_id == hub_id)
        stmt = stmt.where(User.id.in_(subq))
    if q:
        search_pattern = f"%{q}%"
        stmt = stmt.where(
            (User.email.ilike(search_pattern)) | (User.display_name.ilike(search_pattern))
        )

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # Paginate
    stmt = stmt.order_by(User.created_at.desc()).offset(offset).limit(limit)
    users = (await db.execute(stmt)).scalars().all()

    items = [await _enrich_user_response(db, u) for u in users]
    return UserListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/users/pending", response_model=PendingUserListResponse)
async def list_pending_users(
    db: AsyncSession = Depends(get_async_db),
):
    """List users awaiting admin approval (sidebar badge data source)."""
    stmt = select(User).where(User.status == "pending").order_by(User.created_at.asc())
    users = (await db.execute(stmt)).scalars().all()
    items = [await _enrich_user_response(db, u) for u in users]
    return PendingUserListResponse(items=items, count=len(items))


@router.get("/users/{user_id}", response_model=UserDetailResponse)
async def get_user_detail(
    user_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Fetch user detail including identities, hub memberships, and recent audit logs."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    base_resp = await _enrich_user_response(db, user)

    # Audit logs where actor_user_id == user_id
    audit_stmt = (
        select(AuditLog)
        .where(AuditLog.actor_user_id == user_id)
        .order_by(AuditLog.created_at.desc())
        .limit(20)
    )
    audit_logs = (await db.execute(audit_stmt)).scalars().all()

    detail_resp = UserDetailResponse(
        **base_resp.model_dump(),
        recent_audit_logs=[AuditLogRead.model_validate(a) for a in audit_logs],
    )
    return detail_resp


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    payload: UserUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    actor: Dict[str, Any] = Depends(get_current_user),
):
    """Update user display name and/or platform role."""
    actor_id = actor.get("sub") or actor.get("id")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    before_data = {"display_name": user.display_name, "platform_role": user.platform_role}

    if payload.platform_role and payload.platform_role != user.platform_role:
        if user.platform_role == PLATFORM_ROLE_ADMIN and payload.platform_role == PLATFORM_ROLE_MEMBER:
            assert_not_self(actor_id, user_id, "demote")
            await assert_admin_floor(db, user_id)

            # Revoke all sessions for demoted admin
            await revoke_sessions(db, user_id)


        user.platform_role = payload.platform_role

    if payload.display_name is not None:
        user.display_name = payload.display_name

    after_data = {"display_name": user.display_name, "platform_role": user.platform_role}

    await write_audit(
        db,
        actor_id=actor_id,
        action="update",
        resource_type="user",
        resource_id=user_id,
        summary=f"Updated user {user.email}",
        before=before_data,
        after=after_data,
        request=request,
    )
    await db.commit()
    await db.refresh(user)
    return await _enrich_user_response(db, user)


@router.post("/users/{user_id}/approve", response_model=UserResponse)
async def approve_user(
    user_id: str,
    payload: ApproveUserRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    actor: Dict[str, Any] = Depends(get_current_user),
):
    """Approve a pending user, setting status to active and applying optional role and hub grants."""
    actor_id = actor.get("sub") or actor.get("id")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invalid state transition. User is not pending approval",
        )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    user.status = "active"
    user.approved_by = actor_id
    user.approved_at = now

    if payload.platform_role:
        if payload.platform_role not in PLATFORM_ROLES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid platform_role '{payload.platform_role}'",
            )
        user.platform_role = payload.platform_role

    if payload.hub_grants:
        for grant in payload.hub_grants:
            if grant.hub_role not in HUB_ROLES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid hub_role '{grant.hub_role}'",
                )
            hub = await db.get(Hub, grant.hub_id)
            if not hub or hub.is_archived:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Hub '{grant.hub_id}' not found or archived",
                )

            # Check existing membership
            existing_hm = await db.execute(
                select(HubMember).where(
                    HubMember.hub_id == grant.hub_id, HubMember.user_id == user.id
                )
            )
            if not existing_hm.scalar_one_or_none():
                db.add(
                    HubMember(
                        id=str(uuid.uuid4()),
                        hub_id=grant.hub_id,
                        user_id=user.id,
                        hub_role=grant.hub_role,
                        created_at=now,
                    )
                )

    await write_audit(
        db,
        actor_id=actor_id,
        action="update",
        resource_type="user",
        resource_id=user_id,
        summary=f"Approved user {user.email}",
        before={"status": "pending"},
        after={"status": "active", "platform_role": user.platform_role},
        request=request,
    )
    await db.commit()

    # Send approval email notification
    await send_template(
        to=user.email,
        template="approved",
        subject="Your ContAIned Account Has Been Approved",
        name=user.display_name or user.email,
    )

    await db.refresh(user)
    return await _enrich_user_response(db, user)


@router.post("/users/{user_id}/reject", response_model=UserResponse)
async def reject_user(
    user_id: str,
    payload: RejectUserRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    actor: Dict[str, Any] = Depends(get_current_user),
):
    """Reject a pending user, setting status to rejected and sending reason email."""
    actor_id = actor.get("sub") or actor.get("id")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invalid state transition. User is not pending approval",
        )

    user.status = "rejected"

    # Revoke sessions
    await revoke_sessions(db, user_id)

    await write_audit(
        db,
        actor_id=actor_id,
        action="update",
        resource_type="user",
        resource_id=user_id,
        summary=f"Rejected user {user.email}",
        before={"status": "pending"},
        after={"status": "rejected", "reason": payload.reason},
        request=request,
    )
    await db.commit()

    # Send rejection notification email
    await send_template(
        to=user.email,
        template="rejected",
        subject="Your ContAIned Account Registration Update",
        name=user.display_name or user.email,
        reason=payload.reason or "Registration criteria not met.",
    )

    await db.refresh(user)
    return await _enrich_user_response(db, user)


@router.post("/users/{user_id}/suspend", response_model=UserResponse)
async def suspend_user(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    actor: Dict[str, Any] = Depends(get_current_user),
):
    """Suspend an active user and immediately revoke all active sessions."""
    actor_id = actor.get("sub") or actor.get("id")
    assert_not_self(actor_id, user_id, "suspend")
    await assert_admin_floor(db, user_id)

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invalid state transition. User is not active",
        )

    user.status = "suspended"

    # Immediately delete all UserSession rows in same transaction
    await revoke_sessions(db, user_id)


    await write_audit(
        db,
        actor_id=actor_id,
        action="update",
        resource_type="user",
        resource_id=user_id,
        summary=f"Suspended user {user.email}",
        before={"status": "active"},
        after={"status": "suspended"},
        request=request,
    )
    await db.commit()
    await db.refresh(user)
    return await _enrich_user_response(db, user)


@router.post("/users/{user_id}/reinstate", response_model=UserResponse)
async def reinstate_user(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    actor: Dict[str, Any] = Depends(get_current_user),
):
    """Reinstate a suspended user back to active status."""
    actor_id = actor.get("sub") or actor.get("id")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.status != "suspended":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invalid state transition. User is not suspended",
        )

    user.status = "active"

    await write_audit(
        db,
        actor_id=actor_id,
        action="update",
        resource_type="user",
        resource_id=user_id,
        summary=f"Reinstated user {user.email}",
        before={"status": "suspended"},
        after={"status": "active"},
        request=request,
    )
    await db.commit()
    await db.refresh(user)
    return await _enrich_user_response(db, user)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    request: Request,
    response: Response,
    hard: bool = Query(False),
    db: AsyncSession = Depends(get_async_db),
    actor: Dict[str, Any] = Depends(get_current_user),
):
    """Delete a user. Soft-deletes by default; hard purges if hard=true or user is already soft-deleted."""
    actor_id = actor.get("sub") or actor.get("id")
    assert_not_self(actor_id, user_id, "delete")
    await assert_admin_floor(db, user_id)

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Check hub ownership for active hubs
    owned_hubs_stmt = select(Hub.id, Hub.name).where(
        Hub.owner_id == user_id, Hub.is_archived.is_(False), Hub.is_deleted.is_(False)
    )
    owned_hubs = (await db.execute(owned_hubs_stmt)).all()
    if owned_hubs:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "User owns hubs; transfer ownership first",
                "hubs": [{"id": h.id, "name": h.name} for h in owned_hubs],
            },
        )

    # Perform Hard Delete if hard=true or already soft-deleted
    if hard or user.is_deleted:
        await write_audit(
            db,
            actor_id=actor_id,
            action="delete",
            resource_type="user",
            resource_id=user_id,
            summary=f"Hard purged user {user.email}",
            before={"email": user.email, "status": user.status, "is_deleted": user.is_deleted},
            request=request,
        )
        await revoke_sessions(db, user_id)
        await db.delete(user)
        await db.commit()
        response.status_code = status.HTTP_204_NO_CONTENT
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # Perform Soft Delete
    now = datetime.utcnow()
    user.is_deleted = True
    user.deleted_at = now
    await revoke_sessions(db, user_id)

    await write_audit(
        db,
        actor_id=actor_id,
        action="delete",
        resource_type="user",
        resource_id=user_id,
        summary=f"Soft deleted user {user.email}",
        before={"email": user.email, "status": user.status},
        after={"is_deleted": True, "deleted_at": now.isoformat()},
        request=request,
    )
    await db.commit()
    return {"status": "deleted", "id": user_id, "soft": True}


# --- Invite Management Endpoints ---

@router.post("/invites", response_model=List[InviteResult], status_code=status.HTTP_201_CREATED)
@limiter.limit("60/hour")
async def issue_invites(
    request: Request,
    payload: CreateInviteRequest,
    db: AsyncSession = Depends(get_async_db),
    actor: Dict[str, Any] = Depends(get_current_user),
):
    """Create and issue email invitations (single or bulk)."""
    actor_id = actor.get("sub") or actor.get("id")
    results = await create_invites(
        db,
        emails=[str(e) for e in payload.emails],
        platform_role=payload.platform_role,
        hub_grants=payload.hub_grants,
        invited_by=actor_id,
        ttl_hours=payload.ttl_hours,
    )
    return results


@router.get("/invites", response_model=InviteListResponse)
async def list_invites(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_db),
):
    """List pending/accepted/revoked/expired user invites (never includes token_hash)."""
    stmt = select(UserInvite)

    if status_filter:
        stmt = stmt.where(UserInvite.status == status_filter)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(UserInvite.created_at.desc()).offset(offset).limit(limit)
    invites = (await db.execute(stmt)).scalars().all()

    items = [InviteResponse.model_validate(inv) for inv in invites]
    return InviteListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/invites/{invite_id}/resend", response_model=InviteResult)
async def resend_user_invite(
    invite_id: str,
    db: AsyncSession = Depends(get_async_db),
    actor: Dict[str, Any] = Depends(get_current_user),
):
    """Resend an active pending invitation link with a fresh token."""
    actor_id = actor.get("sub") or actor.get("id")

    # Enforce 3/hour per invite resend limit
    invite = await db.get(UserInvite, invite_id)
    if not invite or invite.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending invite not found",
        )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if invite.last_sent_at:
        last_sent_naive = (
            invite.last_sent_at.replace(tzinfo=None)
            if invite.last_sent_at.tzinfo is not None
            else invite.last_sent_at
        )
        if (now - last_sent_naive).total_seconds() < 3600 and (invite.resend_count or 0) >= 3:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Invite resend limit reached (3 per hour)",
            )

    result = await resend_invite(db, invite_id=invite_id, actor_id=actor_id)
    return result


@router.delete("/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_user_invite(
    invite_id: str,
    db: AsyncSession = Depends(get_async_db),
    actor: Dict[str, Any] = Depends(get_current_user),
):
    """Revoke a pending user invitation."""
    actor_id = actor.get("sub") or actor.get("id")
    await revoke_invite(db, invite_id=invite_id, actor_id=actor_id)


# --- Audit Log Endpoint ---

@router.get("/audit", response_model=AuditLogListResponse)
async def list_audit_logs(
    actor_user_id: Optional[str] = Query(None),
    hub_id: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    since: Optional[datetime] = Query(None, alias="from"),
    until: Optional[datetime] = Query(None, alias="to"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_db),
):
    """Fetch system audit log records with filtering and pagination (Platform Admin only)."""
    stmt = select(AuditLog)

    if actor_user_id:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    if hub_id:
        stmt = stmt.where(AuditLog.hub_id == hub_id)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if since:
        stmt = stmt.where(AuditLog.created_at >= since)
    if until:
        stmt = stmt.where(AuditLog.created_at <= until)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset(offset).limit(limit)
    records = (await db.execute(stmt)).scalars().all()

    items = [AuditLogRead.model_validate(r) for r in records]
    return AuditLogListResponse(items=items, total=total, limit=limit, offset=offset)
