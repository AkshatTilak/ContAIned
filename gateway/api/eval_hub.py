"""Eval Hub API routes (S6-07e).

Mounted at /api/hubs/{hub_id}/eval/* and guarded by require_hub(hub_type="eval").
Delegates all operations to projects.evalops services.
"""

import logging
import uuid
from typing import Any, Dict, List, Literal, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.clients.postgres import get_async_db
from common.models.database import EvalMetricResult, EvalRunHistory, HubLink, AgentDefinition, WorkflowDefinition
from common.schemas.evalops import (
    EvalRunRequest,
    EvalRunResponse,
    EvalSuiteCreate,
    EvalSuiteResponse,
    EvalSuiteUpdate,
    EvalTarget,
    EvalTestCaseCreate,
    EvalTestCaseResponse,
)
from common.services import hub_resolver
from gateway.auth.hub_context import HubContext, require_hub
from projects.evalops.src.api import dashboard
from projects.evalops.src.datasets import manager
from projects.evalops.src.generation import synthetic
from projects.evalops.src.runner import consumer, dispatch

router = APIRouter(prefix="/hubs/{hub_id}/eval", tags=["eval-hub"])
logger = logging.getLogger("gateway.api.eval_hub")


# --- Helper to map suite model to response schema ---
def _suite_to_response(suite: Any) -> EvalSuiteResponse:
    return EvalSuiteResponse(
        id=suite.id,
        hub_id=suite.hub_id,
        name=suite.name,
        description=suite.description,
        target=EvalTarget(
            type=suite.target_type,
            target_hub_id=suite.target_hub_id,
            target_id=suite.target_id,
        ),
        target_name=None,
        target_status="ok",
        created_at=suite.created_at.isoformat() if suite.created_at else None,
        updated_at=suite.updated_at.isoformat() if suite.updated_at else None,
    )


# --- Helper to map case model to response schema ---
def _case_to_response(case: Any) -> EvalTestCaseResponse:
    return EvalTestCaseResponse(
        id=case.id,
        suite_id=case.suite_id,
        input_query=case.input_query,
        expected_output=case.expected_output,
        expected_context=case.expected_context,
        node_id=case.node_id,
        assertion_type=case.assertion_type,
        assertion_config=case.assertion_config,
        expected_value=case.expected_value,
        created_at=case.created_at.isoformat() if case.created_at else None,
    )


# --- Suite Routes ---


@router.get("/suites", response_model=List[EvalSuiteResponse])
async def list_eval_suites(
    target_type: Optional[str] = Query(None),
    target_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_db),
    ctx: HubContext = Depends(require_hub(hub_type="eval", min_role="viewer")),
):
    """Lists all evaluation test suites for an eval hub."""
    suites = await manager.list_suites(db, hub_id=ctx.hub.id, target_type=target_type, target_id=target_id)
    return [_suite_to_response(s) for s in suites]


@router.post("/suites", response_model=EvalSuiteResponse, status_code=status.HTTP_201_CREATED)
async def create_eval_suite(
    payload: EvalSuiteCreate,
    db: AsyncSession = Depends(get_async_db),
    ctx: HubContext = Depends(require_hub(hub_type="eval", min_role="contributor")),
):
    """Creates a new evaluation test suite."""
    try:
        suite = await manager.create_suite(
            db,
            hub_id=ctx.hub.id,
            name=payload.name,
            description=payload.description,
            target=payload.target,
        )
        return _suite_to_response(suite)
    except ValueError as ve:
        err_msg = str(ve)
        if "SUITE_NAME_TAKEN" in err_msg:
            raise HTTPException(status_code=409, detail=err_msg)
        if "HUB_LINK_REQUIRED" in err_msg or "EVAL_TARGET_MISSING" in err_msg:
            raise HTTPException(status_code=403, detail=err_msg)
        if "CROSS_HUB_REFERENCE_MISMATCH" in err_msg:
            raise HTTPException(status_code=422, detail=err_msg)
        if "HUB_ARCHIVED" in err_msg:
            raise HTTPException(status_code=409, detail=err_msg)
        raise HTTPException(status_code=400, detail=err_msg)


