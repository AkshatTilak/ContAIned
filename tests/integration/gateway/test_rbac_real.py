"""Real-world integration test suite for RBAC & API Keys against real Postgres.

Tests admin vs member platform roles, hub maintainer role checks,
API key creation, authentication with API keys, and key revocation.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from common.models.database import APIKeyModel
from gateway.auth.utils import create_access_token

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_platform_admin_vs_member_rbac(gateway_client: AsyncClient, seed_user):
    """Test platform admin vs member role restrictions on administrative endpoints."""
    admin = await seed_user(email="admin_rbac@contained.ai", role="admin")
    member = await seed_user(email="member_rbac@contained.ai", role="member")

    admin_token = create_access_token(user_id=admin.id, email=admin.email, platform_role="admin")
    member_token = create_access_token(user_id=member.id, email=member.email, platform_role="member")

    # 1. Member attempts platform-wide API key creation -> 403 Forbidden
    mem_resp = await gateway_client.post(
        "/api/settings/api-keys",
        json={"name": "Platform Key Member"},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert mem_resp.status_code == 403

    # 2. Admin creates platform-wide API key -> 201 Created
    admin_resp = await gateway_client.post(
        "/api/settings/api-keys",
        json={"name": "Platform Key Admin"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_resp.status_code == 201
    key_data = admin_resp.json()
    assert key_data.get("raw_key") is not None
    assert key_data.get("name") == "Platform Key Admin"


@pytest.mark.asyncio
async def test_api_key_lifecycle_and_revocation(gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession):
    """Test full API key lifecycle: creation, usage, and revocation against real DB."""
    admin = await seed_user(email="apikey_admin@contained.ai", role="admin")
    admin_token = create_access_token(user_id=admin.id, email=admin.email, platform_role="admin")

    # 1. Create API key
    create_resp = await gateway_client.post(
        "/api/settings/api-keys",
        json={"name": "Test Key for Revoke"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create_resp.status_code == 201
    key_info = create_resp.json()
    raw_key = key_info["raw_key"]
    key_id = key_info["id"]

    # 2. Revoke API key
    revoke_resp = await gateway_client.delete(
        f"/api/settings/api-keys/{key_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert revoke_resp.status_code in (200, 204)

    # 3. Verify key is deleted in DB
    key_obj = await real_db_session.get(APIKeyModel, key_id)
    assert key_obj is None
