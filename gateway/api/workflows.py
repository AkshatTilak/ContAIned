"""Workflow Hub REST API Routes (S6-06e).

All routes are nested under /hubs/{hub_id}/workflows and guarded by require_hub(hub_type="workflow").
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.clients.postgres import get_async_db
from common.models.database import AuditLog, EvalFlowTrace
from common.services.audit import sanitize_actor_user_id
from common.schemas.workflows import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowSummary,
    WorkflowDetail,
    WorkflowVersionSummary,
    WorkflowVersionDetail,
    ValidationResult,
    WorkflowRunSummary,
    WorkflowRunDetail,
)
from gateway.auth.hub_context import HubContext, require_hub
from projects.guardroute.src.workflows import (
    version_service,
    run_service,
    portability,
)
from projects.guardroute.src.core.graph_parser import validate_workflow_graph

router = APIRouter(prefix="/hubs/{hub_id}/workflows", tags=["workflow-hub"])
logger = logging.getLogger("gateway.api.workflows")


class WorkflowRunRequest(BaseModel):
    """Execution request payload."""
    input: Dict[str, Any] = Field(default_factory=dict)
    use_draft: bool = False
    stream: bool = True
    timeout_s: int = 300


class ImportRequest(BaseModel):
    """Import workflow request payload."""
    document: Dict[str, Any]
    mapping: Optional[Dict[str, str]] = None
    name_override: Optional[str] = None


class DuplicateRequest(BaseModel):
    """Duplicate workflow request payload."""
    target_hub_id: Optional[str] = None
    name_override: Optional[str] = None


async def _log_audit_event(
    session: AsyncSession,
    *,
    hub_id: str,
    actor_user_id: Optional[str],
    action: str,
    resource_id: Optional[str] = None,
    summary: Optional[str] = None,
    before_json: Optional[Dict[str, Any]] = None,
    after_json: Optional[Dict[str, Any]] = None,
) -> None:
    """Helper writing audit log entries for mutating workflow operations."""
    valid_actor_id = await sanitize_actor_user_id(session, actor_user_id)
    audit = AuditLog(
        id=str(uuid.uuid4()),
        hub_id=hub_id,
        actor_user_id=valid_actor_id,
        action=action,
        resource_type="workflow",
        resource_id=resource_id,
        summary=summary,
        before_json=before_json,
        after_json=after_json,
    )
    session.add(audit)


# --- Workflow Routes ---

@router.get("", response_model=List[WorkflowSummary])
async def list_workflows(
    q: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    ctx: HubContext = Depends(require_hub(hub_type="workflow", min_role="viewer")),
    db: AsyncSession = Depends(get_async_db),
):
    """List workflows within the hub."""
    return await version_service.list_workflows(
        db,
        hub_id=ctx.hub.id,
        q=q,
        tag=tag,
        status=status_filter,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=WorkflowDetail, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    payload: WorkflowCreate,
    ctx: HubContext = Depends(require_hub(hub_type="workflow", min_role="contributor")),
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new workflow definition with draft v1."""
    try:
        wf = await version_service.create_workflow(
            db,
            hub_id=ctx.hub.id,
            payload=payload,
            actor_id=ctx.user_id,
        )
        await _log_audit_event(
            db,
            hub_id=ctx.hub.id,
            actor_user_id=ctx.user_id,
            action="workflow_create",
            resource_id=wf.id,
            summary=f"Created workflow '{wf.name}'",
            after_json={"name": wf.name, "slug": wf.slug},
        )
        await db.commit()
        return wf
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error": {"code": "WORKFLOW_SLUG_TAKEN", "message": str(e)}})


@router.get("/templates", response_model=List[Dict[str, Any]])
async def list_templates(
    ctx: HubContext = Depends(require_hub(hub_type="workflow", min_role="viewer")),
):
    """List seed workflow templates."""
    return await portability.list_templates()