@router.get("/suites/{suite_id}", response_model=EvalSuiteResponse)
async def get_eval_suite(
    suite_id: str,
    db: AsyncSession = Depends(get_async_db),
    ctx: HubContext = Depends(require_hub(hub_type="eval", min_role="viewer")),
):
    """Retrieves a single evaluation test suite."""
    suite = await manager.get_suite(db, hub_id=ctx.hub.id, suite_id=suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="SUITE_NOT_FOUND: Test suite not found.")
    return _suite_to_response(suite)


@router.put("/suites/{suite_id}", response_model=EvalSuiteResponse)
async def update_eval_suite(
    suite_id: str,
    payload: EvalSuiteUpdate,
    db: AsyncSession = Depends(get_async_db),
    ctx: HubContext = Depends(require_hub(hub_type="eval", min_role="contributor")),
):
    """Updates metadata or target for an existing evaluation test suite."""
    try:
        suite = await manager.update_suite(
            db,
            hub_id=ctx.hub.id,
            suite_id=suite_id,
            name=payload.name,
            description=payload.description,
            target=payload.target,
        )
        if not suite:
            raise HTTPException(status_code=404, detail="SUITE_NOT_FOUND: Test suite not found.")
        return _suite_to_response(suite)
    except ValueError as ve:
        err_msg = str(ve)
        if "SUITE_HAS_RUNS_RETARGET_BLOCKED" in err_msg:
            raise HTTPException(status_code=409, detail=err_msg)
        if "SUITE_NAME_TAKEN" in err_msg:
            raise HTTPException(status_code=409, detail=err_msg)
        if "HUB_LINK_REQUIRED" in err_msg:
            raise HTTPException(status_code=403, detail=err_msg)
        raise HTTPException(status_code=400, detail=err_msg)


@router.delete("/suites/{suite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_eval_suite(
    suite_id: str,
    db: AsyncSession = Depends(get_async_db),
    ctx: HubContext = Depends(require_hub(hub_type="eval", min_role="maintainer")),
):
    """Deletes an evaluation test suite."""
    deleted = await manager.delete_suite(db, hub_id=ctx.hub.id, suite_id=suite_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="SUITE_NOT_FOUND: Test suite not found.")


@router.post("/suites/{suite_id}/clone", response_model=EvalSuiteResponse, status_code=status.HTTP_201_CREATED)
async def clone_eval_suite(
    suite_id: str,
    new_name: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_db),
    ctx: HubContext = Depends(require_hub(hub_type="eval", min_role="contributor")),
):
    """Clones an existing evaluation test suite."""
    suite = await manager.clone_suite(db, hub_id=ctx.hub.id, suite_id=suite_id, new_name=new_name)
    if not suite:
        raise HTTPException(status_code=404, detail="SUITE_NOT_FOUND: Original suite not found.")
    return _suite_to_response(suite)


# --- Case Routes ---


@router.get("/suites/{suite_id}/cases", response_model=List[EvalTestCaseResponse])
async def list_eval_test_cases(
    suite_id: str,
    db: AsyncSession = Depends(get_async_db),
    ctx: HubContext = Depends(require_hub(hub_type="eval", min_role="viewer")),
):
    """Lists test cases for an evaluation test suite."""
    suite = await manager.get_suite(db, hub_id=ctx.hub.id, suite_id=suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="SUITE_NOT_FOUND: Test suite not found.")
    cases = await manager.list_test_cases(db, hub_id=ctx.hub.id, suite_id=suite_id)
    return [_case_to_response(c) for c in cases]


