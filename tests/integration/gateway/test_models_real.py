"""Real-world Model Registry Integration Tests (B8-16 / sub_16_04).

Tests listing registry, registering custom models, updating configurations, LiteLLM availability, and deletion.
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.database import ModelRegistryModel
from gateway.auth.utils import create_access_token

pytestmark = pytest.mark.integration


async def _auth_headers(user) -> dict:
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_models_registry_lifecycle(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession
):
    """Test model registry retrieval, registration, updating, querying, and deletion."""
    uid = uuid.uuid4().hex[:8]
    admin = await seed_user(email=f"models_admin_{uid}@contained.ai", role="admin")
    headers = await _auth_headers(admin)

    # 1. List Available Models in Registry
    reg_resp = await gateway_client.get("/api/models", headers=headers)
    assert reg_resp.status_code == 200
    registry = reg_resp.json()
    assert "completion" in registry
    assert "embedding" in registry
    assert "available" in registry["completion"]

    # 2. Register Custom Model with distributed model identifier
    custom_model_id = f"gemini/gemma-4-31b-it-custom-{uid}"
    reg_payload = {
        "role": "completion",
        "mode": "cloud",
        "provider": "google",
        "model_id": custom_model_id,
        "display_name": f"Custom Gemma 4 31B {uid}",
        "framework": "litellm",
        "context_window": 8192,
        "is_default": False,
        "is_enabled": True,
    }
    create_resp = await gateway_client.post(
        "/api/models/register",
        json=reg_payload,
        headers=headers,
    )
    assert create_resp.status_code == 200
    res_data = create_resp.json()
    assert res_data["status"] == "success"

    # Verify DB persistence
    stmt = select(ModelRegistryModel).where(ModelRegistryModel.model_id == custom_model_id)
    db_model = (await real_db_session.execute(stmt)).scalar_one_or_none()
    assert db_model is not None
    assert db_model.display_name == reg_payload["display_name"]

    # 3. Update Model in Registry
    update_resp = await gateway_client.put(
        f"/api/models/{custom_model_id}",
        json={"display_name": f"Updated Gemma 4 31B {uid}", "context_window": 16384},
        headers=headers,
    )
    assert update_resp.status_code == 200

    await real_db_session.refresh(db_model)
    assert db_model.display_name == f"Updated Gemma 4 31B {uid}"
    assert db_model.context_window == 16384

    # 4. Query LiteLLM Provider Models
    litellm_resp = await gateway_client.get(
        "/api/models/litellm/available?provider=google",
        headers=headers,
    )
    assert litellm_resp.status_code == 200
    litellm_data = litellm_resp.json()
    assert "models" in litellm_data or isinstance(litellm_data, (list, dict))

    # 5. Query Local Models Status
    local_resp = await gateway_client.get("/api/models/local/status", headers=headers)
    assert local_resp.status_code == 200
    assert "items" in local_resp.json()

    # 6. Delete Model from Registry
    del_resp = await gateway_client.delete(f"/api/models/{custom_model_id}", headers=headers)
    assert del_resp.status_code == 200

    # Verify deleted from DB
    deleted_model = (await real_db_session.execute(stmt)).scalar_one_or_none()
    assert deleted_model is None