@router.post("/templates/{key}/instantiate", response_model=WorkflowDetail, status_code=status.HTTP_201_CREATED)
async def instantiate_template(
    key: str,
    mapping: Optional[Dict[str, str]] = None,
    ctx: HubContext = Depends(require_hub(hub_type="workflow", min_role="contributor")),
    db: AsyncSession = Depends(get_async_db),
):
    """Instantiate a workflow from a template."""
    try:
        wf = await portability.instantiate_template(
            db,
            target_hub_id=ctx.hub.id,
            template_key=key,
            actor_id=ctx.user_id,
            mapping=mapping,
        )
        await _log_audit_event(
            db,
            hub_id=ctx.hub.id,
            actor_user_id=ctx.user_id,
            action="workflow_instantiate_template",
            resource_id=wf.id,
            summary=f"Instantiated template '{key}' as workflow '{wf.name}'",
        )
        await db.commit()
        return await version_service.get_workflow(db, hub_id=ctx.hub.id, workflow_id=wf.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": {"code": "INVALID_TEMPLATE", "message": str(e)}})


@router.post("/import", response_model=WorkflowDetail, status_code=status.HTTP_201_CREATED)
async def import_workflow(
    request: Request,
    payload: ImportRequest,
    ctx: HubContext = Depends(require_hub(hub_type="workflow", min_role="contributor")),
    db: AsyncSession = Depends(get_async_db),
):
    """Import a workflow JSON document."""
    body_bytes = await request.body()
    if len(body_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail={"error": {"code": "IMPORT_TOO_LARGE", "message": "Import payload exceeds 5MB limit."}})

    try:
        wf = await portability.import_workflow(
            db,
            target_hub_id=ctx.hub.id,
            document=payload.document,
            actor_id=ctx.user_id,
            mapping=payload.mapping,
            name_override=payload.name_override,
        )
        await _log_audit_event(
            db,
            hub_id=ctx.hub.id,
            actor_user_id=ctx.user_id,
            action="workflow_import",
            resource_id=wf.id,
            summary=f"Imported workflow '{wf.name}'",
        )
        await db.commit()
        return await version_service.get_workflow(db, hub_id=ctx.hub.id, workflow_id=wf.id)
    except ValueError as e:
        err_msg = str(e)
        if "UNSUPPORTED_EXPORT_FORMAT" in err_msg:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"error": {"code": "UNSUPPORTED_EXPORT_FORMAT", "message": err_msg}})
        if "IMPORT_UNRESOLVED_REFERENCES" in err_msg:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"error": {"code": "IMPORT_UNRESOLVED_REFERENCES", "message": err_msg}})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": {"code": "IMPORT_FAILED", "message": err_msg}})


@router.get("/{wf_id}", response_model=WorkflowDetail)
async def get_workflow(
    wf_id: str,
    ctx: HubContext = Depends(require_hub(hub_type="workflow", min_role="viewer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Fetch workflow metadata & version details."""
    try:
        return await version_service.get_workflow(db, hub_id=ctx.hub.id, workflow_id=wf_id)
    except version_service.WorkflowNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "WORKFLOW_NOT_FOUND", "message": f"Workflow '{wf_id}' not found."}})


@router.patch("/{wf_id}", response_model=WorkflowDetail)
async def update_workflow(
    wf_id: str,
    payload: WorkflowUpdate,
    ctx: HubContext = Depends(require_hub(hub_type="workflow", min_role="contributor")),
    db: AsyncSession = Depends(get_async_db),
):
    """Update workflow metadata (name, description, tags, slug)."""
    try:
        before_wf = await version_service.get_workflow(db, hub_id=ctx.hub.id, workflow_id=wf_id)
        wf = await version_service.update_workflow(db, hub_id=ctx.hub.id, workflow_id=wf_id, payload=payload)
        await _log_audit_event(
            db,
            hub_id=ctx.hub.id,
            actor_user_id=ctx.user_id,
            action="workflow_update",
            resource_id=wf.id,
            summary=f"Updated workflow '{wf.name}'",
            before_json={"name": before_wf.name, "slug": before_wf.slug},
            after_json={"name": wf.name, "slug": wf.slug},
        )
        await db.commit()
        return wf
    except version_service.WorkflowNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "WORKFLOW_NOT_FOUND", "message": f"Workflow '{wf_id}' not found."}})
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error": {"code": "WORKFLOW_SLUG_TAKEN", "message": str(e)}})