@router.post("/suites/{suite_id}/cases", response_model=EvalTestCaseResponse, status_code=status.HTTP_201_CREATED)
async def add_eval_test_case(
    suite_id: str,
    payload: EvalTestCaseCreate,
    db: AsyncSession = Depends(get_async_db),
    ctx: HubContext = Depends(require_hub(hub_type="eval", min_role="contributor")),
):
    """Adds a test case to an evaluation test suite."""
    try:
        case = await manager.add_test_case(
            db,
            hub_id=ctx.hub.id,
            suite_id=suite_id,
            input_query=payload.input_query,
            expected_output=payload.expected_output,
            expected_context=payload.expected_context,
            node_id=payload.node_id,
            assertion_type=payload.assertion_type,
            assertion_config=payload.assertion_config,
            expected_value=payload.expected_value,
        )
        return _case_to_response(case)
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))


@router.put("/suites/{suite_id}/cases/{case_id}", response_model=EvalTestCaseResponse)
async def update_eval_test_case(
    suite_id: str,
    case_id: str,
    payload: EvalTestCaseCreate,
    db: AsyncSession = Depends(get_async_db),
    ctx: HubContext = Depends(require_hub(hub_type="eval", min_role="contributor")),
):
    """Updates a test case."""
    try:
        case = await manager.update_test_case(
            db,
            hub_id=ctx.hub.id,
            case_id=case_id,
            input_query=payload.input_query,
            expected_output=payload.expected_output,
            expected_context=payload.expected_context,
            node_id=payload.node_id,
            assertion_type=payload.assertion_type,
            assertion_config=payload.assertion_config,
            expected_value=payload.expected_value,
        )
        if not case:
            raise HTTPException(status_code=404, detail="CASE_NOT_FOUND: Test case not found.")
        return _case_to_response(case)
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))


@router.delete("/suites/{suite_id}/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_eval_test_case(
    suite_id: str,
    case_id: str,
    db: AsyncSession = Depends(get_async_db),
    ctx: HubContext = Depends(require_hub(hub_type="eval", min_role="contributor")),
):
    """Deletes a test case."""
    deleted = await manager.delete_test_case(db, hub_id=ctx.hub.id, case_id=case_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="CASE_NOT_FOUND: Test case not found.")


@router.post("/suites/{suite_id}/import")
async def import_eval_cases(
    suite_id: str,
    file: UploadFile = File(...),
    fmt: Literal["csv", "json"] = Query("csv"),
    db: AsyncSession = Depends(get_async_db),
    ctx: HubContext = Depends(require_hub(hub_type="eval", min_role="contributor")),
):
    """Imports test cases from a CSV or JSON file into a suite."""
    content = await file.read()
    content_str = content.decode("utf-8")

    try:
        if fmt == "csv":
            count = await manager.import_cases_from_csv(db, hub_id=ctx.hub.id, suite_id=suite_id, csv_content=content_str)
        else:
            json_obj = json.loads(content_str)
            count = await manager.import_cases_from_json(db, hub_id=ctx.hub.id, suite_id=suite_id, json_data=json_obj)
        return {"status": "imported", "imported_count": count}
    except ValueError as ve:
        err_msg = str(ve)
        if "CROSS_HUB_SUITE_ID" in err_msg or "INVALID_ASSERTION_TYPE" in err_msg:
            raise HTTPException(status_code=422, detail=err_msg)
        if "IMPORT_TOO_LARGE" in err_msg:
            raise HTTPException(status_code=413, detail=err_msg)
        raise HTTPException(status_code=400, detail=err_msg)


