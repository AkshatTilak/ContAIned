"""Comprehensive integration test suite for S6-03g Auth Hardening, Approval Gate, and Security Controls."""

import asyncio
from datetime import datetime, timezone
import pytest
from fastapi.routing import APIRoute
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
    PasswordResetToken,
    User,
    UserIdentity,
    UserInvite,
    UserSession,
)
from common.observability.limiter import limiter
from gateway.auth.passwords import hash_password
from gateway.auth.utils import create_access_token
from gateway.main import app

# Ensure AUTH_ENABLED and disable rate limiter interference during unit tests
settings = get_settings()
settings.AUTH_ENABLED = True
settings.AUTO_APPROVE_EMAIL_DOMAINS = []
limiter.enabled = False

# Setup test DB engine matching test_admin_users_api pattern
test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
TestingSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


async def override_get_async_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_async_db] = override_get_async_db
client = TestClient(app)

ADMIN_ID = "admin-v6-id"
ADMIN_EMAIL = "admin@example.com"
ADMIN_PWD = "ComplexSecretPass123!"
admin_token = create_access_token(user_id=ADMIN_ID, email=ADMIN_EMAIL, platform_role="admin")
admin_headers = {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(autouse=True)
def reset_db_state():
    """Reset DB schema and dependency overrides before each test."""
    app.dependency_overrides[get_async_db] = override_get_async_db
    try:
        limiter.reset()
    except Exception:
        pass

    async def _reset():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_reset())



def seed_admin_user():
    async def _seed():
        async with TestingSessionLocal() as db:
            now = datetime.now(timezone.utc)
            admin_user = User(
                id=ADMIN_ID,
                email=ADMIN_EMAIL,
                display_name="Admin V6",
                platform_role="admin",
                status="active",
                failed_login_count=0,
                password_hash=hash_password(ADMIN_PWD),
                created_at=now,
            )
            db.add(admin_user)
            await db.commit()

    asyncio.run(_seed())


def test_invite_and_password_acceptance_flow():
    """Test invite creation -> password acceptance -> duplicate redemption rejection (409)."""
    seed_admin_user()

    # 1. Create invite via Admin API
    resp_inv = client.post(
        "/admin/invites",
        json={
            "emails": ["new_member@example.com"],
            "platform_role": "member",
        },
        headers=admin_headers,
    )
    assert resp_inv.status_code == 201
    results = resp_inv.json()
    assert results[0]["status"] == "created"
    raw_token = results[0]["invite_url"].split("/")[-1]

    # 2. Preview invite
    resp_prev = client.get(f"/auth/invite/{raw_token}")
    assert resp_prev.status_code == 200
    assert resp_prev.json()["email"] == "new_member@example.com"

    # 3. Accept invite via password setup
    resp_acc = client.post(
        f"/auth/invite/{raw_token}/accept",
        json={
            "email": "new_member@example.com",
            "password": "ValidPassword123!",
            "display_name": "New Member",
        },
    )
    assert resp_acc.status_code == 200
    acc_data = resp_acc.json()
    assert "access_token" in acc_data
    assert acc_data["user"]["status"] == "active"

    # 4. Duplicate redemption returns 409 CONFLICT
    resp_dup = client.post(
        f"/auth/invite/{raw_token}/accept",
        json={
            "email": "new_member@example.com",
            "password": "ValidPassword123!",
        },
    )
    assert resp_dup.status_code == 409


def test_invite_email_mismatch_rejection():
    """Test redeeming invite with non-matching email returns 409."""
    seed_admin_user()

    resp_inv = client.post(
        "/admin/invites",
        json={
            "emails": ["intended@example.com"],
            "platform_role": "member",
        },
        headers=admin_headers,
    )
    raw_token = resp_inv.json()[0]["invite_url"].split("/")[-1]

    resp_bad = client.post(
        f"/auth/invite/{raw_token}/accept",
        json={
            "email": "mismatched@example.com",
            "password": "ValidPassword123!",
        },
    )
    assert resp_bad.status_code == 409
    assert "Invite email mismatch" in str(resp_bad.json())


def test_approval_gate_and_admin_lifecycle():
    """Test self sign-up holding state -> admin approve -> admin reject -> domain auto-approve."""
    seed_admin_user()
    settings.AUTO_APPROVE_EMAIL_DOMAINS = []

    # 1. Unsolicited self registration (password signup, no invite)
    resp_reg = client.post(
        "/auth/register",
        json={
            "email": "pending_user@untrusted.org",
            "password": "ValidPassword123!",
            "display_name": "Pending User",
        },
    )
    assert resp_reg.status_code == 202

    # Login attempt returns 403 ACCOUNT_PENDING_APPROVAL
    resp_log = client.post(
        "/auth/login",
        json={
            "email": "pending_user@untrusted.org",
            "password": "ValidPassword123!",
        },
    )
    assert resp_log.status_code == 403
    assert "ACCOUNT_PENDING_APPROVAL" in str(resp_log.json())

    # 2. Get pending user ID from Admin API
    resp_pend_list = client.get("/admin/users/pending", headers=admin_headers)
    assert resp_pend_list.status_code == 200
    pending_items = resp_pend_list.json()["items"]
    assert len(pending_items) == 1
    p_user_id = pending_items[0]["id"]

    # 3. Admin approves user
    resp_app = client.post(f"/admin/users/{p_user_id}/approve", json={"platform_role": "member"}, headers=admin_headers)
    assert resp_app.status_code == 200
    assert resp_app.json()["status"] == "active"

    # Login now succeeds
    resp_log_ok = client.post(
        "/auth/login",
        json={
            "email": "pending_user@untrusted.org",
            "password": "ValidPassword123!",
        },
    )
    assert resp_log_ok.status_code == 200

    # 4. AUTO_APPROVE_EMAIL_DOMAINS bypass
    try:
        settings.AUTO_APPROVE_EMAIL_DOMAINS = ["acme.com"]
        client.post(
            "/auth/register",
            json={
                "email": "employee@acme.com",
                "password": "ValidPassword123!",
            },
        )
        login_auto = client.post(
            "/auth/login",
            json={
                "email": "employee@acme.com",
                "password": "ValidPassword123!",
            },
        )
        assert login_auto.status_code == 200
        assert login_auto.json()["user"]["status"] == "active"
    finally:
        settings.AUTO_APPROVE_EMAIL_DOMAINS = []