@router.delete("/{wf_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    wf_id: str,
    ctx: HubContext = Depends(require_hub(hub_type="workflow", min_role="maintainer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Delete a workflow definition and all associated versions & runs."""
    try:
        wf = await version_service.get_workflow(db, hub_id=ctx.hub.id, workflow_id=wf_id)
        await version_service.delete_workflow(db, hub_id=ctx.hub.id, workflow_id=wf_id)
        await _log_audit_event(
            db,
            hub_id=ctx.hub.id,
            actor_user_id=ctx.user_id,
            action="workflow_delete",
            resource_id=wf_id,
            summary=f"Deleted workflow '{wf.name}'",
        )
        await db.commit()
    except version_service.WorkflowNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "WORKFLOW_NOT_FOUND", "message": f"Workflow '{wf_id}' not found."}})


@router.post("/{wf_id}/duplicate", response_model=WorkflowDetail, status_code=status.HTTP_201_CREATED)
async def duplicate_workflow(
    wf_id: str,
    payload: DuplicateRequest = DuplicateRequest(),
    ctx: HubContext = Depends(require_hub(hub_type="workflow", min_role="contributor")),
    db: AsyncSession = Depends(get_async_db),
):
    """Duplicate workflow inside the hub or to another hub."""
    try:
        wf = await version_service.duplicate(
            db,
            source_hub_id=ctx.hub.id,
            workflow_id=wf_id,
            target_hub_id=payload.target_hub_id or ctx.hub.id,
            actor_id=ctx.user_id,
            name_override=payload.name_override,
        )
        await _log_audit_event(
            db,
            hub_id=payload.target_hub_id or ctx.hub.id,
            actor_user_id=ctx.user_id,
            action="workflow_duplicate",
            resource_id=wf.id,
            summary=f"Duplicated workflow '{wf.name}'",
        )
        await db.commit()
        return wf
    except version_service.WorkflowNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "WORKFLOW_NOT_FOUND", "message": f"Workflow '{wf_id}' not found."}})


@router.get("/{wf_id}/versions", response_model=List[WorkflowVersionSummary])
async def list_versions(
    wf_id: str,
    ctx: HubContext = Depends(require_hub(hub_type="workflow", min_role="viewer")),
    db: AsyncSession = Depends(get_async_db),
):
    """List version history for a workflow."""
    try:
        return await version_service.list_versions(db, hub_id=ctx.hub.id, workflow_id=wf_id)
    except version_service.WorkflowNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "WORKFLOW_NOT_FOUND", "message": f"Workflow '{wf_id}' not found."}})


@router.get("/{wf_id}/versions/{v}", response_model=WorkflowVersionDetail)
async def get_version(
    wf_id: str,
    v: int,
    ctx: HubContext = Depends(require_hub(hub_type="workflow", min_role="viewer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Fetch full details and graph JSON for a specific version number."""
    try:
        return await version_service.get_version(db, hub_id=ctx.hub.id, workflow_id=wf_id, version_number=v)
    except version_service.WorkflowNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "WORKFLOW_NOT_FOUND", "message": f"Workflow '{wf_id}' not found."}})
    except version_service.VersionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "VERSION_NOT_FOUND", "message": f"Version '{v}' not found."}})


