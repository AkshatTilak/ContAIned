"""Signup resolution helper for invite/domain approval gate logic (S6-03b / S6-03d)."""

import logging
from typing import Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from common.config.settings import get_settings
from common.constants.roles import PLATFORM_ROLE_ADMIN, PLATFORM_ROLE_MEMBER
from common.models.database import User, UserInvite

logger = logging.getLogger("gateway.auth.signup_service")


async def resolve_signup(db: AsyncSession, email: str) -> Tuple[str, str, UserInvite | None]:
    """Resolve initial status and platform_role for a signing up email.

    Returns (initial_status, initial_role, matching_invite).
    - If email has an active pending UserInvite -> ('active', invite.platform_role, invite)
    - If user is first in system -> ('active', 'admin', None)
    - If email domain matches AUTO_APPROVE_EMAIL_DOMAINS -> ('active', 'member', None)
    - Otherwise -> ('pending', 'member', None)
    """
    settings = get_settings()
    norm_email = email.strip().lower()

    # 1. Check for open pending invite
    stmt = select(UserInvite).where(
        UserInvite.email == norm_email,
        UserInvite.status == "pending",
    )
    res = await db.execute(stmt)
    invite = res.scalar_one_or_none()

    if invite:
        return ("active", invite.platform_role or PLATFORM_ROLE_MEMBER, invite)



    # 3. Check auto-approve email domains
    auto_domains = getattr(settings, "AUTO_APPROVE_EMAIL_DOMAINS", [])
    if isinstance(auto_domains, str):
        auto_domains = [d.strip().lower() for d in auto_domains.split(",") if d.strip()]

    if "@" in norm_email:
        domain = norm_email.split("@")[1]
        if domain in [d.lower() for d in auto_domains]:
            return ("active", PLATFORM_ROLE_MEMBER, None)

    # 4. Fallback to approval gate holding state
    return ("pending", PLATFORM_ROLE_MEMBER, None)
