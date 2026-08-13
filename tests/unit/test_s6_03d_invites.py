
import pytest
pytestmark = pytest.mark.unit
"""Unit and integration tests for S6-03d Invite Issuance & Redemption Service."""

import pytest
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from common.clients.postgres import get_async_db
from common.config.settings import get_settings
from common.models.database import Base, Hub, HubMember, User, UserInvite
from gateway.auth.invites import (
    create_invites,
    generate_invite_token,
    get_invite_preview,
    redeem_invite,
    resend_invite,
    revoke_invite,
    sweep_expired_invites,
    token_matches,
)
from gateway.main import app

get_settings().AUTH_ENABLED = True

test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
TestingSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


async def override_get_async_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_async_db] = override_get_async_db
client = TestClient(app)


def test_invite_token_primitives():
    """Test raw token generation and constant-time match verification."""
    raw, token_h = generate_invite_token()
    assert isinstance(raw, str)
    assert len(raw) > 20
    assert token_matches(raw, token_h) is True
    assert token_matches("wrong_raw_token", token_h) is False


@pytest.mark.asyncio
async def test_create_and_preview_invite():
    """Test invite creation with hub grants and unauthenticated preview."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as db:
        admin = User(
            id="admin-1",
            email="admin@example.com",
            display_name="Admin User",
            platform_role="admin",
            status="active",
        )
        hub = Hub(
            id="hub-10",
            slug="research-hub",
            name="Research Hub",
            hub_type="ingestion",
            owner_id="admin-1",
            is_archived=False,
        )
        db.add_all([admin, hub])
        await db.commit()


        # Create invite with hub grants
        results = await create_invites(
            db,
            emails=["invited@example.com"],
            platform_role="member",
            hub_grants=[{"hub_id": "hub-10", "hub_role": "maintainer"}],
            invited_by="admin-1",
        )
        assert len(results) == 1
        assert results[0].status == "created"
        assert results[0].invite_url is not None

        raw_token = results[0].invite_url.split("/")[-1]

        # Preview invite
        preview = await get_invite_preview(db, raw_token)
        assert preview.email == "invited@example.com"
        assert preview.inviter_display_name == "Admin User"
        assert preview.platform_role == "member"
        assert len(preview.hubs) == 1
        assert preview.hubs[0].id == "hub-10"
        assert preview.hubs[0].hub_role == "maintainer"


@pytest.mark.asyncio
async def test_redeem_invite_flow():
    """Test invite redemption creating active user, identity, and HubMember rows."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as db:
        admin = User(
            id="admin-1",
            email="admin@example.com",
            display_name="Admin User",
            platform_role="admin",
            status="active",
        )
        hub = Hub(
            id="hub-20",
            slug="workflow-hub",
            name="Workflow Hub",
            hub_type="workflow",
            owner_id="admin-1",
            is_archived=False,
        )
        db.add_all([admin, hub])
        await db.commit()


        results = await create_invites(
            db,
            emails=["new_member@example.com"],
            platform_role="member",
            hub_grants=[{"hub_id": "hub-20", "hub_role": "contributor"}],
            invited_by="admin-1",
        )
        raw_token = results[0].invite_url.split("/")[-1]

        # Redeem invite
        user = await redeem_invite(
            db,
            raw_token=raw_token,
            email="new_member@example.com",
            provider="password",
            provider_id="",
            password="SuperPassword123!",
            display_name="New Member",
        )

        assert user.status == "active"
        assert user.platform_role == "member"

        # Verify HubMember row created
        hm_stmt = select(HubMember).where(HubMember.user_id == user.id, HubMember.hub_id == "hub-20")
        hm_res = await db.execute(hm_stmt)
        hm = hm_res.scalar_one_or_none()
        assert hm is not None
        assert hm.hub_role == "contributor"


@pytest.mark.asyncio
async def test_redeem_email_mismatch():
    """Test redemption attempt with mismatched email fails with 409 Conflict."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as db:
        admin = User(id="admin-1", email="admin@example.com", platform_role="admin", status="active")
        db.add(admin)
        await db.commit()

        results = await create_invites(db, emails=["expected@example.com"], invited_by="admin-1")
        raw_token = results[0].invite_url.split("/")[-1]

        with pytest.raises(HTTPException) as exc_info:
            await redeem_invite(
                db,
                raw_token=raw_token,
                email="different@example.com",
                provider="password",
                provider_id="",
                password="SuperPassword123!",
            )
        assert exc_info.value.status_code == 409
        assert "email mismatch" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_resend_revoke_and_sweep():
    """Test resending, revoking, and sweeping expired invites."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as db:
        admin = User(id="admin-1", email="admin@example.com", platform_role="admin", status="active")
        db.add(admin)
        await db.commit()

        res1 = await create_invites(db, emails=["resend@example.com", "expire@example.com"], invited_by="admin-1")
        invite_id_1 = res1[0].invite_id
        invite_id_2 = res1[1].invite_id

        # Resend invite 1
        resend_res = await resend_invite(db, invite_id_1, actor_id="admin-1")
        assert resend_res.status == "resent"

        # Revoke invite 1
        await revoke_invite(db, invite_id_1, actor_id="admin-1")
        inv1 = await db.get(UserInvite, invite_id_1)
        assert inv1.status == "revoked"

        # Manually backdate invite 2 to test sweeper
        inv2 = await db.get(UserInvite, invite_id_2)
        inv2.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        await db.commit()

        swept_count = await sweep_expired_invites(db)
        assert swept_count == 1

        await db.refresh(inv2)
        assert inv2.status == "expired"


def test_public_invite_api_routes():
    """Test HTTP GET /auth/invite/{token} and POST /auth/invite/{token}/accept."""
    # Seed admin user & invite directly
    admin = User(id="admin-api", email="admin.api@example.com", platform_role="admin", status="active")
    raw_token, token_h = generate_invite_token()

    now = datetime.now(timezone.utc)
    invite = UserInvite(
        id="inv-api-1",
        email="api_invitee@example.com",
        token_hash=token_h,
        invited_by="admin-api",
        platform_role="member",
        hub_grants_json=[],
        status="pending",
        expires_at=now + timedelta(hours=24),
        created_at=now,
    )

    # In HTTP route test client:
    # 1. Preview
    # Create DB records via test_engine
    import asyncio
    async def seed():
        async with TestingSessionLocal() as db:
            db.add_all([admin, invite])
            await db.commit()

    asyncio.run(seed())

    prev_resp = client.get(f"/auth/invite/{raw_token}")
    assert prev_resp.status_code == 200
    prev_data = prev_resp.json()
    assert prev_data["email"] == "api_invitee@example.com"
    assert prev_data["platform_role"] == "member"

    # 2. Accept
    accept_resp = client.post(
        f"/auth/invite/{raw_token}/accept",
        json={
            "email": "api_invitee@example.com",
            "password": "SuperPassword123!",
            "display_name": "API Invitee",
        },
    )
    assert accept_resp.status_code == 200
    acc_data = accept_resp.json()
    assert "access_token" in acc_data
    assert acc_data["user"]["email"] == "api_invitee@example.com"
    assert acc_data["user"]["status"] == "active"
