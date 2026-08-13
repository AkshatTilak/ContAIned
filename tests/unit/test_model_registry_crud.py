
import pytest
pytestmark = pytest.mark.unit
import pytest
import asyncio
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import select

from common.clients.postgres import get_async_db
from common.models.database import Base, ModelRegistryModel, User
from gateway.auth.utils import create_access_token
from gateway.main import app
from tests.unit.test_admin_users_api import test_engine, TestingSessionLocal, override_get_async_db

# Configure TestClient
app.dependency_overrides[get_async_db] = override_get_async_db
client = TestClient(app)

# Helper headers
admin_token = create_access_token(user_id="admin-actor-id", email="admin@contained.local", platform_role="admin")
admin_headers = {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(autouse=True)
def reset_db_state(monkeypatch):
    """Reset database and seed admin user between tests."""
    async def _reset():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        async with TestingSessionLocal() as db:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
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


def test_model_registration_and_crud():
    """Test POST /api/models/register, PUT /api/models/{id}, and DELETE /api/models/{id} endpoints."""
    # 1. Register a new cloud model
    payload = {
        "role": "completion",
        "mode": "cloud",
        "provider": "google",
        "model_id": "gemini/gemini-2.0-flash-exp",
        "display_name": "Gemini 2.0 Flash Exp",
        "framework": "litellm",
        "is_default": True,
        "priority": 10
    }
    resp = client.post("/api/models/register", json=payload, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    
    # Verify database entry exists
    async def check_db():
        async with TestingSessionLocal() as db:
            res = await db.execute(select(ModelRegistryModel).where(ModelRegistryModel.model_id == "gemini/gemini-2.0-flash-exp"))
            entry = res.scalar_one_or_none()
            assert entry is not None
            assert entry.display_name == "Gemini 2.0 Flash Exp"
            assert entry.is_default is True
            assert entry.priority == 10
    asyncio.run(check_db())

    # 2. Update model display name and disable it
    update_payload = {
        "display_name": "Updated Gemini 2.0",
        "is_enabled": False
    }
    resp_update = client.put("/api/models/gemini/gemini-2.0-flash-exp", json=update_payload, headers=admin_headers)
    assert resp_update.status_code == 200
    
    async def check_db_updated():
        async with TestingSessionLocal() as db:
            res = await db.execute(select(ModelRegistryModel).where(ModelRegistryModel.model_id == "gemini/gemini-2.0-flash-exp"))
            entry = res.scalar_one_or_none()
            assert entry is not None
            assert entry.display_name == "Updated Gemini 2.0"
            assert entry.is_enabled is False
    asyncio.run(check_db_updated())

    # 3. Delete model registry entry
    resp_del = client.delete("/api/models/gemini/gemini-2.0-flash-exp", headers=admin_headers)
    assert resp_del.status_code == 200
    
    async def check_db_deleted():
        async with TestingSessionLocal() as db:
            res = await db.execute(select(ModelRegistryModel).where(ModelRegistryModel.model_id == "gemini/gemini-2.0-flash-exp"))
            assert res.scalar_one_or_none() is None
    asyncio.run(check_db_deleted())


def test_get_litellm_available_models():
    """Test GET /api/models/litellm/available endpoint."""
    # Query Gemini LiteLLM models
    resp = client.get("/api/models/litellm/available?provider=google", headers=admin_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) > 0
    # Confirm models are mapped and modes are present
    assert any("gemini" in m["name"] for m in items)
    assert all("mode" in m for m in items)
