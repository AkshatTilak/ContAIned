"""Invite issuance, redemption, preview, resend, revocation, and expiration service (S6-03d)."""

import hashlib
import hmac
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from common.config.settings import get_settings
from common.constants.roles import (
    HUB_ROLES,
    PLATFORM_ROLES,
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
from gateway.auth.passwords import hash_password, validate_password_policy

logger = logging.getLogger("gateway.auth.invites")


def generate_invite_token() -> Tuple[str, str]:
    """Generate a raw invite token and its SHA-256 hash.

    The raw token (256 bits entropy) is returned to the caller exactly once
    and is never stored, logged, or audited.
    """
    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return raw, token_hash


def token_matches(raw: str, stored_hash: str) -> bool:
    """Compare a raw token against a stored hash in constant time."""
    computed = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return hmac.compare_digest(computed, stored_hash)


class HubGrantInput(BaseModel):
    hub_id: str
    hub_role: str


class InviteResult(BaseModel):
    email: str
    status: str
    invite_id: Optional[str] = None
    delivered: bool = False
    invite_url: Optional[str] = None
    detail: Optional[str] = None


class HubGrantPreview(BaseModel):
    id: str
    name: str
    hub_type: str
    hub_role: str


class InvitePreview(BaseModel):
    email: str
    inviter_display_name: Optional[str] = None
    platform_role: str
    hubs: List[HubGrantPreview] = Field(default_factory=list)
    expires_at: datetime


async def create_invites(
    db: AsyncSession,
    *,
    emails: List[str],
    platform_role: str = PLATFORM_ROLE_MEMBER,
    hub_grants: Optional[List[Dict[str, Any]]] = None,
    invited_by: str,
    ttl_hours: Optional[int] = None,
) -> List[InviteResult]:
    """Issue single-use email invitations with pre-assigned platform roles and hub grants.

    Returns partial-success results per input email.
    """
    if platform_role not in PLATFORM_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid platform_role '{platform_role}'. Must be one of: {', '.join(PLATFORM_ROLES)}",
        )

    # Validate hub grants
    validated_grants: List[Dict[str, Any]] = []
    if hub_grants:
        for idx, grant in enumerate(hub_grants):
            hub_id = grant.get("hub_id")
            hub_role = grant.get("hub_role")
            if not hub_id or not hub_role:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Hub grant at index {idx} must specify both 'hub_id' and 'hub_role'",
                )
            if hub_role not in HUB_ROLES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Hub role '{hub_role}' at index {idx} must be one of: {', '.join(HUB_ROLES)}",
                )

            # Resolve non-archived hub
            hub_stmt = select(Hub).where(Hub.id == hub_id, Hub.is_archived.is_(False))
            hub_res = await db.execute(hub_stmt)
            hub_obj = hub_res.scalar_one_or_none()
            if not hub_obj:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Hub '{hub_id}' at index {idx} does not exist or is archived",
                )
            validated_grants.append({"hub_id": hub_id, "hub_role": hub_role})

    settings = get_settings()
    default_ttl = getattr(settings, "INVITE_TTL_HOURS", 72)
    effective_ttl = ttl_hours if ttl_hours is not None else default_ttl
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=effective_ttl)

    # Deduplicate input emails
    unique_emails = list(dict.fromkeys(e.strip().lower() for e in emails if e.strip()))
    results: List[InviteResult] = []

    inviter = await db.get(User, invited_by)
    inviter_name = inviter.display_name if inviter else "Administrator"

    for email_str in unique_emails:
        # Check existing user
        user_stmt = select(User).where(User.email == email_str)
        user_res = await db.execute(user_stmt)
        if user_res.scalar_one_or_none():
            results.append(
                InviteResult(
                    email=email_str,
                    status="rejected",
                    detail="A user account with this email already exists",
                )
            )
            continue

        # Check existing pending invite
        open_invite_stmt = select(UserInvite).where(
            UserInvite.email == email_str,
            UserInvite.status == "pending",
        )
        if (await db.execute(open_invite_stmt)).scalar_one_or_none():
            results.append(
                InviteResult(
                    email=email_str,
                    status="rejected",
                    detail="An active invite already exists for this email",
                )
            )
            continue

        raw_token, token_h = generate_invite_token()
        invite_id = str(uuid.uuid4())

        invite = UserInvite(
            id=invite_id,
            email=email_str,
            token_hash=token_h,
            invited_by=invited_by,
            platform_role=platform_role,
            hub_grants_json=validated_grants,
            status="pending",
            expires_at=expires_at,
            created_at=now,
            last_sent_at=now,
        )
        db.add(invite)

        audit = AuditLog(
            id=str(uuid.uuid4()),
            actor_user_id=invited_by,
            action="create",
            resource_type="invite",
            resource_id=invite_id,
            summary=f"Issued invite to {email_str}",
            created_at=now,
        )
        db.add(audit)

        public_url = getattr(settings, "APP_PUBLIC_URL", "http://localhost:5173")
        invite_url = f"{public_url}/auth/invite/{raw_token}"

        results.append(
            InviteResult(
                email=email_str,
                status="created",
                invite_id=invite_id,
                delivered=False,
                invite_url=invite_url,
            )
        )

    await db.commit()
    return results


