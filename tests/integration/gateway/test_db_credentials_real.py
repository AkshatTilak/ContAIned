"""Real-world External DB Credentials Vault Integration Tests (B8-16 / sub_16_03).

Tests creating, encrypting, testing connection, updating, listing, and deleting external DB credentials.
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.database import ExternalCredential
from gateway.auth.utils import create_access_token

pytestmark = pytest.mark.integration


async def _auth_headers(user) -> dict:
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_db_credentials_lifecycle(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession
):
    """Test full DB credentials vault lifecycle (create, encrypt, test, update, list, delete)."""
    uid = uuid.uuid4().hex[:8]
    user = await seed_user(email=f"dbcred_user_{uid}@contained.ai", role="admin")
    headers = await _auth_headers(user)

    # 1. Create an Agent Hub
    hub_resp = await gateway_client.post(
        "/api/hubs",
        json={"name": f"Vault Hub {uid}", "slug": f"vault-hub-{uid}", "hub_type": "agent"},
        headers=headers,
    )
    assert hub_resp.status_code == 201
    hub_id = hub_resp.json()["id"]

    # 2. Create Postgres External DB Credential
    raw_password = f"secret_pass_{uid}"
    create_payload = {
        "name": f"Analytics DB {uid}",
        "db_type": "postgres",
        "host": "localhost",
        "port": 5432,
        "database_name": "contained",
        "username": "contained_user",
        "password": raw_password,
        "is_read_only": True,
        "max_connections": 5,
    }
    create_resp = await gateway_client.post(
        f"/api/hubs/{hub_id}/db-credentials",
        json=create_payload,
        headers=headers,
    )
    assert create_resp.status_code == 201
    cred_data = create_resp.json()
    cred_id = cred_data["id"]
    assert cred_data["name"] == create_payload["name"]
    assert cred_data["db_type"] == "postgres"
    assert cred_data["has_secret"] is True
    # Ensure password is NOT leaked in response
    assert "password" not in cred_data

    # Verify encrypted storage in DB
    stmt = select(ExternalCredential).where(ExternalCredential.id == cred_id)
    db_cred = (await real_db_session.execute(stmt)).scalar_one_or_none()
    assert db_cred is not None
    assert db_cred.encrypted_secret_payload is not None
    assert raw_password not in db_cred.encrypted_secret_payload  # Ciphertext, not raw password

    # 3. Test Connection
    test_resp = await gateway_client.post(
        f"/api/hubs/{hub_id}/db-credentials/{cred_id}/test",
        headers=headers,
    )
    assert test_resp.status_code == 200
    test_result = test_resp.json()
    assert test_result["credential_id"] == cred_id
    assert "success" in test_result

    # 4. Update Credential
    new_password = f"updated_secret_{uid}"
    update_resp = await gateway_client.put(
        f"/api/hubs/{hub_id}/db-credentials/{cred_id}",
        json={
            "name": f"Updated Analytics DB {uid}",
            "password": new_password,
            "max_connections": 8,
        },
        headers=headers,
    )
    assert update_resp.status_code == 200
    updated_data = update_resp.json()
    assert updated_data["name"] == f"Updated Analytics DB {uid}"
    assert updated_data["max_connections"] == 8

    # Verify re-encryption in DB
    await real_db_session.refresh(db_cred)
    assert new_password not in db_cred.encrypted_secret_payload

    # 5. List Credentials in Hub
    list_resp = await gateway_client.get(
        f"/api/hubs/{hub_id}/db-credentials",
        headers=headers,
    )
    assert list_resp.status_code == 200
    creds_list = list_resp.json()
    assert any(c["id"] == cred_id for c in creds_list)

    # 6. Delete Credential
    delete_resp = await gateway_client.delete(
        f"/api/hubs/{hub_id}/db-credentials/{cred_id}",
        headers=headers,
    )
    assert delete_resp.status_code == 204

    # Verify deleted from DB
    deleted_cred = (await real_db_session.execute(stmt)).scalar_one_or_none()
    assert deleted_cred is None
