"""Ingestion Hub REST API Routes (B6-04 / S6-04e).

All routes are nested under /hubs/{hub_id}/... and guarded by require_hub(hub_type="ingestion").
"""

import asyncio
import hashlib
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.clients.postgres import get_async_db
from common.models.database import AuditLog
from common.schemas.api import (
    CollectionResponse,
    DatastoreBindingResponse,
    IngestionJobResponse,
    SearchHit,
    SearchResponse,
)
from gateway.auth.hub_context import HubContext, require_hub
from projects.syntraflow.src.collections.manager import (
    CollectionManager,
    CollectionProvisioningError,
)
from projects.syntraflow.src.database.models import (
    SyntraFlowChunk,
    SyntraFlowDocument,
    SyntraFlowJob,
)
from projects.syntraflow.src.datastores.binding_manager import DatastoreBindingManager
from projects.syntraflow.src.ingestion.pipeline import (
    assert_collection_in_hub,
)
from projects.syntraflow.src.retrieval import RetrievalEngine

router = APIRouter(prefix="/hubs/{hub_id}/ingestion", tags=["ingestion-hub"])
logger = logging.getLogger("gateway.api.ingestion_hub")

# Upload constraints
MAX_DOC_SIZE = 100 * 1024 * 1024   # 100 MB
MAX_VIDEO_SIZE = 500 * 1024 * 1024 # 500 MB
MAX_AUDIO_SIZE = 200 * 1024 * 1024 # 200 MB

DOC_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".docx", ".pptx"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg"}