async def get_invite_preview(db: AsyncSession, raw_token: str) -> InvitePreview:
    """Retrieve unauthenticated preview details for an invite link.

    Looks up strictly by token_hash.
    """
    token_h = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    stmt = select(UserInvite).where(UserInvite.token_hash == token_h)
    res = await db.execute(stmt)
    invite = res.scalar_one_or_none()

    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found or expired",
        )

    if invite.status == "accepted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invite already accepted",
        )

    now = datetime.now(timezone.utc)
    exp_utc = invite.expires_at.replace(tzinfo=timezone.utc) if invite.expires_at.tzinfo is None else invite.expires_at

    if invite.status in ("revoked", "expired") or exp_utc <= now:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found or expired",
        )

    # Fetch inviter
    inviter = await db.get(User, invite.invited_by)
    inviter_name = inviter.display_name if inviter else "Administrator"

    # Fetch hub details
    hubs_preview: List[HubGrantPreview] = []
    grants = invite.hub_grants_json or []
    for grant in grants:
        hub_id = grant.get("hub_id")
        hub_role = grant.get("hub_role")
        if hub_id:
            h_obj = await db.get(Hub, hub_id)
            if h_obj and not h_obj.is_archived:
                hubs_preview.append(
                    HubGrantPreview(
                        id=h_obj.id,
                        name=h_obj.name,
                        hub_type=h_obj.hub_type,
                        hub_role=hub_role,
                    )
                )

    return InvitePreview(
        email=invite.email,
        inviter_display_name=inviter_name,
        platform_role=invite.platform_role,
        hubs=hubs_preview,
        expires_at=exp_utc,
    )


