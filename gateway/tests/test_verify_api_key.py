"""Unit tests for verify_api_key authentication dependency."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import FastAPI, APIRouter, Depends, Request
from fastapi.testclient import TestClient

from common.config.settings import settings
from common.models.database import APIKeyModel
from gateway.api import verify_api_key
from gateway.auth.utils import create_access_token
from gateway.auth.api_key_middleware import hash_api_key

app = FastAPI()

@app.get("/api/dummy-route", dependencies=[Depends(verify_api_key)])
async def dummy_endpoint(request: Request):
    return {"status": "ok", "user": getattr(request.state, "user", None)}

client = TestClient(app)


def test_verify_api_key_auth_disabled():
    with patch.object(settings, "AUTH_ENABLED", False):
        res = client.get("/api/dummy-route")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"


def test_verify_api_key_jwt_authenticated():
    with patch.object(settings, "AUTH_ENABLED", True):
        token = create_access_token("user-123", "user@example.com", "admin")
        from gateway.auth.middleware import AuthMiddleware
        
        test_router = APIRouter(prefix="/api", dependencies=[Depends(verify_api_key)])
        @test_router.get("/jwt-route")
        async def jwt_route(request: Request):
            return {"status": "ok", "user": getattr(request.state, "user", None)}

        middleware_app = FastAPI()
        middleware_app.add_middleware(AuthMiddleware)
        middleware_app.include_router(test_router)
        
        test_client = TestClient(middleware_app)
        res = test_client.get("/api/jwt-route", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert res.json()["status"] == "ok"


def test_verify_api_key_valid_api_key():
    raw_key = "sk-testkey123"
    hashed = hash_api_key(raw_key)
    mock_key_obj = APIKeyModel(id=1, key=hashed, is_active=True, user_id="user-key-owner")

    with patch.object(settings, "AUTH_ENABLED", True):
        mock_session = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = mock_key_obj
        mock_session.execute = AsyncMock(return_value=mock_res)
        
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_session
        mock_ctx.__aexit__.return_value = None

        with patch("gateway.api.get_sessionmaker", return_value=lambda: mock_ctx):
            res = client.get("/api/dummy-route", headers={"X-API-Key": raw_key})
            assert res.status_code == 200
            assert res.json()["status"] == "ok"
            assert res.json()["user"]["sub"] == "user-key-owner"


def test_verify_api_key_missing_and_invalid():
    with patch.object(settings, "AUTH_ENABLED", True):
        # Missing auth & X-API-Key
        res = client.get("/api/dummy-route")
        assert res.status_code == 401
        assert "Unauthorized" in res.json()["detail"]

        # Invalid X-API-Key
        mock_session = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_res)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_session
        mock_ctx.__aexit__.return_value = None

        with patch("gateway.api.get_sessionmaker", return_value=lambda: mock_ctx):
            res_inv = client.get("/api/dummy-route", headers={"X-API-Key": "invalid_key"})
            assert res_inv.status_code == 401
            assert "Invalid X-API-Key" in res_inv.json()["detail"]
