
import pytest
pytestmark = pytest.mark.unit
"""Integration tests for S6-03b password authentication routes."""

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from common.clients.postgres import get_async_db
from common.config.settings import get_settings
from common.models.database import Base
from gateway.main import app

# Enable AUTH_ENABLED for auth route integration tests
get_settings().AUTH_ENABLED = True

# Create in-memory SQLite engine for test client route tests
test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
TestingSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)



async def override_get_async_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_async_db] = override_get_async_db
client = TestClient(app)


def test_register_and_login_flow():
    """Test user registration, login, and token generation."""
    email = "pass_user@example.com"
    password = "SuperValidPassword123!"

    # 1. Register
    reg_resp = client.post("/auth/register", json={
        "email": email,
        "password": password,
        "display_name": "Password User",
    })
    assert reg_resp.status_code == 202
    assert reg_resp.json() == {"status": "registration_received"}

    # Register duplicate email returns non-enumerating 202
    dup_resp = client.post("/auth/register", json={
        "email": email,
        "password": password,
    })
    assert dup_resp.status_code == 202

    # 2. Login
    login_resp = client.post("/auth/login", json={
        "email": email,
        "password": password,
    })
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == email


def test_login_invalid_credentials():
    """Test login failure with wrong password."""
    resp = client.post("/auth/login", json={
        "email": "unknown@example.com",
        "password": "WrongPassword123!",
    })
    assert resp.status_code == 401
    assert "Invalid email or password" in resp.json()["message"]


def test_forgot_and_reset_password():
    """Test forgot-password and reset-password endpoints."""
    forgot_resp = client.post("/auth/forgot-password", json={
        "email": "pass_user@example.com",
    })
    assert forgot_resp.status_code == 202
    assert forgot_resp.json() == {"status": "reset_email_sent"}

    reset_resp = client.post("/auth/reset-password", json={
        "token": "invalid_token_string",
        "new_password": "NewSuperPassword123!",
    })
    assert reset_resp.status_code == 400


def test_lockout_policy():
    """Test account lockout after 5 consecutive failed login attempts."""
    email = "lockout_user@example.com"
    password = "SuperValidPassword123!"

    # Register user
    client.post("/auth/register", json={"email": email, "password": password})

    # Fail 4 logins
    for _ in range(4):
        resp = client.post("/auth/login", json={"email": email, "password": "WrongPassword123!"})
        assert resp.status_code == 401

    # 5th failed login triggers lockout
    resp = client.post("/auth/login", json={"email": email, "password": "WrongPassword123!"})
    assert resp.status_code == 401

    # 6th attempt (even with correct password) returns 423 Account Locked
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 423


def test_change_password_flow():
    """Test change password endpoint with authorization."""
    email = "change_pass_user@example.com"
    old_pass = "OldSuperPassword123!"
    new_pass = "NewSuperPassword123!"

    client.post("/auth/register", json={"email": email, "password": old_pass})
    login_resp = client.post("/auth/login", json={"email": email, "password": old_pass})
    token = login_resp.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}

    # Incorrect current password -> 403
    bad_resp = client.post(
        "/auth/change-password",
        json={"current_password": "WrongOldPassword123!", "new_password": new_pass},
        headers=headers,
    )
    assert bad_resp.status_code == 403

    # Success change password
    good_resp = client.post(
        "/auth/change-password",
        json={"current_password": old_pass, "new_password": new_pass},
        headers=headers,
    )
    assert good_resp.status_code == 200
    assert good_resp.json() == {"status": "password_changed"}

    # Login with new password succeeds
    new_login = client.post("/auth/login", json={"email": email, "password": new_pass})
    assert new_login.status_code == 200

