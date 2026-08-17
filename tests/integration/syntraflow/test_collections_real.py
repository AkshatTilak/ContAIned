"""Real-world integration test suite for SyntraFlow Collection Management against real Postgres and Qdrant.

Covers collection creation, listing, updating, deletion, Qdrant physical schema synchronization,
and multi-tenant hub isolation.
"""

import pytest
from httpx import AsyncClient
from qdrant_client import AsyncQdrantClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.auth.utils import create_access_token
from projects.syntraflow.src.collections.manager import physical_collection_name
from projects.syntraflow.src.database.models import SyntraFlowCollection

pytestmark = pytest.mark.integration


async def _auth_headers(user) -> dict:
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_list_delete_collections_real(
    gateway_client: AsyncClient,
    seed_user,
    seed_hub,
    real_db_session: AsyncSession,
    qdrant_client: AsyncQdrantClient,
):
    """Test full CRUD lifecycle of SyntraFlow collections against real Postgres and Qdrant."""
    owner = await seed_user(email="coll_owner_crud@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Ingestion Hub CRUD", slug="ingestion-hub-crud", hub_type="ingestion")
    headers = await _auth_headers(owner)

    # 1. Create collection
    create_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/ingestion/collections",
        json={
            "name": "Doc Base Alpha",
            "embedding_model": "harrier-0.6b",
            "vector_dimension": 1024,
            "description": "Integration test vector catalog",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201, f"Create collection failed: {create_resp.text}"
    col_data = create_resp.json()
    col_id = col_data["id"]
    assert col_data["name"] == "Doc Base Alpha"
    assert col_data["vector_dimension"] == 1024

    # Verify DB row
    stmt = select(SyntraFlowCollection).where(SyntraFlowCollection.id == col_id)
    db_col = (await real_db_session.execute(stmt)).scalar_one_or_none()
    assert db_col is not None
    assert db_col.name == "Doc Base Alpha"
    assert db_col.hub_id == hub.id

    # Verify physical collection in Qdrant if available
    if qdrant_client:
        phys_name = physical_collection_name(hub.slug, "Doc Base Alpha")
        exists = await qdrant_client.collection_exists(phys_name)
        assert exists is True, f"Physical Qdrant collection '{phys_name}' should exist"

    # 2. List collections
    list_resp = await gateway_client.get(f"/api/hubs/{hub.id}/ingestion/collections", headers=headers)
    assert list_resp.status_code == 200
    collections = list_resp.json()
    assert any(c["id"] == col_id for c in collections)

    # 3. Update collection metadata
    patch_resp = await gateway_client.patch(
        f"/api/hubs/{hub.id}/ingestion/collections/{col_id}",
        json={"description": "Updated catalog description"},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["description"] == "Updated catalog description"

    # 4. Delete collection
    del_resp = await gateway_client.delete(
        f"/api/hubs/{hub.id}/ingestion/collections/{col_id}?force=true",
        headers=headers,
    )
    assert del_resp.status_code == 204

    # Verify DB removal
    db_col_after = (await real_db_session.execute(stmt)).scalar_one_or_none()
    assert db_col_after is None

    # Verify Qdrant physical collection removal if available
    if qdrant_client:
        exists_after = await qdrant_client.collection_exists(phys_name)
        assert exists_after is False, f"Physical collection '{phys_name}' should be deleted"


@pytest.mark.asyncio
async def test_collection_schema_sync_real(
    gateway_client: AsyncClient,
    seed_user,
    seed_hub,
    qdrant_client: AsyncQdrantClient,
):
    """Verify schema synchronization and vector dimension setup on Qdrant."""
    owner = await seed_user(email="coll_schema_user@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Schema Test Hub", slug="schema-test-hub", hub_type="ingestion")
    headers = await _auth_headers(owner)

    # Create collection with Harrier 0.6B's 1,024-dim output.
    # (Collection names allow only alphanumeric/space/dash/underscore — no dots.)
    resp_harrier = await gateway_client.post(
        f"/api/hubs/{hub.id}/ingestion/collections",
        json={
            "name": "Harrier 06B Collection",
            "embedding_model": "harrier-0.6b",
            "vector_dimension": 1024,
        },
        headers=headers,
    )
    assert resp_harrier.status_code == 201, f"Failed Harrier collection creation: {resp_harrier.text}"

    if qdrant_client:
        phys_name = physical_collection_name(hub.slug, "Harrier 06B Collection")
        info = await qdrant_client.get_collection(phys_name)
        # Vector size verification
        vector_size = info.config.params.vectors.size
        assert vector_size == 1024, f"Expected Qdrant vector size 1024, got {vector_size}"


@pytest.mark.asyncio
async def test_collection_hub_isolation_access_control(
    gateway_client: AsyncClient,
    seed_user,
    seed_hub,
):
    """Verify collection access is strictly scoped to the owner hub and isolated from other hubs."""
    user_a = await seed_user(email="user_hub_a@contained.ai", role="member")
    user_b = await seed_user(email="user_hub_b@contained.ai", role="member")

    hub_a = await seed_hub(owner=user_a, name="Hub Alpha", slug="hub-alpha", hub_type="ingestion")
    hub_b = await seed_hub(owner=user_b, name="Hub Beta", slug="hub-beta", hub_type="ingestion")

    headers_a = await _auth_headers(user_a)
    headers_b = await _auth_headers(user_b)

    # User A creates collection in Hub A
    create_resp = await gateway_client.post(
        f"/api/hubs/{hub_a.id}/ingestion/collections",
        json={"name": "Alpha Private Catalog"},
        headers=headers_a,
    )
    assert create_resp.status_code == 201
    col_a_id = create_resp.json()["id"]

    # User B should not see Hub A's collection in Hub B list
    list_b_resp = await gateway_client.get(f"/api/hubs/{hub_b.id}/ingestion/collections", headers=headers_b)
    assert list_b_resp.status_code == 200
    col_ids_b = [c["id"] for c in list_b_resp.json()]
    assert col_a_id not in col_ids_b

    # User B trying to access Hub A's endpoint or collection under Hub B route should be rejected/not found
    detail_b_resp = await gateway_client.get(
        f"/api/hubs/{hub_b.id}/ingestion/collections/{col_a_id}",
        headers=headers_b,
    )
    assert detail_b_resp.status_code in (404, 403)


@pytest.mark.asyncio
async def test_delete_hub_and_recreate_collection_with_same_name(
    gateway_client: AsyncClient,
    seed_user,
    qdrant_client: AsyncQdrantClient,
):
    """Deleting a hub and creating a new hub with the same slug allows creating a collection with the exact same name."""
    owner = await seed_user(email="lifecycle_tester@contained.ai", role="admin")
    headers = await _auth_headers(owner)

    # 1. Create first hub
    hub1_resp = await gateway_client.post(
        "/api/hubs",
        json={"name": "Resume Hub", "slug": "resume-lifecycle", "hub_type": "ingestion"},
        headers=headers,
    )
    assert hub1_resp.status_code == 201
    hub1_id = hub1_resp.json()["id"]

    # 2. Create collection "resume-data" in first hub
    col1_resp = await gateway_client.post(
        f"/api/hubs/{hub1_id}/ingestion/collections",
        json={"name": "resume-data", "embedding_model": "harrier-0.6b", "vector_dimension": 768},
        headers=headers,
    )
    assert col1_resp.status_code == 201

    # 3. Delete first hub
    del_hub_resp = await gateway_client.delete(f"/api/hubs/{hub1_id}", headers=headers)
    assert del_hub_resp.status_code == 204

    # 4. Re-create new hub with exact same slug
    hub2_resp = await gateway_client.post(
        "/api/hubs",
        json={"name": "Resume Hub", "slug": "resume-lifecycle", "hub_type": "ingestion"},
        headers=headers,
    )
    assert hub2_resp.status_code == 201
    hub2_id = hub2_resp.json()["id"]

    # 5. Create collection with the exact same name "resume-data" in new hub (tests physical_name collision resolution)
    col2_resp = await gateway_client.post(
        f"/api/hubs/{hub2_id}/ingestion/collections",
        json={"name": "resume-data", "embedding_model": "harrier-0.6b", "vector_dimension": 768},
        headers=headers,
    )
    assert col2_resp.status_code == 201, f"Failed to recreate collection with same physical name: {col2_resp.text}"
    assert col2_resp.json()["name"] == "resume-data"

