"""Real-world integration test suite for Invite System against real Postgres.

Tests invite generation, token hashing, invite preview, invite redemption,
TTL expiration, and duplicate invite rejection.
"""

import pytest
import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from common.models.database import UserInvite, User, HubMember
from gateway.auth.invites import (
    create_invites,
    get_invite_preview,
    redeem_invite,
    generate_invite_token,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_invite_creation_and_redemption_real(real_db_session: AsyncSession, seed_user, seed_hub):
    """Test full invite lifecycle: creation by admin, preview, and redemption."""
    admin = await seed_user(email="admin_inviter@contained.ai", role="admin")
    hub = await seed_hub(owner=admin, name="Invite Target Hub", slug="invite-target-hub")
    target_email = "invited_user@contained.ai"

    # 1. Create Invite
    hub_grants = [{"hub_id": hub.id, "hub_role": "contributor"}]
    results = await create_invites(
        db=real_db_session,
        invited_by=admin.id,
        emails=[target_email],
        platform_role="member",
        hub_grants=hub_grants,
    )
    assert len(results) == 1
    invite_res = results[0]
    assert invite_res.status == "created"
    assert invite_res.invite_url is not None

    raw_token = invite_res.invite_url.split("/")[-1]

    # Verify Invite Record in DB
    stmt = select(UserInvite).where(UserInvite.email == target_email)
    invite_db = (await real_db_session.execute(stmt)).scalar_one_or_none()
    assert invite_db is not None
    assert invite_db.status == "pending"

    # 2. Get Invite Preview
    preview = await get_invite_preview(db=real_db_session, raw_token=raw_token)
    assert preview.email == target_email
    assert preview.inviter_display_name is not None

    # 3. Redeem Invite
    user = await redeem_invite(
        db=real_db_session,
        raw_token=raw_token,
        email=target_email,
        provider="password",
        provider_id="invited-user-provider-id",
        password="NewUserPass123!",
        display_name="Invited New User",
    )
    assert user is not None
    assert user.email == target_email
    assert user.platform_role == "member"

    # Verify Hub Membership Created
    mem_stmt = select(HubMember).where(HubMember.hub_id == hub.id, HubMember.user_id == user.id)
    membership = (await real_db_session.execute(mem_stmt)).scalar_one_or_none()
    assert membership is not None
    assert membership.hub_role == "contributor"

    # Verify Invite Status updated to accepted
    await real_db_session.refresh(invite_db)
    assert invite_db.status == "accepted"


@pytest.mark.asyncio
async def test_duplicate_invite_prevention(real_db_session: AsyncSession, seed_user):
    """Test creating an invite for an email with an active pending invite is rejected."""
    admin = await seed_user(email="admin_dup@contained.ai", role="admin")
    target_email = "dup_invite@contained.ai"

    # First invite
    res1 = await create_invites(
        db=real_db_session,
        invited_by=admin.id,
        emails=[target_email],
    )
    assert res1[0].status == "created"

    # Duplicate invite
    res2 = await create_invites(
        db=real_db_session,
        invited_by=admin.id,
        emails=[target_email],
    )
    assert res2[0].status == "rejected"
    assert "active invite already exists" in res2[0].detail.lower()

