"""End-to-End Test: Complete Workflow Journey from design to versioning, execution, and import/export."""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.auth.utils import create_access_token

pytestmark = pytest.mark.integration


async def _auth_headers(user) -> dict:
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_complete_workflow_journey(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession
):
    """Full workflow lifecycle: design -> publish version -> run -> export -> import to new hub."""
    uid = uuid.uuid4().hex[:8]
    owner = await seed_user(email=f"wf_journey_{uid}@contained.ai", role="admin")
    headers = await _auth_headers(owner)

    # 1. Create Workflow Hub
    hub_resp = await gateway_client.post(
        "/api/hubs",
        json={
            "name": f"Workflow Hub {uid}",
            "slug": f"workflow-hub-{uid}",
            "description": "E2E Workflow Journey Hub",
            "hub_type": "workflow",
        },
        headers=headers,
    )
    assert hub_resp.status_code == 201
    hub_id = hub_resp.json()["id"]

    # 2. Create Multi-Node Workflow Design with Distributed Model (gemma-4-26b-a4b-it)
    initial_graph = {
        "nodes": [
            {"id": "node_in", "type": "input", "data": {"label": "Start Input"}},
            {
                "id": "node_llm",
                "type": "llm",
                "data": {
                    "label": "Process LLM",
                    "model_id": "gemini/gemma-4-26b-a4b-it",
                    "temperature": 0.5,
                    "prompt": "Summarize {{input.prompt}}",
                },
            },
            {"id": "node_out", "type": "FinalMessageNode", "data": {"label": "Result Output", "model_id": "gemini/gemma-4-26b-a4b-it"}},
        ],
        "edges": [
            {"id": "e1", "source": "node_in", "target": "node_llm"},
            {"id": "e2", "source": "node_llm", "target": "node_out"},
        ],
    }

    wf_create_resp = await gateway_client.post(
        f"/api/hubs/{hub_id}/workflows",
        json={
            "name": f"Pipeline Flow {uid}",
            "description": "Multi-node processing pipeline",
            "graph": initial_graph,
        },
        headers=headers,
    )
    assert wf_create_resp.status_code == 201
    wf = wf_create_resp.json()
    wf_id = wf["id"]

    # 3. Publish Version 1
    pub_resp = await gateway_client.post(
        f"/api/hubs/{hub_id}/workflows/{wf_id}/publish",
        headers=headers,
    )
    assert pub_resp.status_code == 200
    pub_wf = pub_resp.json()
    assert pub_wf["published_version_id"] is not None

    # 4. Update Draft with If-Match Optimistic Locking
    draft_get_resp = await gateway_client.get(
        f"/api/hubs/{hub_id}/workflows/{wf_id}/draft",
        headers=headers,
    )
    assert draft_get_resp.status_code == 200
    etag = draft_get_resp.headers.get("ETag")

    updated_graph = {
        "nodes": initial_graph["nodes"] + [
            {"id": "node_log", "type": "FinalMessageNode", "data": {"label": "Audit Output", "model_id": "gemini/gemma-4-26b-a4b-it"}}
        ],
        "edges": initial_graph["edges"] + [
            {"id": "e3", "source": "node_llm", "target": "node_log"}
        ],
    }

    draft_update_resp = await gateway_client.put(
        f"/api/hubs/{hub_id}/workflows/{wf_id}/draft",
        json=updated_graph,
        headers={**headers, "If-Match": etag} if etag else headers,
    )
    assert draft_update_resp.status_code == 200

    # 5. Execute Workflow Run
    run_resp = await gateway_client.post(
        f"/api/hubs/{hub_id}/workflows/{wf_id}/runs",
        json={
            "input": {"prompt": "E2E workflow test data input"},
            "use_draft": True,
            "stream": False,
        },
        headers=headers,
    )
    assert run_resp.status_code == 202
    run_id = run_resp.json()["run_id"]
    assert run_id is not None

    # List Runs
    runs_resp = await gateway_client.get(f"/api/hubs/{hub_id}/workflows/{wf_id}/runs", headers=headers)
    assert runs_resp.status_code == 200
    assert len(runs_resp.json()) >= 1

    # 6. Export Workflow Definition
    export_resp = await gateway_client.get(
        f"/api/hubs/{hub_id}/workflows/{wf_id}/export",
        headers=headers,
    )
    assert export_resp.status_code == 200
    export_data = export_resp.json()
    assert "workflow" in export_data or "name" in export_data or "graph" in export_data

    # 7. Create Target Hub and Import Workflow
    target_hub_resp = await gateway_client.post(
        "/api/hubs",
        json={
            "name": f"Target Hub {uid}",
            "slug": f"target-hub-{uid}",
            "description": "Portability Target Hub",
            "hub_type": "workflow",
        },
        headers=headers,
    )
    assert target_hub_resp.status_code == 201
    target_hub_id = target_hub_resp.json()["id"]

    import_resp = await gateway_client.post(
        f"/api/hubs/{target_hub_id}/workflows/import",
        json={
            "document": export_data,
            "name_override": f"Imported Pipeline {uid}",
        },
        headers=headers,
    )
    assert import_resp.status_code in (200, 201)
    imported_wf = import_resp.json()
    assert imported_wf["hub_id"] == target_hub_id
