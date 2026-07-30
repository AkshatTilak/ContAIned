import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from gateway.auth.utils import create_access_token, verify_access_token, hash_token
from gateway.auth.dependencies import require_role


def test_create_and_verify_access_token():
    """Test JWT token encoding and decoding with platform_role."""
    user_id = "user-123-uuid"
    email = "test@example.com"
    platform_role = "member"

    token = create_access_token(user_id=user_id, email=email, platform_role=platform_role, expires_hours=1)
    assert isinstance(token, str)
    assert len(token) > 20

    payload = verify_access_token(token)
    assert payload["sub"] == user_id
    assert payload["email"] == email
    assert payload["platform_role"] == platform_role
    assert "exp" in payload
    assert "iat" in payload


def test_hash_token():
    """Test deterministic token hashing."""
    token = "some.jwt.token"
    h1 = hash_token(token)
    h2 = hash_token(token)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex string length


def test_invalid_role_construction():
    """Test that require_role raises ValueError for unknown platform roles."""
    with pytest.raises(ValueError) as excinfo:
        require_role("editor")
    assert "Unknown platform role" in str(excinfo.value)

    with pytest.raises(ValueError):
        require_role("viewer")


# FastAPI App for testing RBAC dependencies
app = FastAPI()


@app.get("/test/public")
async def public_route():
    return {"message": "public"}


@app.get("/test/admin-only")
async def admin_route(user: dict = Depends(require_role("admin"))):
    return {"user": user["email"], "platform_role": user["platform_role"]}


@app.get("/test/member-or-admin")
async def member_route(user: dict = Depends(require_role("member"))):
    return {"user": user["email"], "platform_role": user["platform_role"]}


client = TestClient(app)


def test_public_route():
    resp = client.get("/test/public")
    assert resp.status_code == 200
    assert resp.json() == {"message": "public"}