@router.get("/{wf_id}/draft", response_model=WorkflowVersionDetail)
async def get_draft(
    wf_id: str,
    response: Response,
    ctx: HubContext = Depends(require_hub(hub_type="workflow", min_role="viewer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Fetch draft version with ETag response header."""
    try:
        draft = await version_service.get_draft(db, hub_id=ctx.hub.id, workflow_id=wf_id)
        etag = version_service.compute_etag(draft)
        response.headers["ETag"] = etag
        return draft
    except version_service.WorkflowNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "WORKFLOW_NOT_FOUND", "message": f"Workflow '{wf_id}' not found."}})


@router.put("/{wf_id}/draft", response_model=WorkflowVersionDetail)
async def update_draft(
    wf_id: str,
    graph: Dict[str, Any],
    response: Response,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    ctx: HubContext = Depends(require_hub(hub_type="workflow", min_role="contributor")),
    db: AsyncSession = Depends(get_async_db),
):
    """Update draft graph with If-Match optimistic locking."""
    try:
        wf = await version_service.get_workflow(db, hub_id=ctx.hub.id, workflow_id=wf_id)
        if wf.published_version_id and not if_match:
            raise HTTPException(status_code=status.HTTP_428_PRECONDITION_REQUIRED, detail={"error": {"code": "ETAG_REQUIRED", "message": "If-Match header is required when updating a published workflow's draft."}})

        res = await version_service.update_draft(
            db,
            hub_id=ctx.hub.id,
            workflow_id=wf_id,
            graph=graph,
            expected_etag=if_match,
            actor_id=ctx.user_id,
        )
        response.headers["ETag"] = res.etag
        return res.version
    except version_service.WorkflowNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "WORKFLOW_NOT_FOUND", "message": f"Workflow '{wf_id}' not found."}})
    except version_service.DraftConflict as conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "VERSION_CONFLICT",
                    "message": "Draft conflict: graph has been modified by another editor.",
                    "server_etag": conflict.server_etag,
                    "server_version_number": conflict.server_version_number,
                    "server_graph": conflict.server_graph,
                    "updated_by": conflict.updated_by,
                    "updated_at": conflict.updated_at.isoformat() if conflict.updated_at else None,
                }
            },
        )


@router.post("/{wf_id}/publish", response_model=WorkflowDetail)
async def publish_workflow(
    wf_id: str,
    ctx: HubContext = Depends(require_hub(hub_type="workflow", min_role="contributor")),
    db: AsyncSession = Depends(get_async_db),
):
    """Publish draft graph as immutable published version."""
    try:
        ver = await version_service.publish(db, hub_id=ctx.hub.id, workflow_id=wf_id, actor_id=ctx.user_id)
        wf = await version_service.get_workflow(db, hub_id=ctx.hub.id, workflow_id=wf_id)
        await _log_audit_event(
            db,
            hub_id=ctx.hub.id,
            actor_user_id=ctx.user_id,
            action="workflow_publish",
            resource_id=wf.id,
            summary=f"Published workflow '{wf.name}' as version {ver.version_number}",
        )
        await db.commit()
        return wf
    except version_service.WorkflowNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "WORKFLOW_NOT_FOUND", "message": f"Workflow '{wf_id}' not found."}})
    except Exception as e:
        err_str = str(e)
        if "GRAPH_INVALID" in err_str:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"error": {"code": "GRAPH_INVALID", "message": err_str}})
        raise e


@router.post("/{wf_id}/versions/{v}/restore", response_model=WorkflowVersionDetail)
async def restore_version(
    wf_id: str,
    v: int,
    ctx: HubContext = Depends(require_hub(hub_type="workflow", min_role="contributor")),
    db: AsyncSession = Depends(get_async_db),
):
    """Restore a historic version as the active draft."""
    try:
        draft = await version_service.restore(db, hub_id=ctx.hub.id, workflow_id=wf_id, version_number=v, actor_id=ctx.user_id)
        await _log_audit_event(
            db,
            hub_id=ctx.hub.id,
            actor_user_id=ctx.user_id,
            action="workflow_restore",
            resource_id=wf_id,
            summary=f"Restored version {v} as active draft",
        )
        await db.commit()
        return draft
    except version_service.WorkflowNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "WORKFLOW_NOT_FOUND", "message": f"Workflow '{wf_id}' not found."}})
    except version_service.VersionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "VERSION_NOT_FOUND", "message": f"Version '{v}' not found."}})