@router.get("/suites/{suite_id}/export")
async def export_eval_suite(
    suite_id: str,
    fmt: Literal["csv", "json"] = Query("json"),
    db: AsyncSession = Depends(get_async_db),
    ctx: HubContext = Depends(require_hub(hub_type="eval", min_role="viewer")),
):
    """Exports test suite and test cases as CSV or JSON download."""
    suite = await manager.get_suite(db, hub_id=ctx.hub.id, suite_id=suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="SUITE_NOT_FOUND: Test suite not found.")

    export_bytes = await manager.export_suite(db, hub_id=ctx.hub.id, suite_id=suite_id, fmt=fmt)
    media_type = "text/csv" if fmt == "csv" else "application/json"
    filename = f"{suite.name.lower().replace(' ', '_')}.{fmt}"

    return Response(
        content=export_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/generate")
async def generate_synthetic_cases(
    target: EvalTarget,
    count: int = Query(10, le=100),
    persist_to_suite_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_db),
    ctx: HubContext = Depends(require_hub(hub_type="eval", min_role="contributor")),
):
    """Generates synthetic test cases for an agent or workflow target."""
    try:
        cases = await synthetic.generate_synthetic_test_cases(
            db,
            hub_id=ctx.hub.id,
            target=target,
            count=count,
            persist_to_suite_id=persist_to_suite_id,
        )
        return {"status": "success", "count": len(cases), "test_cases": cases}
    except ValueError as ve:
        err_msg = str(ve)
        if "HUB_LINK_REQUIRED" in err_msg:
            raise HTTPException(status_code=403, detail=err_msg)
        raise HTTPException(status_code=422, detail=err_msg)


# --- Targets Picker ---


@router.get("/targets")
async def list_pickable_targets(
    db: AsyncSession = Depends(get_async_db),
    ctx: HubContext = Depends(require_hub(hub_type="eval", min_role="viewer")),
):
    """Lists available agent and workflow target resources from linked hubs."""
    links_stmt = select(HubLink).where(HubLink.source_hub_id == ctx.hub.id)
    links_res = await db.execute(links_stmt)
    links = links_res.scalars().all()

    target_items = []
    for l in links:
        # Resolve target agents
        ag_stmt = select(AgentDefinition).where(AgentDefinition.hub_id == l.target_hub_id)
        ag_res = await db.execute(ag_stmt)
        for ag in ag_res.scalars().all():
            target_items.append(
                {
                    "type": "agent",
                    "target_hub_id": l.target_hub_id,
                    "target_id": ag.id,
                    "name": ag.name,
                    "is_available": True,
                }
            )

        # Resolve target workflows
        wf_stmt = select(WorkflowDefinition).where(WorkflowDefinition.hub_id == l.target_hub_id)
        wf_res = await db.execute(wf_stmt)
        for wf in wf_res.scalars().all():
            target_items.append(
                {
                    "type": "workflow",
                    "target_hub_id": l.target_hub_id,
                    "target_id": wf.id,
                    "name": wf.name,
                    "is_available": True,
                }
            )

    return target_items


# --- Runs & Traces Routes ---


