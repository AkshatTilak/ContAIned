"""Identity resolution, profile normalisation, and approval gate logic (S6-03c)."""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from common.config.settings import get_settings
from common.constants.roles import PLATFORM_ROLE_ADMIN, PLATFORM_ROLE_MEMBER
from common.models.database import User, UserIdentity, UserInvite, AuditLog
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("gateway.auth.identities")


@dataclass
class OAuthProfile:
    provider: str        # google | github
    provider_id: str
    email: str           # lowercased & trimmed
    email_verified: bool
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None


async def fetch_profile(provider: str, client: Any, token: Dict[str, Any]) -> OAuthProfile:
    """Fetch and normalise profile data from an OAuth provider."""
    if provider == "google":
        user_info = token.get("userinfo") or {}
        email = (user_info.get("email") or "").strip().lower()
        provider_id = str(user_info.get("sub") or "")
        email_verified = bool(user_info.get("email_verified", False))
        display_name = user_info.get("name")
        avatar_url = user_info.get("picture")

        if not email or not provider_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing email or provider ID from Google userinfo",
            )
        return OAuthProfile(
            provider="google",
            provider_id=provider_id,
            email=email,
            email_verified=email_verified,
            display_name=display_name,
            avatar_url=avatar_url,
        )

    elif provider == "github":
        resp = await client.get("user", token=token)
        gh_data = resp.json() if hasattr(resp, "json") else resp
        provider_id = str(gh_data.get("id"))
        display_name = gh_data.get("name") or gh_data.get("login")
        avatar_url = gh_data.get("avatar_url")

        email = ""
        email_verified = False
        try:
            emails_resp = await client.get("user/emails", token=token)
            emails_data = emails_resp.json() if hasattr(emails_resp, "json") else emails_resp
            if isinstance(emails_data, list):
                for em in emails_data:
                    if em.get("primary") and em.get("verified"):
                        email = (em.get("email") or "").strip().lower()
                        email_verified = True
                        break
        except Exception as e:
            logger.warning(f"Failed to fetch GitHub user emails: {e}")

        if not email:
            raw_email = (gh_data.get("email") or "").strip().lower()
            if raw_email:
                email = raw_email
                email_verified = False

        if not email or not provider_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing primary verified email from GitHub account",
            )

        return OAuthProfile(
            provider="github",
            provider_id=provider_id,
            email=email,
            email_verified=email_verified,
            display_name=display_name,
            avatar_url=avatar_url,
        )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported OAuth provider: {provider}",
        )


def gate_status(user: User) -> None:
    """Raises HTTPException(403) with machine-readable reason for non-active users."""
    if user.status != "active":
        reason_map = {
            "pending": "ACCOUNT_PENDING_APPROVAL",
            "suspended": "ACCOUNT_SUSPENDED",
            "rejected": "ACCOUNT_REJECTED",
        }
        reason_code = reason_map.get(user.status, "ACCOUNT_NOT_ACTIVE")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": reason_code, "status": user.status, "email": user.email},
        )


async def resolve_identity(
    db: AsyncSession,
    profile: OAuthProfile,
    invite_token: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> Tuple[User, bool]:
    """Resolve an incoming OAuthProfile to a unified User account.

    Returns (user, is_new_account).
    """
    now = datetime.now(timezone.utc)

    # 1. Match existing (provider, provider_id) in user_identities
    stmt = select(UserIdentity).where(
        UserIdentity.provider == profile.provider,
        UserIdentity.provider_id == profile.provider_id,
    )
    res = await db.execute(stmt)
    existing_id = res.scalar_one_or_none()

    if existing_id:
        existing_id.last_used_at = now
        user_stmt = select(User).where(User.id == existing_id.user_id)
        user_res = await db.execute(user_stmt)
        user = user_res.scalar_one_or_none()
        if user:
            if profile.display_name and not user.display_name:
                user.display_name = profile.display_name
            if profile.avatar_url and not user.avatar_url:
                user.avatar_url = profile.avatar_url
            await db.commit()
            return user, False

    # 2. Match existing user by verified email (Identity Link)
    email_stmt = select(User).where(User.email == profile.email)
    email_res = await db.execute(email_stmt)
    user_by_email = email_res.scalar_one_or_none()

    if user_by_email:
        new_identity = UserIdentity(
            id=str(uuid.uuid4()),
            user_id=user_by_email.id,
            provider=profile.provider,
            provider_id=profile.provider_id,
            email=profile.email,
            created_at=now,
            last_used_at=now,
        )
        db.add(new_identity)

        audit = AuditLog(
            id=str(uuid.uuid4()),
            actor_user_id=user_by_email.id,
            action="update",
            resource_type="user",
            resource_id=user_by_email.id,
            summary=f"Linked {profile.provider} identity",
            ip_address=ip_address,
            created_at=now,
        )
        db.add(audit)
        await db.commit()
        return user_by_email, False

    # 3. Check for pending invite matching email
    invite_stmt = select(UserInvite).where(
        UserInvite.email == profile.email,
        UserInvite.status == "pending",
    )
    invite_res = await db.execute(invite_stmt)
    invite = invite_res.scalar_one_or_none()

    settings = get_settings()

    # 4. Bootstrap check
    count_stmt = select(func.count(User.id))
    user_count = (await db.execute(count_stmt)).scalar() or 0

    if user_count == 0:
        initial_status = "active"
        initial_role = PLATFORM_ROLE_ADMIN
    elif invite:
        initial_status = "active"
        initial_role = invite.platform_role or PLATFORM_ROLE_MEMBER
        invite.status = "accepted"
        invite.accepted_at = now
    else:
        auto_domains = getattr(settings, "AUTO_APPROVE_EMAIL_DOMAINS", [])
        if isinstance(auto_domains, str):
            auto_domains = [d.strip().lower() for d in auto_domains.split(",") if d.strip()]

        domain = profile.email.split("@")[1] if "@" in profile.email else ""
        if domain and domain.lower() in [d.lower() for d in auto_domains]:
            initial_status = "active"
            initial_role = PLATFORM_ROLE_MEMBER
        else:
            initial_status = "pending"
            initial_role = PLATFORM_ROLE_MEMBER

    user = User(
        id=str(uuid.uuid4()),
        email=profile.email,
        display_name=profile.display_name,
        avatar_url=profile.avatar_url,
        platform_role=initial_role,
        status=initial_status,
        created_at=now,
        last_login=now if initial_status == "active" else None,
    )
    db.add(user)
    await db.flush()

    if invite:
        invite.accepted_user_id = user.id

    new_identity = UserIdentity(
        id=str(uuid.uuid4()),
        user_id=user.id,
        provider=profile.provider,
        provider_id=profile.provider_id,
        email=profile.email,
        created_at=now,
        last_used_at=now,
    )
    db.add(new_identity)

    audit_summary = "Created user account"
    if initial_status == "active" and not invite and user_count > 0:
        audit_summary = "User account created and auto-approved by domain rule"

    audit = AuditLog(
        id=str(uuid.uuid4()),
        actor_user_id=user.id,
        action="create" if initial_status == "pending" else "approve",
        resource_type="user",
        resource_id=user.id,
        summary=audit_summary,
        ip_address=ip_address,
        created_at=now,
    )
    db.add(audit)

    await db.commit()
    await db.refresh(user)

    return user, True