@router.get("/{wf_id}/diff")
async def diff_versions(
    wf_id: str,
    base: int = Query(...),
    head: int = Query(...),
    ctx: HubContext = Depends(require_hub(hub_type="workflow", min_role="viewer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Compare graph topology between base and head versions."""
    try:
        return await version_service.diff_versions(db, hub_id=ctx.hub.id, workflow_id=wf_id, base_version=base, head_version=head)
    except version_service.WorkflowNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "WORKFLOW_NOT_FOUND", "message": f"Workflow '{wf_id}' not found."}})


class WorkflowValidatePayload(BaseModel):
    """Payload for validating graph payload (supports nested graph key or direct nodes/edges)."""
    graph: Optional[Dict[str, Any]] = None
    nodes: Optional[List[Dict[str, Any]]] = None
    edges: Optional[List[Dict[str, Any]]] = None


@router.post("/{wf_id}/validate", response_model=ValidationResult)
async def validate_workflow(
    wf_id: str,
    payload: Optional[WorkflowValidatePayload] = Body(None),
    ctx: HubContext = Depends(require_hub(hub_type="workflow", min_role="viewer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Validate workflow graph payload without modifying draft state."""
    graph = None
    if payload:
        if payload.graph:
            graph = payload.graph
        elif payload.nodes is not None or payload.edges is not None:
            graph = {"nodes": payload.nodes or [], "edges": payload.edges or []}

    if not graph:
        draft = await version_service.get_draft(db, hub_id=ctx.hub.id, workflow_id=wf_id)
        graph = draft.graph_json or {}

    res = await validate_workflow_graph(db, graph_json=graph, source_hub_id=ctx.hub.id, strict=False)
    if isinstance(res, ValidationResult):
        return res
    if hasattr(res, "errors"):
        return ValidationResult(is_valid=getattr(res, "is_valid", True), errors=getattr(res, "errors", []))
    if isinstance(res, tuple):
        is_v, errs = res
        return ValidationResult(is_valid=is_v, errors=errs if isinstance(errs, list) else [])
    return res


@router.post("/{wf_id}/run")
@router.post("/{wf_id}/runs")
async def run_workflow(
    wf_id: str,
    payload: WorkflowRunRequest,
    ctx: HubContext = Depends(require_hub(hub_type="workflow", min_role="contributor")),
    db: AsyncSession = Depends(get_async_db),
):
    """Execute workflow version and stream SSE output or return 202 Queued."""
    try:
        run = await run_service.start_run(
            db,
            hub_id=ctx.hub.id,
            workflow_id=wf_id,
            input_json=payload.input,
            trigger="manual",
            started_by=ctx.user_id,
            use_draft=payload.use_draft,
            timeout_s=payload.timeout_s,
        )

        if payload.stream:
            async def _sse_generator():
                async for evt in run_service.stream_run(run.id):
                    yield f"event: {evt['event']}\ndata: {json.dumps(evt['data'])}\n\n"

            return StreamingResponse(
                _sse_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                    "X-Run-Id": run.id,
                },
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content={"run_id": run.id, "status": "queued"},
            )
    except run_service.WorkflowNotPublishedError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error": {"code": "WORKFLOW_NOT_PUBLISHED", "message": f"Workflow '{wf_id}' is not published."}})
    except run_service.WorkflowNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "WORKFLOW_NOT_FOUND", "message": f"Workflow '{wf_id}' not found."}})


@router.get("/{wf_id}/runs", response_model=List[WorkflowRunSummary])
async def list_runs(
    wf_id: str,
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    ctx: HubContext = Depends(require_hub(hub_type="workflow", min_role="viewer")),
    db: AsyncSession = Depends(get_async_db),
):
    """List execution runs for a workflow."""
    return await run_service.list_runs(
        db,
        hub_id=ctx.hub.id,
        workflow_id=wf_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )


