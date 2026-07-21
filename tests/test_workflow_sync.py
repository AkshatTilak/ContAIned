"""Unit and integration tests for GuardRoute visual workflow backend sync & DB CRUD.
"""

import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock

from projects.guardroute.api import (
    list_workflows,
    create_workflow,
    activate_workflow,
    get_active_workflow,
    WorkflowCreatePayload
)


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_create_workflow_validation(mock_db):
    valid_payload = WorkflowCreatePayload(
        name="Test LangGraph Workflow",
        graph_json={
            "nodes": [
                {"id": "classify", "type": "ClassifierNode"},
                {"id": "gather", "type": "SynthesisNode"}
            ],
            "edges": [
                {"id": "e1", "source": "classify", "target": "gather"}
            ]
        },
        is_active=False
    )

    res = await create_workflow(payload=valid_payload, db=mock_db)
    assert res.name == "Test LangGraph Workflow"
    assert res.is_active is False
    assert mock_db.add.called


@pytest.mark.asyncio
async def test_activate_workflow(mock_db):
    wf_id = str(uuid.uuid4())
    mock_wf = MagicMock()
    mock_wf.id = wf_id
    mock_wf.name = "Custom Workflow"
    mock_wf.graph_json = {"nodes": [{"id": "n1"}], "edges": []}
    mock_wf.is_active = False

    res_mock = MagicMock()
    res_mock.scalar_one_or_none.return_value = mock_wf
    mock_db.execute.return_value = res_mock

    res = await activate_workflow(workflow_id=wf_id, db=mock_db)
    assert res.id == wf_id
    assert res.is_active is True


@pytest.mark.asyncio
async def test_get_active_workflow_none(mock_db):
    res_mock = MagicMock()
    res_mock.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = res_mock

    active = await get_active_workflow(db=mock_db)
    assert active is None
