"""Real-world integration test suite for Datastore Bindings against real Postgres.

Covers binding a Qdrant collection to an ingestion hub, credential
encryption/decryption, unbind cleanup, and the security invariant that
credentials are never serialised in API responses.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.database import DatastoreBinding
from gateway.auth.utils import create_access_token
from projects.syntraflow.src.datastores.crypto import decrypt_credentials

pytestmark = pytest.mark.integration


async def _auth_headers(user) -> dict:
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_datastore_binding(gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession):
    """Bind a Qdrant datastore to an ingestion hub and verify the DB row."""
    owner = await seed_user(email="ds_owner_create@contained.ai", role="member")
    ingestion_hub = await seed_hub(owner=owner, name="Ingestion Hub", slug="ds-ingestion-hub", hub_type="ingestion")
    headers = await _auth_headers(owner)

    resp = await gateway_client.post(
        f"/api/hubs/{ingestion_hub.id}/ingestion/datastores",
        json={
            "name": "qdrant-main",
            "store_type": "qdrant",
            "connection_uri": "http://localhost:6333",
            "is_default": True,
        },
        headers=headers,
    )
    assert resp.status_code == 201, f"Create datastore failed: {resp.text}"
    data = resp.json()
    assert data["name"] == "qdrant-main"
    assert data["store_type"] == "qdrant"
    assert data["is_default"] is True

    # Verify DB row
    stmt = select(DatastoreBinding).where(DatastoreBinding.hub_id == ingestion_hub.id, DatastoreBinding.name == "qdrant-main")
    binding = (await real_db_session.execute(stmt)).scalar_one_or_none()
    assert binding is not None
    assert binding.store_type == "qdrant"
    assert binding.connection_uri == "http://localhost:6333"


@pytest.mark.asyncio
async def test_credential_encryption_and_no_serialization(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Credentials are encrypted at rest and never serialised in API responses."""
    owner = await seed_user(email="ds_owner_creds@contained.ai", role="member")
    ingestion_hub = await seed_hub(owner=owner, name="Ingestion Hub", slug="ds-creds-hub", hub_type="ingestion")
    headers = await _auth_headers(owner)

    secret_creds = {"api_key": "super-secret-key-123", "username": "dbuser", "password": "dbpass"}
    resp = await gateway_client.post(
        f"/api/hubs/{ingestion_hub.id}/ingestion/datastores",
        json={
            "name": "postgres-main",
            "store_type": "postgres",
            "connection_uri": "postgresql://dbuser:dbpass@localhost:5432/db",
            "credentials": secret_creds,
        },
        headers=headers,
    )
    assert resp.status_code == 201, f"Create datastore with creds failed: {resp.text}"
    data = resp.json()

    # Security invariant: credentials must NOT appear in the response
    assert "credentials" not in data
    assert "credentials_encrypted" not in data
    assert "api_key" not in str(data)
    assert "super-secret-key-123" not in str(data)

    # Verify encrypted at rest in DB
    stmt = select(DatastoreBinding).where(DatastoreBinding.hub_id == ingestion_hub.id, DatastoreBinding.name == "postgres-main")
    binding = (await real_db_session.execute(stmt)).scalar_one()
    assert binding.credentials_encrypted is not None
    # Stored value is NOT plaintext
    assert "super-secret-key-123" not in binding.credentials_encrypted

    # Decrypt and verify round-trip
    decrypted = decrypt_credentials(binding.credentials_encrypted)
    assert decrypted == secret_creds


@pytest.mark.asyncio
async def test_list_datastores_and_synthetic_defaults(
    gateway_client: AsyncClient, seed_user, seed_hub
):
    """Listing datastores returns created bindings plus synthetic platform defaults."""
    owner = await seed_user(email="ds_owner_list@contained.ai", role="member")
    ingestion_hub = await seed_hub(owner=owner, name="Ingestion Hub", slug="ds-list-hub", hub_type="ingestion")
    headers = await _auth_headers(owner)

    # Create one qdrant binding
    await gateway_client.post(
        f"/api/hubs/{ingestion_hub.id}/ingestion/datastores",
        json={
            "name": "qdrant-main",
            "store_type": "qdrant",
            "connection_uri": "http://localhost:6333",
        },
        headers=headers,
    )

    resp = await gateway_client.get(f"/api/hubs/{ingestion_hub.id}/ingestion/datastores", headers=headers)
    assert resp.status_code == 200
    bindings = resp.json()

    # Our created binding present
    assert any(b["name"] == "qdrant-main" and b["is_synthetic"] is False for b in bindings)
    # Synthetic platform defaults for other store types present
    synthetic = [b for b in bindings if b.get("is_synthetic")]
    assert len(synthetic) >= 1


@pytest.mark.asyncio
async def test_unbind_datastore_cleanup(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Unbinding a datastore removes the row."""
    owner = await seed_user(email="ds_owner_unbind@contained.ai", role="member")
    ingestion_hub = await seed_hub(owner=owner, name="Ingestion Hub", slug="ds-unbind-hub", hub_type="ingestion")
    headers = await _auth_headers(owner)

    create_resp = await gateway_client.post(
        f"/api/hubs/{ingestion_hub.id}/ingestion/datastores",
        json={
            "name": "qdrant-temp",
            "store_type": "qdrant",
            "connection_uri": "http://localhost:6333",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    binding_id = create_resp.json()["id"]

    # Unbind
    del_resp = await gateway_client.delete(
        f"/api/hubs/{ingestion_hub.id}/ingestion/datastores/{binding_id}",
        headers=headers,
    )
    assert del_resp.status_code == 204

    # Verify row gone
    binding = await real_db_session.get(DatastoreBinding, binding_id)
    assert binding is None


@pytest.mark.asyncio
async def test_datastore_binding_requires_ingestion_hub(
    gateway_client: AsyncClient, seed_user, seed_hub
):
    """Datastore binding endpoints reject non-ingestion hubs with 404."""
    owner = await seed_user(email="ds_owner_wronghub@contained.ai", role="member")
    agent_hub = await seed_hub(owner=owner, name="Agent Hub", slug="ds-agent-hub", hub_type="agent")
    headers = await _auth_headers(owner)

    resp = await gateway_client.get(f"/api/hubs/{agent_hub.id}/ingestion/datastores", headers=headers)
    assert resp.status_code == 404