@router.get("/{wf_id}/runs/{run_id}", response_model=WorkflowRunDetail)
async def get_run(
    wf_id: str,
    run_id: str,
    ctx: HubContext = Depends(require_hub(hub_type="workflow", min_role="viewer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Fetch detail for a specific workflow run."""
    try:
        return await run_service.get_run(db, hub_id=ctx.hub.id, run_id=run_id)
    except run_service.RunNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "RUN_NOT_FOUND", "message": f"Run '{run_id}' not found."}})


@router.get("/{wf_id}/runs/{run_id}/stream")
async def stream_run_events(
    wf_id: str,
    run_id: str,
    ctx: HubContext = Depends(require_hub(hub_type="workflow", min_role="viewer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Stream real-time SSE execution events for a workflow run."""
    try:
        await run_service.get_run(db, hub_id=ctx.hub.id, run_id=run_id)
    except run_service.RunNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "RUN_NOT_FOUND", "message": f"Run '{run_id}' not found."}})

    async def _sse_generator():
        async for evt in run_service.stream_run(run_id):
            yield f"event: {evt['event']}\ndata: {json.dumps(evt['data'])}\n\n"

    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "X-Run-Id": run_id,
        },
    )


@router.post("/{wf_id}/runs/{run_id}/cancel", response_model=WorkflowRunDetail)
async def cancel_run(
    wf_id: str,
    run_id: str,
    ctx: HubContext = Depends(require_hub(hub_type="workflow", min_role="contributor")),
    db: AsyncSession = Depends(get_async_db),
):
    """Cancel a running workflow execution."""
    try:
        run = await run_service.cancel_run(db, hub_id=ctx.hub.id, run_id=run_id, actor_id=ctx.user_id)
        return WorkflowRunDetail.model_validate(run)
    except run_service.RunNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "RUN_NOT_FOUND", "message": f"Run '{run_id}' not found."}})
    except run_service.RunNotCancellableError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error": {"code": "RUN_NOT_CANCELLABLE", "message": str(e)}})


@router.get("/{wf_id}/runs/{run_id}/traces")
async def get_run_traces(
    wf_id: str,
    run_id: str,
    include_state: bool = Query(False),
    ctx: HubContext = Depends(require_hub(hub_type="workflow", min_role="viewer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Fetch execution traces for a workflow run."""
    stmt = (
        select(EvalFlowTrace)
        .where(
            EvalFlowTrace.hub_id == ctx.hub.id,
            EvalFlowTrace.run_id == run_id,
        )
        .order_by(EvalFlowTrace.sequence.asc(), EvalFlowTrace.timestamp.asc())
    )
    traces = (await db.execute(stmt)).scalars().all()
    results = []
    for t in traces:
        item = {
            "id": t.id,
            "node_id": t.node_id,
            "node_type": t.node_type,
            "sequence": t.sequence,
            "latency_ms": t.latency_ms,
            "timestamp": t.timestamp.isoformat() if t.timestamp else None,
        }
        if include_state:
            item["input_state"] = t.input_state
            item["output_state"] = t.output_state
        results.append(item)
    return results


@router.get("/{wf_id}/export")
async def export_workflow(
    wf_id: str,
    version_number: Optional[int] = Query(None, alias="v"),
    ctx: HubContext = Depends(require_hub(hub_type="workflow", min_role="viewer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Export workflow to JSON document attachment."""
    try:
        data = await portability.export_workflow(
            db,
            hub_id=ctx.hub.id,
            workflow_id=wf_id,
            version_number=version_number,
        )
        slug = data.get("workflow", {}).get("slug", "workflow")
        vn = data.get("version", {}).get("version_number", 1)
        filename = f"{slug}-v{vn}.workflow.json"
        return Response(
            content=json.dumps(data, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "EXPORT_FAILED", "message": str(e)}})