async def redeem_invite(
    db: AsyncSession,
    *,
    raw_token: str,
    email: str,
    provider: str,
    provider_id: str,
    password: Optional[str] = None,
    display_name: Optional[str] = None,
    avatar_url: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> User:
    """Redeem an invitation using row-level locking (FOR UPDATE)."""
    norm_email = email.strip().lower()
    token_h = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    # Lock invite row
    stmt = (
        select(UserInvite)
        .where(UserInvite.token_hash == token_h)
        .with_for_update()
    )
    res = await db.execute(stmt)
    invite = res.scalar_one_or_none()

    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found or expired",
        )

    if invite.email != norm_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invite email mismatch",
        )

    if invite.status == "accepted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invite already accepted",
        )

    now = datetime.now(timezone.utc)
    exp_utc = invite.expires_at.replace(tzinfo=timezone.utc) if invite.expires_at.tzinfo is None else invite.expires_at

    if invite.status in ("revoked", "expired") or exp_utc <= now:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found or expired",
        )

    # Password validation if password path
    pwd_hash: Optional[str] = None
    if password:
        validate_password_policy(password, norm_email)
        pwd_hash = hash_password(password)

    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email=norm_email,
        display_name=display_name,
        avatar_url=avatar_url,
        platform_role=invite.platform_role,
        status="active",
        password_hash=pwd_hash,
        password_updated_at=now if pwd_hash else None,
        approved_by=invite.invited_by,
        approved_at=now,
        created_at=now,
        last_login=now,
    )
    db.add(user)
    await db.flush()

    identity = UserIdentity(
        id=str(uuid.uuid4()),
        user_id=user.id,
        provider=provider,
        provider_id=provider_id or user.id,
        email=norm_email,
        created_at=now,
        last_used_at=now,
    )
    db.add(identity)

    # Add HubMembers
    grants = invite.hub_grants_json or []
    for grant in grants:
        h_id = grant.get("hub_id")
        h_role = grant.get("hub_role")
        if h_id and h_role:
            h_obj = await db.get(Hub, h_id)
            if h_obj and not h_obj.is_archived:
                member = HubMember(
                    id=str(uuid.uuid4()),
                    hub_id=h_id,
                    user_id=user.id,
                    hub_role=h_role,
                    created_at=now,
                )
                db.add(member)

    invite.status = "accepted"
    invite.accepted_at = now
    invite.accepted_user_id = user.id

    audit = AuditLog(
        id=str(uuid.uuid4()),
        actor_user_id=user.id,
        action="create",
        resource_type="user",
        resource_id=user.id,
        summary=f"Redeemed invite {invite.id}",
        ip_address=ip_address,
        created_at=now,
    )
    db.add(audit)

    await db.commit()
    await db.refresh(user)
    return user


async def resend_invite(
    db: AsyncSession,
    invite_id: str,
    actor_id: str,
) -> InviteResult:
    """Resend an existing pending invite with a rotated token and extended TTL."""
    invite = await db.get(UserInvite, invite_id)
    if not invite or invite.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending invite not found",
        )

    raw_token, token_h = generate_invite_token()
    settings = get_settings()
    ttl = getattr(settings, "INVITE_TTL_HOURS", 72)
    now = datetime.now(timezone.utc)

    invite.token_hash = token_h
    invite.expires_at = now + timedelta(hours=ttl)
    invite.resend_count = (invite.resend_count or 0) + 1
    invite.last_sent_at = now

    audit = AuditLog(
        id=str(uuid.uuid4()),
        actor_user_id=actor_id,
        action="update",
        resource_type="invite",
        resource_id=invite.id,
        summary=f"Resent invite to {invite.email}",
        created_at=now,
    )
    db.add(audit)
    await db.commit()

    public_url = getattr(settings, "APP_PUBLIC_URL", "http://localhost:5173")
    invite_url = f"{public_url}/auth/invite/{raw_token}"

    return InviteResult(
        email=invite.email,
        status="resent",
        invite_id=invite.id,
        delivered=False,
        invite_url=invite_url,
    )


async def revoke_invite(
    db: AsyncSession,
    invite_id: str,
    actor_id: str,
) -> None:
    """Revoke an active invite link."""
    invite = await db.get(UserInvite, invite_id)
    if not invite or invite.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending invite not found",
        )

    now = datetime.now(timezone.utc)
    invite.status = "revoked"

    audit = AuditLog(
        id=str(uuid.uuid4()),
        actor_user_id=actor_id,
        action="delete",
        resource_type="invite",
        resource_id=invite.id,
        summary=f"Revoked invite for {invite.email}",
        created_at=now,
    )
    db.add(audit)
    await db.commit()


async def sweep_expired_invites(db: AsyncSession) -> int:
    """Background task to transition past-due pending invites to expired."""
    now = datetime.now(timezone.utc)
    stmt = select(UserInvite).where(
        UserInvite.status == "pending",
        UserInvite.expires_at < now,
    )
    res = await db.execute(stmt)
    expired_invites = res.scalars().all()

    for invite in expired_invites:
        invite.status = "expired"

    if expired_invites:
        await db.commit()
        logger.info(f"Swept {len(expired_invites)} expired invites")

    return len(expired_invites)
