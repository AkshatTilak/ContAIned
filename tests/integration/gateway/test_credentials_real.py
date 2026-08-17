"""Real-world Provider Credentials Integration Tests (B8-16 / sub_16_02).

Tests setting, listing (merged DB + Env), overriding, masking, and deleting provider credentials.
"""

import os
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.database import ProviderCredential
from gateway.auth.utils import create_access_token

pytestmark = pytest.mark.integration


async def _auth_headers(user) -> dict:
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_credentials_lifecycle(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession
):
    """Test full provider credentials lifecycle (create, masked view, DB precedence, delete)."""
    uid = uuid.uuid4().hex[:8]
    admin = await seed_user(email=f"cred_admin_{uid}@contained.ai", role="admin")
    headers = await _auth_headers(admin)

    test_api_key = "AIzaSyDummyTestKeyForVerification12345678"

    # 1. Upsert Credential for provider 'google'
    upsert_resp = await gateway_client.post(
        "/api/settings/credentials",
        json={"provider": "google", "api_key": test_api_key},
        headers=headers,
    )
    assert upsert_resp.status_code == 201
    cred_data = upsert_resp.json()
    assert cred_data["provider"] == "google"
    assert cred_data["source"] == "db"
    assert cred_data["masked_key"] == f"{test_api_key[:4]}...{test_api_key[-4:]}"

    # Verify DB persistence
    stmt = select(ProviderCredential).where(ProviderCredential.provider == "google")
    db_cred = (await real_db_session.execute(stmt)).scalar_one_or_none()
    assert db_cred is not None
    assert db_cred.api_key == test_api_key

    # 2. List Credentials (merged view)
    list_resp = await gateway_client.get("/api/settings/credentials", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    google_item = next((i for i in items if i["provider"] == "google"), None)
    assert google_item is not None
    assert google_item["source"] == "db"

    # 3. Delete Credential from DB
    del_resp = await gateway_client.delete("/api/settings/credentials/google", headers=headers)
    assert del_resp.status_code == 204

    # Verify deleted from DB
    deleted_cred = (await real_db_session.execute(stmt)).scalar_one_or_none()
    assert deleted_cred is None


@pytest.mark.asyncio
async def test_credentials_rbac(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession
):
    """Verify non-admin users are rejected with 403 Forbidden."""
    uid = uuid.uuid4().hex[:8]
    member = await seed_user(email=f"cred_member_{uid}@contained.ai", role="member")
    headers = await _auth_headers(member)

    # Member attempting to list credentials
    list_resp = await gateway_client.get("/api/settings/credentials", headers=headers)
    assert list_resp.status_code == 403

    # Member attempting to upsert credentials
    upsert_resp = await gateway_client.post(
        "/api/settings/credentials",
        json={"provider": "anthropic", "api_key": "sk-ant-test"},
        headers=headers,
    )
    assert upsert_resp.status_code == 403