async def _log_audit_event(
    session: AsyncSession,
    *,
    hub_id: Optional[str],
    actor_user_id: Optional[str],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    summary: Optional[str] = None,
    before_json: Optional[Dict[str, Any]] = None,
    after_json: Optional[Dict[str, Any]] = None,
) -> None:
    audit = AuditLog(
        id=str(uuid.uuid4()),
        hub_id=hub_id,
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        summary=summary,
        before_json=before_json,
        after_json=after_json,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(audit)


# Request Payloads
class CreateDatastorePayload(BaseModel):
    name: str
    store_type: str
    connection_uri: str
    credentials: Optional[Dict[str, Any]] = None
    is_default: bool = False
    config: Optional[Dict[str, Any]] = None


class UpdateDatastorePayload(BaseModel):
    name: Optional[str] = None
    connection_uri: Optional[str] = None
    credentials: Optional[Dict[str, Any]] = None
    is_default: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None


class CreateCollectionPayload(BaseModel):
    name: str
    embedding_model: Optional[str] = "jina-clip-v2"
    vector_dimension: Optional[int] = 1024
    description: Optional[str] = None
    retrieval_config: Optional[Dict[str, Any]] = None
    datastore_binding_id: Optional[str] = None


class UpdateCollectionPayload(BaseModel):
    description: Optional[str] = None
    retrieval_config: Optional[Dict[str, Any]] = None
    datastore_binding_id: Optional[str] = None


class TextIngestPayload(BaseModel):
    collection_id: str
    text: str
    filename: str
    chunker_type: Optional[str] = "recursive"
    chunk_size: Optional[int] = 512
    chunk_overlap: Optional[int] = 64
    pre_processors: Optional[List[str]] = None
    post_processors: Optional[List[str]] = None


class SearchPayload(BaseModel):
    query: str
    collection_ids: Optional[List[str]] = None
    strategy: Optional[str] = None
    limit: Optional[int] = 5
    metadata_filter: Optional[Dict[str, Any]] = None


# --- Datastore Binding Routes ---

@router.get("/datastores", response_model=List[DatastoreBindingResponse])
async def list_datastores(
    store_type: Optional[str] = Query(None),
    ctx: HubContext = Depends(require_hub(hub_type="ingestion", min_role="viewer")),
    db: AsyncSession = Depends(get_async_db),
):
    """List datastore bindings for an ingestion hub."""
    manager = DatastoreBindingManager(db)
    return await manager.list_bindings(hub_id=ctx.hub_id, store_type=store_type)


@router.post("/datastores", response_model=DatastoreBindingResponse, status_code=status.HTTP_201_CREATED)
async def create_datastore(
    payload: CreateDatastorePayload,
    ctx: HubContext = Depends(require_hub(hub_type="ingestion", min_role="maintainer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Create a physical datastore binding for an ingestion hub."""
    manager = DatastoreBindingManager(db)
    try:
        binding = await manager.create_binding(
            hub_id=ctx.hub_id,
            name=payload.name,
            store_type=payload.store_type,
            connection_uri=payload.connection_uri,
            credentials=payload.credentials,
            is_default=payload.is_default,
            config=payload.config,
        )
        await _log_audit_event(
            db,
            hub_id=ctx.hub_id,
            actor_user_id=ctx.user_id,
            action="create",
            resource_type="datastore_binding",
            resource_id=binding.id,
            summary=f"Created {payload.store_type} datastore binding '{binding.name}'",
            after_json={"id": binding.id, "name": binding.name, "store_type": binding.store_type},
        )
        await db.commit()
        res = await manager.get_binding(hub_id=ctx.hub_id, binding_id=binding.id)
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        if "already exists" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        raise


@router.patch("/datastores/{binding_id}", response_model=DatastoreBindingResponse)
async def update_datastore(
    binding_id: str,
    payload: UpdateDatastorePayload,
    ctx: HubContext = Depends(require_hub(hub_type="ingestion", min_role="maintainer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Update a datastore binding."""
    manager = DatastoreBindingManager(db)
    try:
        fields = payload.model_dump(exclude_unset=True)
        res = await manager.update_binding(hub_id=ctx.hub_id, binding_id=binding_id, **fields)
        await _log_audit_event(
            db,
            hub_id=ctx.hub_id,
            actor_user_id=ctx.user_id,
            action="update",
            resource_type="datastore_binding",
            resource_id=binding_id,
            summary=f"Updated datastore binding '{binding_id}'",
        )
        await db.commit()
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/datastores/{binding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_datastore(
    binding_id: str,
    ctx: HubContext = Depends(require_hub(hub_type="ingestion", min_role="maintainer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Delete a datastore binding."""
    manager = DatastoreBindingManager(db)
    try:
        await manager.delete_binding(hub_id=ctx.hub_id, binding_id=binding_id)
        await _log_audit_event(
            db,
            hub_id=ctx.hub_id,
            actor_user_id=ctx.user_id,
            action="delete",
            resource_type="datastore_binding",
            resource_id=binding_id,
            summary=f"Deleted datastore binding '{binding_id}'",
        )
        await db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ValueError as e:
        if "in use" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/datastores/test")
async def test_datastore_draft(
    payload: CreateDatastorePayload,
    ctx: HubContext = Depends(require_hub(hub_type="ingestion", min_role="maintainer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Test connectivity for an unsaved datastore binding draft."""
    manager = DatastoreBindingManager(db)
    draft = payload.model_dump()
    res = await manager.test_connection(hub_id=ctx.hub_id, draft=draft)
    return res


@router.post("/datastores/{binding_id}/health")
async def test_datastore_health(
    binding_id: str,
    ctx: HubContext = Depends(require_hub(hub_type="ingestion", min_role="maintainer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Trigger an immediate health check on a datastore binding."""
    manager = DatastoreBindingManager(db)
    try:
        res = await manager.test_connection(hub_id=ctx.hub_id, binding_id=binding_id)
        await db.commit()
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# --- Collection Routes ---

@router.get("/collections", response_model=List[CollectionResponse])
async def list_collections(
    ctx: HubContext = Depends(require_hub(hub_type="ingestion", min_role="viewer")),
    db: AsyncSession = Depends(get_async_db),
):
    """List collections in an ingestion hub."""
    manager = CollectionManager(db)
    return await manager.list_collections(hub_id=ctx.hub_id)


@router.post("/collections", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_collection(
    payload: CreateCollectionPayload,
    ctx: HubContext = Depends(require_hub(hub_type="ingestion", min_role="contributor")),
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new collection in an ingestion hub."""
    manager = CollectionManager(db)
    try:
        col = await manager.create_collection(
            hub_id=ctx.hub_id,
            name=payload.name,
            embedding_model=payload.embedding_model or "jina-clip-v2",
            vector_dimension=payload.vector_dimension or 1024,
            description=payload.description,
            retrieval_config=payload.retrieval_config,
            datastore_binding_id=payload.datastore_binding_id,
        )
        await _log_audit_event(
            db,
            hub_id=ctx.hub_id,
            actor_user_id=ctx.user_id,
            action="create",
            resource_type="collection",
            resource_id=col.id,
            summary=f"Created collection '{col.name}' in hub",
        )
        await db.commit()
        return await manager.get_collection(hub_id=ctx.hub_id, collection_id=col.id)
    except ValueError as e:
        msg = str(e)
        if "already exists" in msg.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)
    except CollectionProvisioningError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/collections/{collection_id}", response_model=CollectionResponse)
async def get_collection_detail(
    collection_id: str,
    ctx: HubContext = Depends(require_hub(hub_type="ingestion", min_role="viewer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Get collection details by ID or friendly name."""
    manager = CollectionManager(db)
    col = await manager.get_collection(hub_id=ctx.hub_id, collection_id=collection_id)
    if not col:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    return col


@router.patch("/collections/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: str,
    payload: UpdateCollectionPayload,
    ctx: HubContext = Depends(require_hub(hub_type="ingestion", min_role="contributor")),
    db: AsyncSession = Depends(get_async_db),
):
    """Update collection metadata and retrieval config."""
    manager = CollectionManager(db)
    try:
        col = await manager.update_collection(
            hub_id=ctx.hub_id,
            collection_id=collection_id,
            description=payload.description,
            retrieval_config=payload.retrieval_config,
            datastore_binding_id=payload.datastore_binding_id,
        )
        await _log_audit_event(
            db,
            hub_id=ctx.hub_id,
            actor_user_id=ctx.user_id,
            action="update",
            resource_type="collection",
            resource_id=col.id,
            summary=f"Updated collection '{collection_id}'",
        )
        await db.commit()
        return await manager.get_collection(hub_id=ctx.hub_id, collection_id=col.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    collection_id: str,
    force: bool = Query(False),
    ctx: HubContext = Depends(require_hub(hub_type="ingestion", min_role="maintainer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Delete a collection."""
    manager = CollectionManager(db)
    try:
        await manager.delete_collection(hub_id=ctx.hub_id, collection_id=collection_id, force=force)
        await _log_audit_event(
            db,
            hub_id=ctx.hub_id,
            actor_user_id=ctx.user_id,
            action="delete",
            resource_type="collection",
            resource_id=collection_id,
            summary=f"Deleted collection '{collection_id}' (force={force})",
        )
        await db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ValueError as e:
        msg = str(e)
        if "not empty" in msg.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)


# --- Document & Ingestion Routes ---

def _sanitize_filename(name: str) -> str:
    """Sanitize filename preventing path traversal."""
    p = Path(name).name
    p = p.replace("..", "").replace("/", "").replace("\\", "")
    return p or "uploaded_file"


@router.post("/documents", status_code=status.HTTP_202_ACCEPTED)
async def ingest_document_file(
    collection_id: str = Form(...),
    file: UploadFile = File(None),
    filepath: Optional[str] = Form(None),
    chunk_strategy: Optional[str] = Form(None),
    chunk_size: Optional[int] = Form(None),
    chunk_overlap: Optional[int] = Form(None),
    ocr_cleanup: Optional[bool] = Form(None),
    lang_filter: Optional[bool] = Form(None),
    extract_metadata: Optional[bool] = Form(None),
    generate_summary: Optional[bool] = Form(None),
    ctx: HubContext = Depends(require_hub(hub_type="ingestion", min_role="contributor")),
    db: AsyncSession = Depends(get_async_db),
):
    """Ingest document file in hub."""
    # Assert collection belongs to hub
    collection = await assert_collection_in_hub(db, hub_id=ctx.hub_id, collection_id=collection_id)

    if not file and not filepath:
        raise HTTPException(status_code=400, detail="Must provide either 'file' upload or 'filepath'")

    if file:
        filename = _sanitize_filename(file.filename)
        file_bytes = await file.read()
    else:
        if ".." in filepath or os.path.isabs(filepath) is False:
            pass # local path allowed if valid file
        if not os.path.exists(filepath):
            raise HTTPException(status_code=400, detail=f"File not found: {filepath}")
        filename = _sanitize_filename(os.path.basename(filepath))
        with open(filepath, "rb") as f:
            file_bytes = f.read()

    file_hash = hashlib.sha256(file_bytes).hexdigest()

    # Save to hub upload path
    temp_dir = Path("projects/syntraflow/temp_uploads") / ctx.hub_id
    temp_dir.mkdir(parents=True, exist_ok=True)

    job = SyntraFlowJob(
        id=uuid.uuid4(),
        hub_id=ctx.hub_id,
        collection_id=collection.id,
        status="queued",
        progress=0.0,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    temp_filepath = str(temp_dir / f"{job.id}_{filename}")
    with open(temp_filepath, "wb") as f:
        f.write(file_bytes)

    pre_procs = []
    if ocr_cleanup:
        pre_procs.append("ocr_cleanup")
    if lang_filter:
        pre_procs.append("language_filter")

    post_procs = []
    if extract_metadata:
        post_procs.append("metadata_extractor")
    if generate_summary:
        post_procs.append("summary_gen")

    from projects.syntraflow.src.worker import process_ingestion_job
    asyncio.create_task(
        process_ingestion_job(
            job_id=str(job.id),
            file_hash=file_hash,
            filename=filename,
            temp_filepath=temp_filepath,
            hub_id=ctx.hub_id,
            collection_id=collection.id,
            chunker_type=chunk_strategy,
            chunk_size=chunk_size or 512,
            chunk_overlap=chunk_overlap or 64,
            pre_processors=pre_procs,
            post_processors=post_procs,
        )
    )

    await _log_audit_event(
        db,
        hub_id=ctx.hub_id,
        actor_user_id=ctx.user_id,
        action="ingest",
        resource_type="document",
        resource_id=str(job.id),
        summary=f"Ingested file '{filename}' into collection '{collection.name}'",
    )
    await db.commit()

    return {"status": "queued", "job_id": str(job.id), "filename": filename}


@router.post("/documents/text", status_code=status.HTTP_202_ACCEPTED)
async def ingest_raw_text(
    payload: TextIngestPayload,
    ctx: HubContext = Depends(require_hub(hub_type="ingestion", min_role="contributor")),
    db: AsyncSession = Depends(get_async_db),
):
    """Ingest raw text content into a collection."""
    collection = await assert_collection_in_hub(db, hub_id=ctx.hub_id, collection_id=payload.collection_id)

    file_bytes = payload.text.encode("utf-8")
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    temp_dir = Path("projects/syntraflow/temp_uploads") / ctx.hub_id
    temp_dir.mkdir(parents=True, exist_ok=True)

    job = SyntraFlowJob(
        id=uuid.uuid4(),
        hub_id=ctx.hub_id,
        collection_id=collection.id,
        status="queued",
        progress=0.0,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    filename = _sanitize_filename(payload.filename)
    temp_filepath = str(temp_dir / f"{job.id}_{filename}")
    with open(temp_filepath, "wb") as f:
        f.write(file_bytes)

    from projects.syntraflow.src.worker import process_ingestion_job
    asyncio.create_task(
        process_ingestion_job(
            job_id=str(job.id),
            file_hash=file_hash,
            filename=filename,
            temp_filepath=temp_filepath,
            hub_id=ctx.hub_id,
            collection_id=collection.id,
            chunker_type=payload.chunker_type,
            chunk_size=payload.chunk_size or 512,
            chunk_overlap=payload.chunk_overlap or 64,
            pre_processors=payload.pre_processors,
            post_processors=payload.post_processors,
        )
    )

    await _log_audit_event(
        db,
        hub_id=ctx.hub_id,
        actor_user_id=ctx.user_id,
        action="ingest_text",
        resource_type="document",
        resource_id=str(job.id),
        summary=f"Ingested raw text '{filename}' into collection '{collection.name}'",
    )
    await db.commit()

    return {"status": "queued", "job_id": str(job.id), "filename": filename}


@router.get("/documents", response_model=Dict[str, Any])
async def list_documents(
    collection_id: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    ctx: HubContext = Depends(require_hub(hub_type="ingestion", min_role="viewer")),
    db: AsyncSession = Depends(get_async_db),
):
    """List documents in hub with optional collection filter."""
    total_query = select(func.count()).select_from(SyntraFlowDocument).where(SyntraFlowDocument.hub_id == ctx.hub_id)
    query = select(SyntraFlowDocument).where(SyntraFlowDocument.hub_id == ctx.hub_id)

    if collection_id:
        total_query = total_query.where(SyntraFlowDocument.collection_id == collection_id)
        query = query.where(SyntraFlowDocument.collection_id == collection_id)

    total_res = await db.execute(total_query)
    total_count = total_res.scalar() or 0

    query = query.order_by(SyntraFlowDocument.created_at.desc()).offset(offset).limit(limit)
    docs = (await db.execute(query)).scalars().all()

    items = [
        {
            "id": str(doc.id),
            "hub_id": doc.hub_id,
            "collection_id": doc.collection_id,
            "filename": doc.filename,
            "file_hash": doc.file_hash,
            "file_type": doc.filename.split(".")[-1] if "." in doc.filename else "unknown",
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
        }
        for doc in docs
    ]

    return {
        "status": "success",
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


@router.get("/documents/{doc_id}/chunks")
async def get_document_chunks(
    doc_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    ctx: HubContext = Depends(require_hub(hub_type="ingestion", min_role="viewer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Get chunks for a document inside the hub."""
    try:
        doc_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format.")

    # Verify doc belongs to hub
    doc_stmt = select(SyntraFlowDocument).where(
        SyntraFlowDocument.id == doc_uuid, SyntraFlowDocument.hub_id == ctx.hub_id
    )
    doc = (await db.execute(doc_stmt)).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    total_stmt = (
        select(func.count())
        .select_from(SyntraFlowChunk)
        .where(SyntraFlowChunk.document_id == doc_uuid, SyntraFlowChunk.hub_id == ctx.hub_id)
    )
    total_count = (await db.execute(total_stmt)).scalar() or 0

    chunk_stmt = (
        select(SyntraFlowChunk)
        .where(SyntraFlowChunk.document_id == doc_uuid, SyntraFlowChunk.hub_id == ctx.hub_id)
        .order_by(SyntraFlowChunk.chunk_index.asc())
        .offset(offset)
        .limit(limit)
    )
    chunks = (await db.execute(chunk_stmt)).scalars().all()

    items = [
        {
            "id": str(c.id),
            "document_id": str(c.document_id),
            "chunk_index": c.chunk_index,
            "text": c.text,
            "token_count": c.token_count,
            "metadata": c.metadata_json,
        }
        for c in chunks
    ]

    return {
        "status": "success",
        "document_id": doc_id,
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


@router.delete("/documents/{doc_id}", status_code=status.HTTP_200_OK)
async def delete_document(
    doc_id: str,
    ctx: HubContext = Depends(require_hub(hub_type="ingestion", min_role="maintainer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Cascade delete document and related chunks / vectors in hub."""
    try:
        doc_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format.")

    doc_stmt = select(SyntraFlowDocument).where(
        SyntraFlowDocument.id == doc_uuid, SyntraFlowDocument.hub_id == ctx.hub_id
    )
    doc = (await db.execute(doc_stmt)).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    await db.delete(doc)
    await _log_audit_event(
        db,
        hub_id=ctx.hub_id,
        actor_user_id=ctx.user_id,
        action="delete",
        resource_type="document",
        resource_id=doc_id,
        summary=f"Deleted document '{doc.filename}'",
    )
    await db.commit()

    return {"status": "success", "message": f"Document {doc_id} deleted."}


# --- Job Routes ---

@router.get("/jobs")
async def list_jobs(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    ctx: HubContext = Depends(require_hub(hub_type="ingestion", min_role="viewer")),
    db: AsyncSession = Depends(get_async_db),
):
    """List ingestion jobs in hub."""
    total_query = select(func.count()).select_from(SyntraFlowJob).where(SyntraFlowJob.hub_id == ctx.hub_id)
    query = select(SyntraFlowJob).where(SyntraFlowJob.hub_id == ctx.hub_id)

    if status_filter:
        total_query = total_query.where(SyntraFlowJob.status == status_filter)
        query = query.where(SyntraFlowJob.status == status_filter)

    total_count = (await db.execute(total_query)).scalar() or 0
    jobs = (await db.execute(query.order_by(SyntraFlowJob.created_at.desc()).offset(offset).limit(limit))).scalars().all()

    items = [
        {
            "job_id": str(j.id),
            "hub_id": j.hub_id,
            "collection_id": j.collection_id,
            "document_id": str(j.document_id) if j.document_id else None,
            "status": j.status,
            "progress": j.progress,
            "error_msg": j.error_msg,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "updated_at": j.updated_at.isoformat() if j.updated_at else None,
        }
        for j in jobs
    ]

    return {
        "status": "success",
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


@router.get("/jobs/{job_id}", response_model=IngestionJobResponse)
async def get_job_status(
    job_id: str,
    ctx: HubContext = Depends(require_hub(hub_type="ingestion", min_role="viewer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Get ingestion job status in hub."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format.")

    stmt = select(SyntraFlowJob).where(
        SyntraFlowJob.id == job_uuid, SyntraFlowJob.hub_id == ctx.hub_id
    )
    job = (await db.execute(stmt)).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    return IngestionJobResponse(
        job_id=str(job.id),
        hub_id=job.hub_id,
        collection_id=job.collection_id,
        document_id=str(job.document_id) if job.document_id else None,
        status=job.status,
        progress=job.progress,
        error_msg=job.error_msg,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


# --- Search Route ---

@router.post("/search", response_model=SearchResponse)
async def search_hub(
    payload: SearchPayload,
    ctx: HubContext = Depends(require_hub(hub_type="ingestion", min_role="viewer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Issue a multi-collection or hybrid search within an ingestion hub."""
    engine = RetrievalEngine(db, ctx.hub_id)
    try:
        hits = await engine.search(
            query=payload.query,
            collection_ids=payload.collection_ids,
            strategy=payload.strategy,
            limit=payload.limit or 5,
            metadata_filter=payload.metadata_filter,
        )

        formatted_hits = [
            SearchHit(
                id=h.get("id", str(uuid.uuid4())),
                hub_id=h.get("hub_id", ctx.hub_id),
                collection_id=h.get("collection_id", ""),
                collection_name=h.get("collection_name"),
                document_id=h.get("document_id"),
                score=float(h.get("score", 0.0)),
                text=h.get("text", ""),
                metadata=h.get("metadata", {}),
            )
            for h in hits
        ]

        return SearchResponse(
            status="success",
            query=payload.query,
            count=len(formatted_hits),
            results=formatted_hits,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        if "unreachable" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
        logger.error("Search failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
