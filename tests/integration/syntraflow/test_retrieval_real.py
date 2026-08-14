"""Real-world integration test suite for SyntraFlow Retrieval Engine against real Postgres, Qdrant, & Neo4j.

Covers semantic search, vector-only vs hybrid retrieval, metadata filtering,
hub-scoped retrieval isolation, and multi-dimension collection querying.
"""

import asyncio
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.auth.utils import create_access_token

pytestmark = pytest.mark.integration


async def _auth_headers(user) -> dict:
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


async def _wait_for_job_completion(gateway_client: AsyncClient, hub_id: str, job_id: str, headers: dict, timeout: int = 15):
    """Poll job status until completed or failed."""
    start_time = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start_time < timeout:
        resp = await gateway_client.get(f"/api/hubs/{hub_id}/ingestion/jobs/{job_id}", headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") in ("completed", "failed"):
                return data
        await asyncio.sleep(0.3)
    return {"status": "timeout"}


@pytest.mark.asyncio
async def test_retrieval_engine_known_documents(
    gateway_client: AsyncClient,
    seed_user,
    seed_hub,
    real_db_session: AsyncSession,
):
    """Test ingesting known content and searching via the retrieval endpoint."""
    owner = await seed_user(email="retrieval_owner_known@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Retrieval Known Hub", slug="retrieval-known-hub", hub_type="ingestion")
    headers = await _auth_headers(owner)

    # 1. Create collection
    col_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/ingestion/collections",
        json={"name": "Known Doc Catalog", "embedding_model": "harrier-0.6b", "vector_dimension": 1024},
        headers=headers,
    )
    assert col_resp.status_code == 201
    col_id = col_resp.json()["id"]

    # 2. Ingest document with unique search terms
    doc_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/ingestion/documents/text",
        json={
            "collection_id": col_id,
            "filename": "quantum_encryption.txt",
            "text": (
                "Post-quantum cryptography utilizes lattice-based algorithms to withstand "
                "attacks from quantum computers. The Falcon and Kyber algorithms were selected by NIST."
            ),
            "embedding_model": "harrier-0.6b",
        },
        headers=headers,
    )
    assert doc_resp.status_code == 202
    job_id = doc_resp.json()["job_id"]
    job_res = await _wait_for_job_completion(gateway_client, hub.id, job_id, headers)
    assert job_res["status"] == "completed"

    # 3. Perform semantic search
    search_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/ingestion/search",
        json={
            "query": "lattice-based algorithms post-quantum cryptography",
            "collection_ids": [col_id],
            "limit": 5,
            "strategy": "vector",
        },
        headers=headers,
    )
    assert search_resp.status_code == 200, f"Search failed: {search_resp.text}"
    search_results = search_resp.json()

    results = search_results.get("results", [])
    assert len(results) > 0, "Search should return relevant result for quantum query"
    first_hit = results[0]
    assert first_hit.get("score", 0.0) >= 0.0


@pytest.mark.asyncio
async def test_vector_only_vs_hybrid_retrieval_comparison(
    gateway_client: AsyncClient,
    seed_user,
    seed_hub,
    real_db_session: AsyncSession,
):
    """Compare vector-only strategy vs hybrid/graph retrieval strategies."""
    owner = await seed_user(email="retrieval_strat_owner@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Strategy Hub", slug="strategy-hub", hub_type="ingestion")
    headers = await _auth_headers(owner)

    col_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/ingestion/collections",
        json={"name": "Strategy Catalog"},
        headers=headers,
    )
    assert col_resp.status_code == 201
    col_id = col_resp.json()["id"]

    # Ingest test text
    doc_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/ingestion/documents/text",
        json={
            "collection_id": col_id,
            "filename": "microservice_architecture.txt",
            "text": "Microservices communicate asynchronously via Kafka message brokers and Redis caches.",
        },
        headers=headers,
    )
    assert doc_resp.status_code == 202
    job_id = doc_resp.json()["job_id"]
    job_res = await _wait_for_job_completion(gateway_client, hub.id, job_id, headers)
    assert job_res["status"] == "completed"

    # 1. Vector strategy
    vec_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/ingestion/search",
        json={"query": "Kafka message brokers", "collection_id": col_id, "strategy": "vector"},
        headers=headers,
    )
    assert vec_resp.status_code == 200

    # 2. Hybrid strategy
    hyb_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/ingestion/search",
        json={"query": "Kafka message brokers", "collection_id": col_id, "strategy": "hybrid"},
        headers=headers,
    )
    assert hyb_resp.status_code == 200


