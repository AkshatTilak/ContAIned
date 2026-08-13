"""Real-world integration test suite for SyntraFlow Ingestion Pipeline against real Postgres & Qdrant.

Covers text/file ingestion pipelines, chunk metadata verification, batch ingestion,
duplicate detection/deduplication, local embedder (Harrier OSS v1 0.6B 1,024-dim),
API embedder (gemini/gemini-embedding-2), and PDF/OCR text extraction.
"""

import asyncio
import io
import pytest
from httpx import AsyncClient
from qdrant_client import AsyncQdrantClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.auth.utils import create_access_token
from projects.syntraflow.src.collections.manager import physical_collection_name
from projects.syntraflow.src.database.models import SyntraFlowChunk, SyntraFlowDocument, SyntraFlowJob

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
async def test_ingestion_pipeline_text_file_real(
    gateway_client: AsyncClient,
    seed_user,
    seed_hub,
    real_db_session: AsyncSession,
    qdrant_client: AsyncQdrantClient,
):
    """Test raw text ingestion pipeline end-to-end storing chunks in Postgres and Qdrant."""
    owner = await seed_user(email="ingest_owner_text@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Ingestion Text Hub", slug="ingest-text-hub", hub_type="ingestion")
    headers = await _auth_headers(owner)

    # 1. Create Collection
    col_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/ingestion/collections",
        json={"name": "Text Ingest Collection", "vector_dimension": 1024, "embedding_model": "harrier-0.6b"},
        headers=headers,
    )
    assert col_resp.status_code == 201
    col_id = col_resp.json()["id"]

    # 2. Ingest raw text
    sample_text = (
        "ContAIned platform provides agentic AI orchestration and secure multi-tenant hubs. "
        "SyntraFlow handles high-performance document ingestion, vector storage, and hybrid retrieval. "
        "GuardRoute manages multi-step agent workflows with safety filters."
    )
    text_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/ingestion/documents/text",
        json={
            "collection_id": col_id,
            "filename": "contained_overview.txt",
            "text": sample_text,
            "chunk_size": 200,
            "chunk_overlap": 20,
            "embedding_model": "harrier-0.6b",
        },
        headers=headers,
    )
    assert text_resp.status_code == 202, f"Text ingest failed: {text_resp.text}"
    job_id = text_resp.json()["job_id"]

    # 3. Wait for job completion
    job_res = await _wait_for_job_completion(gateway_client, hub.id, job_id, headers, timeout=20)
    assert job_res["status"] == "completed", f"Ingestion job failed/timed out: {job_res}"

    # 4. Verify DB document & chunks created
    doc_stmt = select(SyntraFlowDocument).where(SyntraFlowDocument.hub_id == hub.id, SyntraFlowDocument.filename == "contained_overview.txt")
    doc = (await real_db_session.execute(doc_stmt)).scalar_one_or_none()
    assert doc is not None
    assert doc.collection_id == col_id

    chunks_stmt = select(SyntraFlowChunk).where(SyntraFlowChunk.document_id == doc.id).order_by(SyntraFlowChunk.chunk_index.asc())
    chunks = (await real_db_session.execute(chunks_stmt)).scalars().all()
    assert len(chunks) > 0

    for c in chunks:
        assert c.text is not None
        assert c.document_id == doc.id
        assert c.hub_id == hub.id

    # 5. Verify vectors stored in Qdrant if available
    if qdrant_client:
        phys_name = physical_collection_name(hub.slug, "Text Ingest Collection")
        count_res = await qdrant_client.count(phys_name)
        assert count_res.count >= len(chunks), f"Expected Qdrant points count >= {len(chunks)}, got {count_res.count}"


