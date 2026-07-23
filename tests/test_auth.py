import unittest
import jwt
from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient

from gateway.auth.utils import create_access_token, verify_access_token, hash_token
from gateway.auth.dependencies import get_current_user, require_role, ROLE_HIERARCHY


def test_create_and_verify_access_token():
    """Test JWT token encoding and decoding."""
    user_id = "user-123-uuid"
    email = "test@example.com"
    role = "editor"

    token = create_access_token(user_id=user_id, email=email, role=role, expires_hours=1)
    assert isinstance(token, str)
    assert len(token) > 20

    payload = verify_access_token(token)
    assert payload["sub"] == user_id
    assert payload["email"] == email
    assert payload["role"] == role
    assert "exp" in payload
    assert "iat" in payload


def test_hash_token():
    """Test deterministic token hashing."""
    token = "some.jwt.token"
    h1 = hash_token(token)
    h2 = hash_token(token)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex string length


def test_role_hierarchy_logic():
    """Test RBAC role ordering logic."""
    assert ROLE_HIERARCHY["admin"] > ROLE_HIERARCHY["editor"]
    assert ROLE_HIERARCHY["editor"] > ROLE_HIERARCHY["viewer"]


# FastAPI App for testing RBAC dependencies
app = FastAPI()


@app.get("/test/public")
async def public_route():
    return {"message": "public"}


@app.get("/test/admin-only")
async def admin_route(user: dict = Depends(require_role("admin"))):
    return {"user": user["email"], "role": user["role"]}


@app.get("/test/editor-or-admin")
async def editor_route(user: dict = Depends(require_role("editor", "admin"))):
    return {"user": user["email"], "role": user["role"]}


client = TestClient(app)


def test_public_route():
    resp = client.get("/test/public")
    assert resp.status_code == 200
    assert resp.json() == {"message": "public"}
