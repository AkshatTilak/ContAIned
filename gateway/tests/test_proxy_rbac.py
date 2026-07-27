"""Unit test for S5-11b: RBAC Authorization & Middleware for Infrastructure Proxy Routes."""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
import httpx

from common.config.settings import settings
from common.models.database import APIKeyModel
from gateway.main import app
from gateway.auth.utils import create_access_token
from gateway.auth.dependencies import get_db
from gateway.api import verify_api_key

client = TestClient(app)


class MockDB:
    def __init__(self):
        self.key = APIKeyModel(key="sk_test", is_active=True)

    async def execute(self, stmt):
        mock_res = AsyncMock()
        mock_res.scalar_one_or_none.return_value = self.key
        return mock_res


@pytest.fixture(autouse=True)
def setup_mock_db():
    mock_db = MockDB()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_api_key] = lambda: None
    yield
    app.dependency_overrides.clear()


def test_proxy_rbac_admin_allowed():
    """Verify admin user can access Qdrant/Neo4j infrastructure proxies."""
    admin_token = create_access_token("admin-1", "admin@contained.local", "admin")
    headers = {"Authorization": f"Bearer {admin_token}", "X-API-Key": "sk_test"}

    with patch.object(settings, "AUTH_ENABLED", True):
        mock_resp = httpx.Response(status_code=200, content=b"OK", headers={"content-type": "text/plain"})
        with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_resp
            res = client.get("/api/qdrant/collections", headers=headers)
            assert res.status_code == 200


def test_proxy_rbac_viewer_forbidden():
    """Verify viewer user is denied access (403 Forbidden) to infrastructure proxies."""
    viewer_token = create_access_token("viewer-1", "viewer@contained.local", "viewer")
    headers = {"Authorization": f"Bearer {viewer_token}", "X-API-Key": "sk_test"}

    with patch.object(settings, "AUTH_ENABLED", True):
        res = client.get("/api/qdrant/collections", headers=headers)
        assert res.status_code == 403
        assert "Insufficient permissions" in res.text