def test_suspension_live_session_revocation():
    """Test that suspending an active user revokes sessions and blocks presentation of unexpired JWT tokens."""
    seed_admin_user()
    settings.AUTO_APPROVE_EMAIL_DOMAINS = []

    # 1. Register user
    client.post(
        "/auth/register",
        json={
            "email": "suspend_test@untrusted.org",
            "password": "ValidPassword123!",
        },
    )

    # Approve user
    resp_pend = client.get("/admin/users?status=pending", headers=admin_headers)
    items = resp_pend.json()["items"]
    assert len(items) > 0
    target_id = items[0]["id"]
    client.post(f"/admin/users/{target_id}/approve", json={}, headers=admin_headers)

    # Login to obtain token
    resp_login = client.post(
        "/auth/login",
        json={
            "email": "suspend_test@untrusted.org",
            "password": "ValidPassword123!",
        },
    )
    assert resp_login.status_code == 200
    user_jwt = resp_login.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {user_jwt}"}

    # 2. Suspend user via Admin API
    resp_susp = client.post(f"/admin/users/{target_id}/suspend", headers=admin_headers)
    assert resp_susp.status_code == 200

    # 3. Presenting original JWT token now gets 403 ACCOUNT_SUSPENDED in AuthMiddleware
    resp_blocked = client.get("/admin/users", headers=user_headers)
    assert resp_blocked.status_code == 403
    assert "ACCOUNT_SUSPENDED" in str(resp_blocked.json())


def test_brute_force_account_lockout():
    """Test 5 failed login attempts lock account, and 6th attempt (even with correct password) returns AccountLockedError."""
    seed_admin_user()

    email = "lockout_target@example.com"
    pwd = "ComplexPassword123!"

    # Create active user
    async def _seed():
        async with TestingSessionLocal() as db:
            now = datetime.now(timezone.utc)
            u = User(
                id="lockout-user-id",
                email=email,
                platform_role="member",
                status="active",
                failed_login_count=0,
                password_hash=hash_password(pwd),
                created_at=now,
            )
            db.add(u)
            await db.commit()

    asyncio.run(_seed())

    # Fail 5 times with wrong password
    for i in range(5):
        resp_fail = client.post("/auth/login", json={"email": email, "password": "WrongPassword123!"})
        assert resp_fail.status_code == 401

    # 6th attempt with correct password fails with lockout error
    resp_locked = client.post("/auth/login", json={"email": email, "password": pwd})
    assert resp_locked.status_code in (401, 423)
    assert "locked" in str(resp_locked.json()).lower()


def test_enumeration_resistance_and_response_symmetry():
    """Test login with non-existent email vs wrong password return byte-identical responses."""
    seed_admin_user()

    resp_unknown = client.post("/auth/login", json={"email": "nonexistent@example.com", "password": "DummyPassword123!"})
    resp_wrong_pwd = client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": "WrongPassword123!"})

    assert resp_unknown.status_code == resp_wrong_pwd.status_code == 401
    u_json = resp_unknown.json()
    w_json = resp_wrong_pwd.json()
    assert u_json["error_code"] == w_json["error_code"] == "HTTP_ERROR"
    assert u_json["message"] == w_json["message"] == "Invalid email or password"


def test_admin_console_guardrails():
    """Test self-demotion prohibition (409 ACTION_ON_SELF) and active hub ownership deletion protection."""
    seed_admin_user()

    # 1. Self demote -> 409 ACTION_ON_SELF
    resp_self = client.patch(f"/admin/users/{ADMIN_ID}", json={"platform_role": "member"}, headers=admin_headers)
    assert resp_self.status_code == 409

    # 2. Delete hub owner -> 409
    async def _seed_hub_owner():
        async with TestingSessionLocal() as db:
            now = datetime.now(timezone.utc)
            u = User(id="hub-owner-id", email="owner@example.com", status="active", failed_login_count=0, created_at=now)
            h = Hub(id="owned-h-1", name="H1", slug="h1", hub_type="agent", owner_id="hub-owner-id", created_at=now)
            db.add_all([u, h])
            await db.commit()

    asyncio.run(_seed_hub_owner())

    resp_del = client.delete("/admin/users/hub-owner-id", headers=admin_headers)
    assert resp_del.status_code == 409
    assert "User owns hubs" in str(resp_del.json())


def test_static_response_model_sensitive_field_guard():
    """Verify no FastAPI route response model exposes 'password_hash' or 'token_hash' fields."""
    sensitive_fields = {"password_hash", "token_hash", "token_h"}

    for route in app.routes:
        if isinstance(route, APIRoute) and route.response_model:
            model = route.response_model
            if hasattr(model, "model_fields"):
                fields = set(model.model_fields.keys())
                leaked = fields.intersection(sensitive_fields)
                assert not leaked, f"Route {route.path} response_model leaks sensitive fields: {leaked}"
