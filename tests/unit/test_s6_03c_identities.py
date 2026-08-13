
import pytest
pytestmark = pytest.mark.unit
"""Unit and integration tests for S6-03c Multi-Provider OAuth Linking & Approval Gate."""

import pytest
from datetime import datetime, timezone
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from common.clients.postgres import get_async_db
from common.config.settings import get_settings
from common.models.database import Base, User, UserIdentity
from gateway.auth.identities import (
    OAuthProfile,
    resolve_identity,
    gate_status,
)
from gateway.auth.providers import build_state, parse_state
from gateway.main import app

# Enable AUTH_ENABLED for test suite
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


def test_build_and_parse_state():
    """Test OAuth state signing and verification."""
    payload = {"invite_token": "inv_123", "redirect": "/dashboard"}
    state_token = build_state(payload)
    assert isinstance(state_token, str)

    decoded = parse_state(state_token)
    assert decoded["invite_token"] == "inv_123"
    assert decoded["redirect"] == "/dashboard"
    assert "nonce" in decoded

    # Invalid state raises 400
    with pytest.raises(HTTPException) as exc_info:
        parse_state("invalid.state.token")
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid OAuth state"


@pytest.mark.asyncio
async def test_resolve_identity_single_account_linking():
    """Test that Google and GitHub credentials with identical email link to ONE account."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as db:
        # Pre-seed an existing admin user to bypass bootstrap
        existing_user = User(
            id="user-100",
            email="shared@example.com",
            display_name="Existing User",
            platform_role="member",
            status="active",
            created_at=datetime.now(timezone.utc),
        )
        db.add(existing_user)
        await db.commit()

        # 1. Resolve Google Profile for shared@example.com
        google_profile = OAuthProfile(
            provider="google",
            provider_id="google-id-123",
            email="shared@example.com",
            email_verified=True,
            display_name="Shared User",
        )

        user1, is_new1 = await resolve_identity(db, google_profile)
        assert is_new1 is False
        assert user1.id == "user-100"

        # 2. Resolve GitHub Profile for shared@example.com
        github_profile = OAuthProfile(
            provider="github",
            provider_id="github-id-456",
            email="shared@example.com",
            email_verified=True,
            display_name="Shared User",
        )

        user2, is_new2 = await resolve_identity(db, github_profile)
        assert is_new2 is False
        assert user2.id == "user-100"

        # Verify two identity rows exist for the single user account
        id_stmt = select(UserIdentity).where(UserIdentity.user_id == "user-100")
        identities = (await db.execute(id_stmt)).scalars().all()
        assert len(identities) == 2
        providers = {i.provider for i in identities}
        assert providers == {"google", "github"}


@pytest.mark.asyncio
async def test_resolve_identity_approval_gate():
    """Test approval gate holding state for unsolicited sign-ups vs domain auto-approval."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


    async with TestingSessionLocal() as db:
        # First user is bootstrap admin
        admin_profile = OAuthProfile(
            provider="google",
            provider_id="admin-g-id",
            email="admin@contained.local",
            email_verified=True,
        )
        admin_user, _ = await resolve_identity(db, admin_profile)
        assert admin_user.status == "active"
        assert admin_user.platform_role == "admin"

        # Unsolicited sign-up without invite or domain match -> status="pending"
        unsolicited_profile = OAuthProfile(
            provider="google",
            provider_id="unsolicited-g-id",
            email="random@otherdomain.com",
            email_verified=True,
        )
        pending_user, _ = await resolve_identity(db, unsolicited_profile)
        assert pending_user.status == "pending"

        # Sign-up matching AUTO_APPROVE_EMAIL_DOMAINS ("example.com") -> status="active"
        auto_profile = OAuthProfile(
            provider="google",
            provider_id="auto-g-id",
            email="newuser@example.com",
            email_verified=True,
        )
        approved_user, _ = await resolve_identity(db, auto_profile)
        assert approved_user.status == "active"


def test_gate_status_enforcement():
    """Test gate_status helper raises 403 for non-active users."""
    active_user = User(id="1", email="a@example.com", status="active")
    gate_status(active_user)  # Should not raise

    pending_user = User(id="2", email="p@example.com", status="pending")
    with pytest.raises(HTTPException) as exc_info:
        gate_status(pending_user)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["reason"] == "ACCOUNT_PENDING_APPROVAL"

    suspended_user = User(id="3", email="s@example.com", status="suspended")
    with pytest.raises(HTTPException) as exc_info:
        gate_status(suspended_user)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["reason"] == "ACCOUNT_SUSPENDED"


def test_unlink_identity_flow():
    """Test identity unlinking endpoint and sole-identity protection constraint."""
    # Register and login password user
    email = "unlink_test@example.com"
    password = "SuperPassword123!"

    client.post("/auth/register", json={"email": email, "password": password})
    login_resp = client.post("/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Unlink password identity -> user has password_hash so unlinking provider identity works
    unlink_resp = client.post("/auth/identities/password/unlink", headers=headers)
    assert unlink_resp.status_code == 200
    assert unlink_resp.json() == {"status": "unlinked", "provider": "password"}

    # Unlinking again -> 404 target identity not found
    unlink_again = client.post("/auth/identities/password/unlink", headers=headers)
    assert unlink_again.status_code == 404