@pytest.mark.asyncio
async def test_retrieval_metadata_filtering(
    gateway_client: AsyncClient,
    seed_user,
    seed_hub,
    real_db_session: AsyncSession,
):
    """Test metadata filtering by document_id during retrieval."""
    owner = await seed_user(email="retrieval_meta_owner@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Metadata Hub", slug="metadata-hub", hub_type="ingestion")
    headers = await _auth_headers(owner)

    col_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/ingestion/collections",
        json={"name": "Metadata Catalog"},
        headers=headers,
    )
    assert col_resp.status_code == 201
    col_id = col_resp.json()["id"]

    # Ingest Doc A
    doc_a = await gateway_client.post(
        f"/api/hubs/{hub.id}/ingestion/documents/text",
        json={"collection_id": col_id, "filename": "doc_a.txt", "text": "Document Alpha contains secret code ALPHA-99."},
        headers=headers,
    )
    job_a_id = doc_a.json()["job_id"]
    res_a = await _wait_for_job_completion(gateway_client, hub.id, job_a_id, headers)
    assert res_a["status"] == "completed"

    # Ingest Doc B
    doc_b = await gateway_client.post(
        f"/api/hubs/{hub.id}/ingestion/documents/text",
        json={"collection_id": col_id, "filename": "doc_b.txt", "text": "Document Beta contains secret code BETA-88."},
        headers=headers,
    )
    job_b_id = doc_b.json()["job_id"]
    res_b = await _wait_for_job_completion(gateway_client, hub.id, job_b_id, headers)
    assert res_b["status"] == "completed"

    # Fetch document IDs from API
    docs_resp = await gateway_client.get(f"/api/hubs/{hub.id}/ingestion/documents", headers=headers)
    items = docs_resp.json()["items"]
    doc_a_id = next(i["id"] for i in items if i["filename"] == "doc_a.txt")

    # Search with document_id filter for doc_a
    filter_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/ingestion/search",
        json={
            "query": "secret code",
            "collection_id": col_id,
            "metadata_filter": {"document_id": doc_a_id},
        },
        headers=headers,
    )
    assert filter_resp.status_code == 200
    results = filter_resp.json().get("results", [])
    for res in results:
        assert res.get("document_id") == doc_a_id


@pytest.mark.asyncio
async def test_hub_scoped_retrieval_isolation(
    gateway_client: AsyncClient,
    seed_user,
    seed_hub,
    real_db_session: AsyncSession,
):
    """Verify search queries in Hub A cannot access collections or chunks belonging to Hub B."""
    user_a = await seed_user(email="retrieval_iso_a@contained.ai", role="member")
    user_b = await seed_user(email="retrieval_iso_b@contained.ai", role="member")

    hub_a = await seed_hub(owner=user_a, name="Hub Iso A", slug="hub-iso-a", hub_type="ingestion")
    hub_b = await seed_hub(owner=user_b, name="Hub Iso B", slug="hub-iso-b", hub_type="ingestion")

    headers_a = await _auth_headers(user_a)
    headers_b = await _auth_headers(user_b)

    # Collection in Hub B
    col_b_resp = await gateway_client.post(
        f"/api/hubs/{hub_b.id}/ingestion/collections",
        json={"name": "Catalog Beta"},
        headers=headers_b,
    )
    col_b_id = col_b_resp.json()["id"]

    # Search from Hub A referencing Hub B's collection ID should be rejected / 404
    search_cross = await gateway_client.post(
        f"/api/hubs/{hub_a.id}/ingestion/search",
        json={"query": "secret", "collection_ids": [col_b_id]},
        headers=headers_a,
    )
    assert search_cross.status_code in (404, 403, 422)


@pytest.mark.asyncio
async def test_retrieval_multi_dimension_collections(
    gateway_client: AsyncClient,
    seed_user,
    seed_hub,
    real_db_session: AsyncSession,
):
    """Test retrieval on Harrier 0.6B (1,024-dim) and Harrier 270M (640-dim) collections."""
    owner = await seed_user(email="retrieval_multidim@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="MultiDim Hub", slug="multidim-hub", hub_type="ingestion")
    headers = await _auth_headers(owner)

    # 1. Harrier 0.6B 1,024-dim collection
    col_harrier_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/ingestion/collections",
        json={"name": "Harrier Catalog", "embedding_model": "harrier-0.6b", "vector_dimension": 1024},
        headers=headers,
    )
    col_harrier_id = col_harrier_resp.json()["id"]

    # 2. Harrier 270M 640-dim collection
    col640_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/ingestion/collections",
        json={"name": "Harrier 270M Catalog", "embedding_model": "harrier-270m", "vector_dimension": 640},
        headers=headers,
    )
    col640_id = col640_resp.json()["id"]

    # Search Harrier 0.6B collection
    search_harrier = await gateway_client.post(
        f"/api/hubs/{hub.id}/ingestion/search",
        json={"query": "multidim vector test", "collection_id": col_harrier_id},
        headers=headers,
    )
    assert search_harrier.status_code == 200

    # Search 640-dim Harrier 270M collection
    search_640 = await gateway_client.post(
        f"/api/hubs/{hub.id}/ingestion/search",
        json={"query": "multidim vector test", "collection_id": col640_id},
        headers=headers,
    )
    assert search_640.status_code == 200