@router.post("/runs", response_model=EvalRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_eval_run(
    payload: EvalRunRequest,
    run_async: bool = Query(True, alias="async"),
    db: AsyncSession = Depends(get_async_db),
    ctx: HubContext = Depends(require_hub(hub_type="eval", min_role="contributor")),
):
    """Triggers an evaluation run for a suite."""
    suite = await manager.get_suite(db, hub_id=ctx.hub.id, suite_id=payload.suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="SUITE_NOT_FOUND: Test suite not found.")

    cases = await manager.list_test_cases(db, hub_id=ctx.hub.id, suite_id=suite.id)
    if not cases:
        raise HTTPException(status_code=400, detail="SUITE_EMPTY: Cannot run evaluation on an empty suite.")

    if not run_async and len(cases) > 50:
        raise HTTPException(status_code=413, detail="SYNC_RUN_TOO_LARGE: Synchronous runs capped at 50 cases. Use async=true.")

    run_id = str(uuid.uuid4())
    target = EvalTarget(type=suite.target_type, target_hub_id=suite.target_hub_id, target_id=suite.target_id)

    if run_async:
        consumer.publish_eval_trigger_event(
            hub_id=ctx.hub.id,
            suite_id=suite.id,
            run_id=run_id,
            framework=payload.framework,
        )
        return EvalRunResponse(
            id=run_id,
            hub_id=ctx.hub.id,
            suite_id=suite.id,
            target=target,
            run_status="queued",
            created_at=datetime.utcnow().isoformat(),
        )
    else:
        try:
            outcomes = await dispatch.dispatch_run(
                db,
                eval_hub_id=ctx.hub.id,
                suite=suite,
                cases=cases,
                run_id=run_id,
                framework=payload.framework or "both",
            )
            return EvalRunResponse(
                id=run_id,
                hub_id=ctx.hub.id,
                suite_id=suite.id,
                target=target,
                run_status="completed",
                created_at=datetime.utcnow().isoformat(),
            )
        except ValueError as ve:
            err_str = str(ve)
            if "HUB_LINK_REQUIRED" in err_str:
                raise HTTPException(status_code=403, detail=err_str)
            if "CROSS_HUB_REFERENCE_MISMATCH" in err_str:
                raise HTTPException(status_code=422, detail=err_str)
            raise HTTPException(status_code=400, detail=err_str)


@router.get("/runs")
async def list_eval_runs(
    target_type: Optional[str] = Query(None),
    target_id: Optional[str] = Query(None),
    suite_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_db),
    ctx: HubContext = Depends(require_hub(hub_type="eval", min_role="viewer")),
):
    """Lists evaluation runs for an eval hub."""
    stmt = select(EvalRunHistory).where(EvalRunHistory.hub_id == ctx.hub.id).order_by(EvalRunHistory.created_at.desc())
    if target_type:
        stmt = stmt.where(EvalRunHistory.target_type == target_type)
    if target_id:
        stmt = stmt.where(EvalRunHistory.target_id == target_id)
    if suite_id:
        stmt = stmt.where(EvalRunHistory.suite_id == suite_id)

    res = await db.execute(stmt)
    runs = res.scalars().all()
    return [
        {
            "id": r.id,
            "hub_id": r.hub_id,
            "suite_id": r.suite_id,
            "target": {"type": r.target_type, "target_hub_id": r.target_hub_id, "target_id": r.target_id},
            "status": r.run_status,
            "passed_count": r.passed_count,
            "failed_count": r.failed_count,
            "duration_sec": r.duration_sec,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in runs
    ]


@router.get("/runs/{run_id}")
async def get_eval_run(
    run_id: str,
    db: AsyncSession = Depends(get_async_db),
    ctx: HubContext = Depends(require_hub(hub_type="eval", min_role="viewer")),
):
    """Retrieves a single evaluation run."""
    stmt = select(EvalRunHistory).where(EvalRunHistory.id == run_id, EvalRunHistory.hub_id == ctx.hub.id)
    res = await db.execute(stmt)
    run = res.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="RUN_NOT_FOUND: Evaluation run not found.")

    return {
        "id": run.id,
        "hub_id": run.hub_id,
        "suite_id": run.suite_id,
        "target": {"type": run.target_type, "target_hub_id": run.target_hub_id, "target_id": run.target_id},
        "status": run.run_status,
        "faithfulness_score": run.faithfulness_score,
        "relevance_score": run.relevance_score,
        "total_test_cases": run.total_test_cases,
        "passed_count": run.passed_count,
        "failed_count": run.failed_count,
        "duration_sec": run.duration_sec,
        "details": run.details_json,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


@router.get("/runs/{run_id}/traces")
async def get_eval_run_traces(
    run_id: str,
    include_state: bool = Query(False),
    db: AsyncSession = Depends(get_async_db),
    ctx: HubContext = Depends(require_hub(hub_type="eval", min_role="viewer")),
):
    """Trace replay endpoint returning ordered node timeline and assertions."""
    stmt = select(EvalRunHistory).where(EvalRunHistory.id == run_id, EvalRunHistory.hub_id == ctx.hub.id)
    res = await db.execute(stmt)
    run = res.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="RUN_NOT_FOUND: Evaluation run not found.")

    if run.target_type == "agent":
        return {
            "run_id": run_id,
            "target": {"type": "agent", "target_hub_id": run.target_hub_id, "target_id": run.target_id},
            "nodes": [],
            "reason": "AGENT_TARGET_HAS_NO_TRACES",
        }

    # Fetch metric assertion results for run
    m_stmt = select(EvalMetricResult).where(EvalMetricResult.run_id == run_id, EvalMetricResult.framework == "node_assertion")
    m_res = await db.execute(m_stmt)
    node_metrics = m_res.scalars().all()

    # Load traces from trace_reader
    from projects.evalops.src.runner.trace_reader import load_run_traces
    traces = await load_run_traces(db, hub_id=ctx.hub.id, run_id=run.workflow_run_id or "")

    nodes = []
    for tr in traces:
        node_assertions = [
            {
                "case_id": m.test_case_id,
                "assertion_type": m.assertion_type,
                "passed": m.passed,
                "reason": m.metric_reason,
            }
            for m in node_metrics
            if m.node_id == tr.node_id
        ]
        n_data = {
            "sequence": tr.sequence,
            "node_id": tr.node_id,
            "node_type": tr.node_type,
            "latency_ms": tr.latency_ms,
            "status": "succeeded",
            "assertions": node_assertions,
        }
        if include_state:
            n_data["input_state"] = tr.input_state
            n_data["output_state"] = tr.output_state
        nodes.append(n_data)

    return {
        "run_id": run_id,
        "workflow_run_id": run.workflow_run_id,
        "target": {"type": "workflow", "target_hub_id": run.target_hub_id, "target_id": run.target_id},
        "nodes": nodes,
        "total_latency_ms": sum(n["latency_ms"] for n in nodes),
    }


