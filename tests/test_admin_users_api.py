"""Integration tests for S6-03f Admin Users, Invites & Audit API."""

import pytest
import asyncio
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from common.clients.postgres import get_async_db
from common.config.settings import get_settings
from common.models.database import (
    AuditLog,
    Base,
    Hub,
    HubMember,
    User,
    UserIdentity,
    UserInvite,
    UserSession,
)
from gateway.auth.utils import create_access_token
from gateway.main import app

# Ensure AUTH_ENABLED
get_settings().AUTH_ENABLED = True

# Setup test DB engine
test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
TestingSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

# Helper headers
admin_token = create_access_token(user_id="admin-actor-id", email="admin@contained.local", platform_role="admin")
admin_headers = {"Authorization": f"Bearer {admin_token}"}

member_token = create_access_token(user_id="member-actor-id", email="member@contained.local", platform_role="member")
member_headers = {"Authorization": f"Bearer {member_token}"}


async def override_get_async_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_async_db] = override_get_async_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db_state():
    """Reset database and actor state between tests."""
    app.dependency_overrides[get_async_db] = override_get_async_db
    async def _reset():

        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        # Seed default admin user
        async with TestingSessionLocal() as db:
            now = datetime.now(timezone.utc)
            admin_user = User(
                id="admin-actor-id",
                email="admin@contained.local",
                display_name="Admin Actor",
                platform_role="admin",
                status="active",
                created_at=now,
            )
            db.add(admin_user)
            await db.commit()

    asyncio.run(_reset())


def test_require_platform_admin_authorization():
    """Non-admin user should be blocked from /admin routes with 403."""
    resp = client.get("/admin/users", headers=member_headers)
    assert "Insufficient platform permissions" in (resp.json().get("message") or resp.json().get("detail") or "")



