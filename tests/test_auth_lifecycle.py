"""Integration test suite for Base Task 1: Auth & User Lifecycle Management.

Covers soft deletion schemas, self-service account deletion, admin soft/hard delete,
logout session revocation, and super admin/test user bootstrapping.
"""

import asyncio
from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import select

from common.clients.postgres import get_async_db
from common.config.settings import get_settings
from common.models.database import (
    Base,
    Hub,
    User,
    UserSession,
)
from common.observability.limiter import limiter
from gateway.auth.utils import create_access_token, hash_token
from gateway.main import app

settings = get_settings()

test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
TestingSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


async def override_get_async_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_async_db] = override_get_async_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db_state(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
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


def test_user_and_hub_soft_delete_attributes():
    """Verify that User and Hub models have is_deleted and deleted_at attributes."""
    u = User(email="test_sd@contained.ai", is_deleted=False)
    h = Hub(name="Test Hub", slug="test-hub", hub_type="ingestion", owner_id="some-owner-id", is_deleted=False)

    assert hasattr(u, "is_deleted")
    assert hasattr(u, "deleted_at")
    assert u.is_deleted is False
    assert u.deleted_at is None

    assert hasattr(h, "is_deleted")
    assert hasattr(h, "deleted_at")
    assert h.is_deleted is False
    assert h.deleted_at is None


def test_self_service_soft_delete():
    """Verify DELETE /auth/me soft-deletes user and revokes active session."""
    user_id = "user-sd-01"
    email = "user_sd@contained.ai"
    token = create_access_token(user_id=user_id, email=email, platform_role="member")
    token_h = hash_token(token)

    # Seed user and active session in test DB
    async def _seed():
        async with TestingSessionLocal() as db:
            u = User(
                id=user_id,
                email=email,
                platform_role="member",
                status="active",
                is_deleted=False,
            )
            sess = UserSession(
                id="sess-01",
                user_id=user_id,
                token_hash=token_h,
                expires_at=datetime.utcnow(),
            )
            db.add(u)
            db.add(sess)
            await db.commit()

    asyncio.run(_seed())

    headers = {"Authorization": f"Bearer {token}"}
    res = client.delete("/auth/me", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "soft_deleted"

    # Verify user is soft-deleted in DB
    async def _check_db():
        async with TestingSessionLocal() as db:
            u = await db.get(User, user_id)
            assert u.is_deleted is True
            assert u.deleted_at is not None
            # Check sessions revoked
            sess_res = await db.execute(select(UserSession).where(UserSession.user_id == user_id))
            assert len(sess_res.scalars().all()) == 0

    asyncio.run(_check_db())

    # Subsequent call with same token should be rejected
    res_after = client.get("/auth/me", headers=headers)
    assert res_after.status_code in (401, 403)


def test_logout_session_revocation():
    """Verify POST /auth/logout deletes active session and invalidates access token."""
    user_id = "user-logout-01"
    email = "logout_user@contained.ai"
    token = create_access_token(user_id=user_id, email=email, platform_role="member")
    token_h = hash_token(token)

    async def _seed():
        async with TestingSessionLocal() as db:
            u = User(id=user_id, email=email, platform_role="member", status="active", is_deleted=False)
            sess = UserSession(id="sess-logout", user_id=user_id, token_hash=token_h, expires_at=datetime.utcnow())
            db.add(u)
            db.add(sess)
            await db.commit()

    asyncio.run(_seed())

    headers = {"Authorization": f"Bearer {token}"}

    # Logout
    res = client.post("/auth/logout", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "logged_out"

    # Verify request using logged-out token returns 401 Unauthorized
    res_me = client.get("/auth/me", headers=headers)
    assert res_me.status_code == 401


def test_users_me_alias_soft_deletes_user_and_revokes_sessions():
    """Verify DELETE /users/me behaves like DELETE /auth/me for self-service account deletion."""
    user_id = "user-users-me-01"
    email = "users_me@contained.ai"
    token = create_access_token(user_id=user_id, email=email, platform_role="member")
    token_h = hash_token(token)

    async def _seed():
        async with TestingSessionLocal() as db:
            u = User(
                id=user_id,
                email=email,
                platform_role="member",
                status="active",
                is_deleted=False,
            )
            sess = UserSession(
                id="sess-users-me",
                user_id=user_id,
                token_hash=token_h,
                expires_at=datetime.utcnow(),
            )
            db.add_all([u, sess])
            await db.commit()

    asyncio.run(_seed())

    headers = {"Authorization": f"Bearer {token}"}
    res = client.delete("/users/me", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "soft_deleted"

    async def _check_db():
        async with TestingSessionLocal() as db:
            u = await db.get(User, user_id)
            assert u is not None
            assert u.is_deleted is True
            sess_res = await db.execute(select(UserSession).where(UserSession.user_id == user_id))
            assert len(sess_res.scalars().all()) == 0

    asyncio.run(_check_db())


def test_logout_clears_cookies_and_revokes_all_sessions():
    """Verify POST /auth/logout clears cookies and invalidates all active sessions for the user."""
    user_id = "user-logout-all-01"
    email = "logout_all@contained.ai"
    token = create_access_token(user_id=user_id, email=email, platform_role="member")
    token_h = hash_token(token)

    async def _seed():
        async with TestingSessionLocal() as db:
            u = User(id=user_id, email=email, platform_role="member", status="active", is_deleted=False)
            db.add(u)
            db.add_all([
                UserSession(id="sess-logout-1", user_id=user_id, token_hash=token_h, expires_at=datetime.utcnow()),
                UserSession(id="sess-logout-2", user_id=user_id, token_hash=hash_token("other-token"), expires_at=datetime.utcnow()),
            ])
            await db.commit()

    asyncio.run(_seed())

    headers = {"Authorization": f"Bearer {token}"}
    res = client.post("/auth/logout", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "logged_out"

    cookie_headers = res.headers.get_list("set-cookie")
    assert any("auth_token=" in header for header in cookie_headers)
    assert any("contained_session=" in header for header in cookie_headers)

    async def _check_db():
        async with TestingSessionLocal() as db:
            sess_res = await db.execute(select(UserSession).where(UserSession.user_id == user_id))
            assert len(sess_res.scalars().all()) == 0

    asyncio.run(_check_db())


def test_admin_soft_delete_and_hard_purge():
    """Verify DELETE /admin/users/{id} soft-deletes by default, and hard-purges when hard=true."""
    admin_id = "admin-user-id"
    admin_email = "admin@contained.ai"
    admin_token = create_access_token(user_id=admin_id, email=admin_email, platform_role="admin")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    target_id = "target-member-id"
    target_email = "target@contained.ai"

    async def _seed():
        async with TestingSessionLocal() as db:
            admin_u = User(id=admin_id, email=admin_email, platform_role="admin", status="active")
            admin_sess = UserSession(id="sess-admin", user_id=admin_id, token_hash=hash_token(admin_token), expires_at=datetime.utcnow())
            target_u = User(id=target_id, email=target_email, platform_role="member", status="active")
            db.add_all([admin_u, admin_sess, target_u])
            await db.commit()

    asyncio.run(_seed())

    # Step 1: Admin Soft Delete
    res_soft = client.delete(f"/admin/users/{target_id}", headers=admin_headers)
    assert res_soft.status_code == 200
    assert res_soft.json()["status"] in ("deleted", "soft_deleted")

    async def _check_soft():
        async with TestingSessionLocal() as db:
            u = await db.get(User, target_id)
            assert u is not None
            assert u.is_deleted is True

    asyncio.run(_check_soft())

    # Step 2: Admin Hard Delete
    res_hard = client.delete(f"/admin/users/{target_id}?hard=true", headers=admin_headers)
    assert res_hard.status_code == 204

    async def _check_hard():
        async with TestingSessionLocal() as db:
            u = await db.get(User, target_id)
            assert u is None

    asyncio.run(_check_hard())