# --- Dashboard Panel Aggregation Routes ---


@router.get("/dashboard/stats")
async def get_dashboard_stats(
    target_type: Optional[str] = Query(None),
    target_id: Optional[str] = Query(None),
    framework: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: AsyncSession = Depends(get_async_db),
    ctx: HubContext = Depends(require_hub(hub_type="eval", min_role="viewer")),
):
    """Aggregate dashboard stats."""
    try:
        return await dashboard.get_dashboard_stats(
            db,
            hub_id=ctx.hub.id,
            target_type=target_type,
            target_id=target_id,
            framework=framework,
            date_from=date_from,
            date_to=date_to,
        )
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))


@router.get("/dashboard/trends")
async def get_dashboard_trends(
    target_type: Optional[str] = Query(None),
    target_id: Optional[str] = Query(None),
    framework: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: AsyncSession = Depends(get_async_db),
    ctx: HubContext = Depends(require_hub(hub_type="eval", min_role="viewer")),
):
    """Daily metric score trends."""
    try:
        return await dashboard.get_dashboard_trends(
            db,
            hub_id=ctx.hub.id,
            target_type=target_type,
            target_id=target_id,
            framework=framework,
            date_from=date_from,
            date_to=date_to,
        )
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))


@router.get("/dashboard/comparison")
async def get_dashboard_comparison(
    target_ids: str = Query(..., description="Comma-separated target IDs"),
    framework: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_db),
    ctx: HubContext = Depends(require_hub(hub_type="eval", min_role="viewer")),
):
    """Side-by-side metric comparison across up to 5 targets."""
    t_ids = [t.strip() for t in target_ids.split(",") if t.strip()]
    try:
        return await dashboard.get_dashboard_comparison(db, hub_id=ctx.hub.id, target_ids=t_ids, framework=framework)
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))


@router.get("/dashboard/targets")
async def get_dashboard_targets(
    target_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_db),
    ctx: HubContext = Depends(require_hub(hub_type="eval", min_role="viewer")),
):
    """Per-target score and run rollups."""
    return await dashboard.get_dashboard_targets(db, hub_id=ctx.hub.id, target_type=target_type)
