"""Tests for API Key Management CRUD & Usage endpoints (`/api/settings/api-keys`)."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from common.models.database import APIKeyModel
from gateway.auth.dependencies import get_db
from gateway.main import app


class MockDB:
    def __init__(self):
        self.keys = []
        self.counter = 1

    def add(self, item):
        if not hasattr(item, "id") or item.id is None:
            item.id = self.counter
            self.counter += 1
        self.keys.append(item)

    async def commit(self):
        pass

    async def refresh(self, item):
        pass

    async def execute(self, stmt):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = self.keys
        mock_result.scalar_one_or_none.return_value = self.keys[0] if self.keys else None
        mock_result.scalar.return_value = 0
        return mock_result

    async def delete(self, item):
        self.keys = [k for k in self.keys if k.id != item.id]


@pytest.fixture(autouse=True)
def setup_mock_db():
    mock_db = MockDB()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


def test_create_api_key():
    payload = {"name": "Test Key", "rate_limit": 100}
    response = client.post("/api/settings/api-keys", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "raw_key" in data
    assert data["raw_key"].startswith("sk-")
    assert data["name"] == "Test Key"
    assert data["rate_limit"] == 100


def test_list_api_keys():
    response = client.get("/api/settings/api-keys")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_update_api_key():
    create_res = client.post("/api/settings/api-keys", json={"name": "Old Name", "rate_limit": 60})
    key_id = create_res.json()["id"]

    update_payload = {"name": "New Name", "rate_limit": 120, "is_active": False}
    response = client.put(f"/api/settings/api-keys/{key_id}", json=update_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"
    assert data["rate_limit"] == 120


def test_revoke_api_key():
    create_res = client.post("/api/settings/api-keys", json={"name": "Key to Revoke"})
    key_id = create_res.json()["id"]

    response = client.delete(f"/api/settings/api-keys/{key_id}")
    assert response.status_code == 204
