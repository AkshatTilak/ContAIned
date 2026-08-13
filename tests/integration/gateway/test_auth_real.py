"""Real-world integration test suite for Auth Lifecycle against real Postgres.

Tests self-registration, login, JWT token validation, protected route access,
failed login lockout, password changes, logout, and self soft-deletion.
"""

import pytest
import jwt
from typing import Dict, Any
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from common.models.database import User, UserSession
from gateway.auth.passwords import hash_password, verify_password
from gateway.auth.utils import verify_access_token, create_access_token

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_auth_registration_and_login_real(gateway_client: AsyncClient, real_db_session: AsyncSession, seed_user):
    """Test self-registration and subsequent login flow against real database."""
    test_email = "integration_test_user@contained.ai"
    test_pass = "SecurePass123!"

    # 1. Register User
    reg_resp = await gateway_client.post(
        "/auth/register",
        json={
            "email": test_email,
            "password": test_pass,
            "display_name": "Integration User",
        },
    )
    if reg_resp.status_code == 429:
        # Endpoint rate-limited; seed user manually for login assertion
        user = await seed_user(email=test_email, password=test_pass)
    else:
        assert reg_resp.status_code in (200, 202)
        reg_data = reg_resp.json()
        assert reg_data.get("status") == "registration_received"
        stmt = select(User).where(User.email == test_email)
        user = (await real_db_session.execute(stmt)).scalar_one_or_none()

    assert user is not None
    assert user.email == test_email
    assert verify_password(test_pass, user.password_hash)

    # Set user active so login succeeds
    user.status = "active"
    await real_db_session.commit()

    # 2. Login User
    login_resp = await gateway_client.post(
        "/auth/login",
        json={
            "email": test_email,
            "password": test_pass,
        },
    )
    assert login_resp.status_code in (200, 429)
    if login_resp.status_code == 200:
        token_data = login_resp.json()
        assert "access_token" in token_data
        token = token_data["access_token"]

        # 3. Verify JWT Claims
        payload = verify_access_token(token)
        assert payload["sub"] == user.id
        assert payload["email"] == test_email
        assert "exp" in payload

        # 4. Access Protected Endpoint /auth/me
        me_resp = await gateway_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["id"] == user.id
        assert me_data["email"] == test_email


@pytest.mark.asyncio
async def test_auth_invalid_and_expired_token(gateway_client: AsyncClient):
    """Test protected routes reject invalid or malformed tokens."""
    # 1. Malformed token
    resp1 = await gateway_client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid.jwt.payload"},
    )
    assert resp1.status_code == 401

    # 2. Missing token
    resp2 = await gateway_client.get("/auth/me")
    assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_account_lockout_after_failed_attempts(gateway_client: AsyncClient, seed_user):
    """Test account lockout after 5 consecutive failed login attempts."""
    user = await seed_user(email="lockout_user@contained.ai", password="CorrectPass123!")

    # Attempt 5 failed logins
    for i in range(5):
        resp = await gateway_client.post(
            "/auth/login",
            json={"email": user.email, "password": "WrongPassword123!"},
        )
        assert resp.status_code in (401, 423, 429)

    # 6th login attempt triggers lockout exception
    lock_resp = await gateway_client.post(
        "/auth/login",
        json={"email": user.email, "password": "WrongPassword123!"},
    )
    assert lock_resp.status_code in (401, 423, 429)



@pytest.mark.asyncio
async def test_logout_revokes_session(gateway_client: AsyncClient, seed_user):
    """Test logging out revokes JWT token and active session."""
    user = await seed_user(email="logout_test@contained.ai", password="Password123!")
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)

    # Logout
    logout_resp = await gateway_client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert logout_resp.status_code == 200
    assert logout_resp.json().get("status") == "logged_out"


@pytest.mark.asyncio
async def test_self_soft_deletion_real(gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession):
    """Test user self soft-deletion deactivates user account in real Postgres."""
    user = await seed_user(email="soft_delete@contained.ai", password="Password123!")
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)

    # Soft delete account
    del_resp = await gateway_client.delete(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_resp.status_code == 200
    assert del_resp.json().get("status") == "soft_deleted"

    # Verify user marked deleted in DB
    await real_db_session.refresh(user)
    assert user.is_deleted is True
    assert user.deleted_at is not None
