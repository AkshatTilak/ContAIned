"""Fixture factories for creating test Workflow, WorkflowVersion, and WorkflowRun models."""

import uuid
from datetime import datetime
from common.models.database import WorkflowDefinition, WorkflowVersion, WorkflowRun


def make_workflow(
    hub_id: str,
    name: str = "Test Workflow",
    slug: str | None = None,
    description: str | None = "A test workflow",
    tags: list[str] | None = None,
    status: str = "draft",
    created_by: str | None = None,
    workflow_id: str | None = None,
) -> WorkflowDefinition:
    """Factory helper to construct a WorkflowDefinition instance for testing."""
    wf_id = workflow_id or str(uuid.uuid4())
    wf_slug = slug or name.lower().replace(" ", "-")
    return WorkflowDefinition(
        id=wf_id,
        hub_id=hub_id,
        name=name,
        slug=wf_slug,
        description=description,
        tags_json=tags or [],
        status=status,
        created_by=created_by,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def make_version(
    workflow_id: str,
    version_number: int = 1,
    graph: dict | None = None,
    change_note: str | None = "Initial graph version",
    is_valid: bool = True,
    validation_json: dict | None = None,
    created_by: str | None = None,
    version_id: str | None = None,
) -> WorkflowVersion:
    """Factory helper to construct a WorkflowVersion instance for testing."""
    default_graph = {
        "nodes": [
            {
                "id": "start-1",
                "type": "start",
                "position": {"x": 100, "y": 100},
                "data": {"label": "Start Node"},
            },
            {
                "id": "end-1",
                "type": "final_message",
                "position": {"x": 500, "y": 100},
                "data": {"label": "End Node"},
            },
        ],
        "edges": [
            {
                "id": "e-start-end",
                "source": "start-1",
                "target": "end-1",
            }
        ],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }
    return WorkflowVersion(
        id=version_id or str(uuid.uuid4()),
        workflow_id=workflow_id,
        version_number=version_number,
        graph_json=graph if graph is not None else default_graph,
        change_note=change_note,
        is_valid=is_valid,
        validation_json=validation_json,
        created_by=created_by,
        created_at=datetime.utcnow(),
    )


def make_run(
    hub_id: str,
    workflow_id: str,
    version_id: str | None = None,
    trigger: str = "manual",
    status: str = "succeeded",
    input_json: dict | None = None,
    output_json: dict | None = None,
    error_message: str | None = None,
    node_count: int | None = 2,
    duration_ms: int | None = 150,
    started_by: str | None = None,
    run_id: str | None = None,
) -> WorkflowRun:
    """Factory helper to construct a WorkflowRun instance for testing."""
    return WorkflowRun(
        id=run_id or str(uuid.uuid4()),
        hub_id=hub_id,
        workflow_id=workflow_id,
        version_id=version_id,
        trigger=trigger,
        status=status,
        input_json=input_json or {"query": "test input"},
        output_json=output_json or {"result": "success"},
        error_message=error_message,
        node_count=node_count,
        duration_ms=duration_ms,
        started_by=started_by,
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
    )