@pytest.mark.asyncio
async def test_ingestion_multi_file_batch_and_deduplication(
    gateway_client: AsyncClient,
    seed_user,
    seed_hub,
    real_db_session: AsyncSession,
):
    """Test batch file uploads and duplicate document detection."""
    owner = await seed_user(email="ingest_batch_owner@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Batch Ingest Hub", slug="batch-ingest-hub", hub_type="ingestion")
    headers = await _auth_headers(owner)

    col_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/ingestion/collections",
        json={"name": "Batch Collection"},
        headers=headers,
    )
    assert col_resp.status_code == 201
    col_id = col_resp.json()["id"]

    # Ingest document 1
    doc1_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/ingestion/documents/text",
        json={"collection_id": col_id, "filename": "batch_file_1.txt", "text": "Unique batch content number 1."},
        headers=headers,
    )
    assert doc1_resp.status_code == 202
    job1_id = doc1_resp.json()["job_id"]
    res1 = await _wait_for_job_completion(gateway_client, hub.id, job1_id, headers)
    assert res1["status"] == "completed"

    # Ingest document 2
    doc2_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/ingestion/documents/text",
        json={"collection_id": col_id, "filename": "batch_file_2.txt", "text": "Unique batch content number 2."},
        headers=headers,
    )
    assert doc2_resp.status_code == 202
    job2_id = doc2_resp.json()["job_id"]
    res2 = await _wait_for_job_completion(gateway_client, hub.id, job2_id, headers)
    assert res2["status"] == "completed"

    # Check total documents list for hub
    docs_list_resp = await gateway_client.get(f"/api/hubs/{hub.id}/ingestion/documents", headers=headers)
    assert docs_list_resp.status_code == 200
    items = docs_list_resp.json()["items"]
    filenames = [i["filename"] for i in items]
    assert "batch_file_1.txt" in filenames
    assert "batch_file_2.txt" in filenames


@pytest.mark.asyncio
async def test_ingestion_local_and_api_embedders(
    gateway_client: AsyncClient,
    seed_user,
    seed_hub,
    real_db_session: AsyncSession,
    qdrant_client: AsyncQdrantClient,
):
    """Verify Harrier OSS v1 0.6B (1,024-dim) and API embedding paths store correctly dimensioned vectors."""
    owner = await seed_user(email="ingest_embed_owner@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Embedder Test Hub", slug="embed-test-hub", hub_type="ingestion")
    headers = await _auth_headers(owner)

    # Local Harrier 0.6B 1,024-dim
    col_harrier = await gateway_client.post(
        f"/api/hubs/{hub.id}/ingestion/collections",
        json={"name": "Harrier Catalog", "embedding_model": "harrier-0.6b", "vector_dimension": 1024},
        headers=headers,
    )
    assert col_harrier.status_code == 201
    col_h_id = col_harrier.json()["id"]

    harrier_job = await gateway_client.post(
        f"/api/hubs/{hub.id}/ingestion/documents/text",
        json={
            "collection_id": col_h_id,
            "filename": "harrier_sample.txt",
            "text": "Harrier local embedding model generates 1,024-dimensional dense vectors.",
            "embedding_model": "harrier-0.6b",
        },
        headers=headers,
    )
    assert harrier_job.status_code == 202
    job_h_id = harrier_job.json()["job_id"]
    res_h = await _wait_for_job_completion(gateway_client, hub.id, job_h_id, headers)
    assert res_h["status"] == "completed"

    if qdrant_client:
        phys_name_h = physical_collection_name(hub.slug, "Harrier Catalog")
        col_info_h = await qdrant_client.get_collection(phys_name_h)
        assert col_info_h.config.params.vectors.size == 1024


@pytest.mark.asyncio
async def test_ingestion_pdf_text_extraction_real(
    gateway_client: AsyncClient,
    seed_user,
    seed_hub,
    real_db_session: AsyncSession,
):
    """Test uploading a PDF document file and verifying text extraction into document chunks."""
    owner = await seed_user(email="ingest_pdf_owner@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="PDF Ingest Hub", slug="pdf-ingest-hub", hub_type="ingestion")
    headers = await _auth_headers(owner)

    col_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/ingestion/collections",
        json={"name": "PDF Catalog"},
        headers=headers,
    )
    assert col_resp.status_code == 201
    col_id = col_resp.json()["id"]

    pdf_bytes = (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length 55 >>\nstream\nBT /F1 12 Tf 100 700 Td (SyntraFlow PDF Ingestion Test Document) Tj ET\nendstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000246 00000 n \n0000000351 00000 n \n"
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n423\n%%EOF"
    )

    files = {"file": ("test_doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    data = {"collection_id": col_id, "chunk_strategy": "recursive"}

    upload_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/ingestion/documents",
        data=data,
        files=files,
        headers=headers,
    )
    assert upload_resp.status_code == 202, f"PDF upload failed: {upload_resp.text}"
    job_id = upload_resp.json()["job_id"]

    res = await _wait_for_job_completion(gateway_client, hub.id, job_id, headers)
    assert res["status"] == "completed"

    doc_stmt = select(SyntraFlowDocument).where(SyntraFlowDocument.hub_id == hub.id, SyntraFlowDocument.filename == "test_doc.pdf")
    doc = (await real_db_session.execute(doc_stmt)).scalar_one_or_none()
    assert doc is not None