def test_list_and_pending_users():
    """Test user listing, search, status filtering, and pending badge API."""
    async def _seed():
        async with TestingSessionLocal() as db:
            now = datetime.now(timezone.utc)
            u1 = User(
                id="user-pending-1",
                email="pending1@example.com",
                display_name="Pending One",
                platform_role="member",
                status="pending",
                created_at=now,
            )
            u2 = User(
                id="user-active-1",
                email="active1@example.com",
                display_name="Active One",
                platform_role="member",
                status="active",
                created_at=now,
            )
            db.add_all([u1, u2])
            await db.commit()

    asyncio.run(_seed())

    # GET /admin/users
    resp = client.get("/admin/users", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3  # admin + 2 seeded
    assert len(data["items"]) == 3

    # Filter by status=pending
    resp_pending = client.get("/admin/users?status=pending", headers=admin_headers)
    assert resp_pending.status_code == 200
    assert resp_pending.json()["total"] == 1
    assert resp_pending.json()["items"][0]["email"] == "pending1@example.com"

    # Free text search q=Active
    resp_q = client.get("/admin/users?q=Active", headers=admin_headers)
    assert resp_q.status_code == 200
    assert resp_q.json()["total"] == 1
    assert resp_q.json()["items"][0]["email"] == "active1@example.com"

    # GET /admin/users/pending (sidebar badge endpoint)
    resp_badge = client.get("/admin/users/pending", headers=admin_headers)
    assert resp_badge.status_code == 200
    badge_data = resp_badge.json()
    assert badge_data["count"] == 1
    assert len(badge_data["items"]) == 1


def test_user_detail_endpoint():
    """Test fetching detailed user profile including identities, memberships, and audit log history."""
    async def _seed():
        async with TestingSessionLocal() as db:
            now = datetime.now(timezone.utc)
            u = User(
                id="target-user-id",
                email="target@example.com",
                display_name="Target User",
                platform_role="member",
                status="active",
                created_at=now,
            )
            identity = UserIdentity(
                id="id-1",
                user_id="target-user-id",
                provider="google",
                provider_id="g-123",
                email="target@example.com",
                created_at=now,
            )
            hub = Hub(
                id="hub-1",
                name="Test Hub",
                slug="test-hub",
                hub_type="agent",
                owner_id="admin-actor-id",
                created_at=now,
            )
            hm = HubMember(
                id="hm-1",
                hub_id="hub-1",
                user_id="target-user-id",
                hub_role="contributor",
                created_at=now,
            )
            audit = AuditLog(
                id="aud-1",
                actor_user_id="target-user-id",
                action="update",
                resource_type="user",
                resource_id="target-user-id",
                summary="User profile update",
                created_at=now,
            )
            db.add_all([u, identity, hub, hm, audit])
            await db.commit()

    asyncio.run(_seed())

    resp = client.get("/admin/users/target-user-id", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "target-user-id"
    assert len(data["identities"]) == 1
    assert data["identities"][0]["provider"] == "google"
    assert len(data["hub_memberships"]) == 1
    assert data["hub_memberships"][0]["hub_name"] == "Test Hub"
    assert len(data["recent_audit_logs"]) == 1


def test_user_update_and_guardrails():
    """Test PATCH /admin/users/{id} and admin demotion / last-admin / self-action guardrails."""
    async def _seed():
        async with TestingSessionLocal() as db:
            now = datetime.now(timezone.utc)
            admin2 = User(
                id="admin2-id",
                email="admin2@example.com",
                display_name="Admin Two",
                platform_role="admin",
                status="active",
                created_at=now,
            )
            sess = UserSession(
                id="sess-1",
                user_id="admin2-id",
                token_hash="hash123",
                expires_at=now,
                created_at=now,
            )
            db.add_all([admin2, sess])
            await db.commit()

    asyncio.run(_seed())

    # 1. Self demotion attempt on current logged in admin -> 409 ACTION_ON_SELF
    resp_self = client.patch("/admin/users/admin-actor-id", json={"platform_role": "member"}, headers=admin_headers)
    assert resp_self.status_code == 409
    assert resp_self.headers.get("X-Error-Code") == "ACTION_ON_SELF"

    # 2. Demote admin2 -> member (succeeds since admin-actor-id remains active admin)
    resp_demote = client.patch("/admin/users/admin2-id", json={"platform_role": "member"}, headers=admin_headers)
    assert resp_demote.status_code == 200
    assert resp_demote.json()["platform_role"] == "member"

    # Verify session for demoted admin was deleted
    async def _check_sess():
        async with TestingSessionLocal() as db:
            res = await db.execute(select(UserSession).where(UserSession.user_id == "admin2-id"))
            assert res.scalar_one_or_none() is None

    asyncio.run(_check_sess())

    # 3. Attempting to demote admin-actor-id now when no other active admin exists -> 409 ACTION_ON_SELF (or LAST_ACTIVE_ADMIN)
    resp_last = client.patch("/admin/users/admin-actor-id", json={"platform_role": "member"}, headers=admin_headers)
    assert resp_last.status_code == 409


def test_user_approval_workflow():
    """Test approval gate transitions: approve, reject, suspend, reinstate."""
    async def _seed():
        async with TestingSessionLocal() as db:
            now = datetime.now(timezone.utc)
            p_user = User(
                id="pending-user-id",
                email="newbie@example.com",
                display_name="Newbie",
                platform_role="member",
                status="pending",
                created_at=now,
            )
            hub = Hub(
                id="hub-approve-1",
                name="Approve Hub",
                slug="approve-hub",
                hub_type="ingestion",
                owner_id="admin-actor-id",
                created_at=now,
            )
            db.add_all([p_user, hub])
            await db.commit()

    asyncio.run(_seed())

    # Approve pending user with hub grants
    resp_app = client.post(
        "/admin/users/pending-user-id/approve",
        json={
            "platform_role": "member",
            "hub_grants": [{"hub_id": "hub-approve-1", "hub_role": "contributor"}],
        },
        headers=admin_headers,
    )
    assert resp_app.status_code == 200
    data_app = resp_app.json()
    assert data_app["status"] == "active"
    assert data_app["approved_by"] == "admin-actor-id"
    assert len(data_app["hub_memberships"]) == 1

    # Approving already active user returns 409
    resp_dup_app = client.post("/admin/users/pending-user-id/approve", json={}, headers=admin_headers)
    assert resp_dup_app.status_code == 409

    # Suspend user
    resp_susp = client.post("/admin/users/pending-user-id/suspend", headers=admin_headers)
    assert resp_susp.status_code == 200
    assert resp_susp.json()["status"] == "suspended"

    # Reinstate user
    resp_rein = client.post("/admin/users/pending-user-id/reinstate", headers=admin_headers)
    assert resp_rein.status_code == 200
    assert resp_rein.json()["status"] == "active"


def test_reject_user_workflow():
    """Test rejecting a pending user."""
    async def _seed():
        async with TestingSessionLocal() as db:
            now = datetime.now(timezone.utc)
            u = User(
                id="reject-target-id",
                email="rejected@example.com",
                platform_role="member",
                status="pending",
                created_at=now,
            )
            db.add(u)
            await db.commit()

    asyncio.run(_seed())

    resp = client.post("/admin/users/reject-target-id/reject", json={"reason": "Domain not permitted"}, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


def test_delete_user_and_hub_ownership_guardrail():
    """Test DELETE /admin/users/{id} and ownership blocking."""
    async def _seed():
        async with TestingSessionLocal() as db:
            now = datetime.now(timezone.utc)
            owner = User(
                id="owner-user-id",
                email="owner@example.com",
                platform_role="member",
                status="active",
                created_at=now,
            )
            hub = Hub(
                id="hub-owned-1",
                name="Owned Hub",
                slug="owned-hub",
                hub_type="agent",
                owner_id="owner-user-id",
                created_at=now,
            )
            db.add_all([owner, hub])
            await db.commit()

    asyncio.run(_seed())

    # Attempt delete user owning hub -> 409 CONFLICT
    resp_del_blocked = client.delete("/admin/users/owner-user-id", headers=admin_headers)
    assert resp_del_blocked.status_code == 409

    err_str = str(resp_del_blocked.json())
    assert "User owns hubs" in err_str


    # Archive or transfer hub ownership, then delete succeeds
    async def _unown():
        async with TestingSessionLocal() as db:
            h = await db.get(Hub, "hub-owned-1")
            h.is_archived = True
            await db.commit()

    asyncio.run(_unown())

    resp_del_ok = client.delete("/admin/users/owner-user-id", headers=admin_headers)
    assert resp_del_ok.status_code == 200
    assert resp_del_ok.json()["status"] == "deleted"


def test_invite_management_routes():
    """Test POST /admin/invites, GET /admin/invites, resend, and revoke."""
    # 1. Issue invite
    resp_create = client.post(
        "/admin/invites",
        json={
            "emails": ["invited@example.com"],
            "platform_role": "member",
        },
        headers=admin_headers,
    )
    assert resp_create.status_code == 201
    results = resp_create.json()
    assert len(results) == 1
    assert results[0]["status"] == "created"
    invite_id = results[0]["invite_id"]
    assert invite_id is not None
    assert "invite_url" in results[0]

    # 2. List invites (verify token_hash is never exposed)
    resp_list = client.get("/admin/invites", headers=admin_headers)
    assert resp_list.status_code == 200
    inv_data = resp_list.json()
    assert inv_data["total"] == 1
    item = inv_data["items"][0]
    assert item["id"] == invite_id
    assert "token_hash" not in item

    # 3. Resend invite
    resp_resend = client.post(f"/admin/invites/{invite_id}/resend", headers=admin_headers)
    assert resp_resend.status_code == 200
    assert resp_resend.json()["status"] == "resent"

    # 4. Revoke invite
    resp_revoke = client.delete(f"/admin/invites/{invite_id}", headers=admin_headers)
    assert resp_revoke.status_code == 204


def test_admin_audit_log_querying():
    """Test GET /admin/audit filters and pagination."""
    async def _seed_audits():
        async with TestingSessionLocal() as db:
            now = datetime.now(timezone.utc)
            a1 = AuditLog(
                id="aud-log-1",
                actor_user_id="admin-actor-id",
                action="create",
                resource_type="invite",
                resource_id="inv-100",
                summary="Issued invite to test@example.com",
                created_at=now,
            )
            a2 = AuditLog(
                id="aud-log-2",
                actor_user_id="admin-actor-id",
                action="update",
                resource_type="user",
                resource_id="user-200",
                summary="Updated user role",
                created_at=now,
            )
            db.add_all([a1, a2])
            await db.commit()

    asyncio.run(_seed_audits())

    # Query all audit logs
    resp_all = client.get("/admin/audit", headers=admin_headers)
    assert resp_all.status_code == 200
    assert resp_all.json()["total"] == 2

    # Filter by resource_type=invite
    resp_filt = client.get("/admin/audit?resource_type=invite", headers=admin_headers)
    assert resp_filt.status_code == 200
    assert resp_filt.json()["total"] == 1
    assert resp_filt.json()["items"][0]["action"] == "create"
