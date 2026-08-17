"""Real-world API Key Lifecycle Integration Tests (B8-16 / sub_16_01).

Tests creating, hub-scoping, updating, authenticating with, querying stats for, and revoking API keys.
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.database import APIKeyModel, APIKeyUsageModel
from gateway.auth.utils import create_access_token

pytestmark = pytest.mark.integration


async def _auth_headers(user) -> dict:
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_api_key_full_lifecycle(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession
):
    """Test full API key creation, database persistence, updating, stats, and revocation."""
    uid = uuid.uuid4().hex[:8]
    admin = await seed_user(email=f"apikey_admin_{uid}@contained.ai", role="admin")
    headers = await _auth_headers(admin)

    # 1. Create Platform API Key
    create_resp = await gateway_client.post(
        "/api/settings/api-keys",
        json={"name": f"Admin Test Key {uid}", "rate_limit": 100},
        headers=headers,
    )
    assert create_resp.status_code == 201
    key_data = create_resp.json()
    raw_key = key_data["raw_key"]
    key_id = key_data["id"]
    assert raw_key.startswith("sk-")
    assert key_data["prefix"] == raw_key[:8]
    assert key_data["is_active"] is True

    # Verify key is hashed in DB
    stmt = select(APIKeyModel).where(APIKeyModel.id == key_id)
    db_key = (await real_db_session.execute(stmt)).scalar_one_or_none()
    assert db_key is not None
    assert db_key.key != raw_key  # Hashed, not plaintext

    # 2. List API Keys
    list_resp = await gateway_client.get("/api/settings/api-keys", headers=headers)
    assert list_resp.status_code == 200
    keys = list_resp.json()
    assert any(k["id"] == key_id for k in keys)

    # 3. Update API Key
    update_resp = await gateway_client.put(
        f"/api/settings/api-keys/{key_id}",
        json={"name": f"Renamed Test Key {uid}", "rate_limit": 200},
        headers=headers,
    )
    assert update_resp.status_code == 200
    updated_key = update_resp.json()
    assert updated_key["name"] == f"Renamed Test Key {uid}"
    assert updated_key["rate_limit"] == 200

    # 4. Use API Key for Authentication via Bearer token on /v1/models
    models_resp = await gateway_client.get(
        "/v1/models",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert models_resp.status_code == 200

    # 5. Query Key Usage Stats
    usage_resp = await gateway_client.get(
        f"/api/settings/api-keys/{key_id}/usage",
        headers=headers,
    )
    assert usage_resp.status_code == 200
    usage_data = usage_resp.json()
    assert usage_data["key_id"] == key_id
    assert "total_requests" in usage_data

    # 6. Revoke API Key
    delete_resp = await gateway_client.delete(
        f"/api/settings/api-keys/{key_id}",
        headers=headers,
    )
    assert delete_resp.status_code == 204

    # Verify deleted from DB
    deleted_key = (await real_db_session.execute(stmt)).scalar_one_or_none()
    assert deleted_key is None

    # Verify subsequent requests with revoked key fail
    revoked_resp = await gateway_client.get(
        "/v1/models",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert revoked_resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_hub_scoped_api_key(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession
):
    """Test creating and managing hub-scoped API keys."""
    uid = uuid.uuid4().hex[:8]
    user = await seed_user(email=f"hub_user_{uid}@contained.ai", role="member")
    headers = await _auth_headers(user)

    # 1. Create a Hub where user is owner/maintainer
    hub_resp = await gateway_client.post(
        "/api/hubs",
        json={"name": f"Scoped Hub {uid}", "slug": f"scoped-hub-{uid}", "hub_type": "agent"},
        headers=headers,
    )
    assert hub_resp.status_code == 201
    hub_id = hub_resp.json()["id"]

    # 2. Create Hub-Scoped API Key
    key_resp = await gateway_client.post(
        "/api/settings/api-keys",
        json={"name": f"Hub Key {uid}", "hub_id": hub_id},
        headers=headers,
    )
    assert key_resp.status_code == 201
    scoped_data = key_resp.json()
    assert scoped_data["hub_id"] == hub_id
    assert scoped_data["hub_label"] == f"agent/scoped-hub-{uid}"

    # 3. List keys filtered by hub_id
    list_resp = await gateway_client.get(f"/api/settings/api-keys?hub_id={hub_id}", headers=headers)
    assert list_resp.status_code == 200
    hub_keys = list_resp.json()
    assert len(hub_keys) >= 1
    assert hub_keys[0]["hub_id"] == hub_id
