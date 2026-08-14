"""Real-world integration test suite for GuardRoute Workflow Lifecycle against real Postgres.

Covers workflow creation with draft v1, optimistic locking with ETag/If-Match headers,
multi-version publishing, version diffing, historic version restoration,
workflow duplication, import/export portability, seed templates, and hub scoping.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.database import (
    WorkflowDefinition,
    WorkflowVersion,
    AuditLog,
)
from gateway.auth.utils import create_access_token

pytestmark = pytest.mark.integration


async def _auth_headers(user) -> dict:
    """Build Authorization header for a seeded user."""
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


def _make_valid_graph(nodes_count: int = 2) -> dict:
    """Helper creating a Rule 8 compliant graph ending in final_message."""
    nodes = [
        {
            "id": "start_node",
            "type": "transform",
            "position": {"x": 0, "y": 0},
            "data": {"label": "Transform Input", "mode": "template", "template": "Processed: {{prompt}}"},
        }
    ]
    edges = []

    if nodes_count > 2:
        for i in range(2, nodes_count):
            mid_id = f"mid_node_{i}"
            nodes.append({
                "id": mid_id,
                "type": "transform",
                "position": {"x": 50 * i, "y": 0},
                "data": {"label": f"Step {i}", "mode": "template", "template": "Mid step"},
            })
            prev_id = nodes[-2]["id"]
            edges.append({"id": f"e_{prev_id}_{mid_id}", "source": prev_id, "target": mid_id})

    end_id = "end_node"
    nodes.append({
        "id": end_id,
        "type": "final_message",
        "position": {"x": 200, "y": 0},
        "data": {"label": "Final Output", "message": "Workflow completed"},
    })
    last_prev_id = nodes[-2]["id"]
    edges.append({"id": f"e_{last_prev_id}_{end_id}", "source": last_prev_id, "target": end_id})

    return {"nodes": nodes, "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": 1}}


@pytest.mark.asyncio
async def test_create_workflow_and_verify_draft_v1(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Create a new workflow and verify DB row and draft version v1 creation."""
    owner = await seed_user(email="wf_creator@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Workflow Hub", slug="wf-hub-test", hub_type="workflow")
    headers = await _auth_headers(owner)

    graph_payload = _make_valid_graph(2)

    create_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/workflows",
        json={
            "name": "Customer Support Pipeline",
            "description": "Automates support ticket classification and response",
            "tags_json": ["support", "v1"],
            "graph": graph_payload,
        },
        headers=headers,
    )
    assert create_resp.status_code == 201, f"Create workflow failed: {create_resp.text}"
    data = create_resp.json()
    wf_id = data["id"]
    assert data["name"] == "Customer Support Pipeline"
    assert data["slug"] == "customer-support-pipeline"
    assert data["status"] == "draft"
    assert data["hub_id"] == hub.id
    assert data["draft_version_id"] is not None

    # Verify real DB row in workflows table
    db_wf = await real_db_session.get(WorkflowDefinition, wf_id)
    assert db_wf is not None
    assert db_wf.name == "Customer Support Pipeline"
    assert db_wf.slug == "customer-support-pipeline"
    assert "support" in (db_wf.tags_json or [])

    # Verify real DB row in workflow_versions table
    stmt = select(WorkflowVersion).where(
        WorkflowVersion.workflow_id == wf_id,
        WorkflowVersion.version_number == 1,
    )
    db_ver = (await real_db_session.execute(stmt)).scalar_one_or_none()
    assert db_ver is not None
    assert len(db_ver.graph_json.get("nodes", [])) == 2


@pytest.mark.asyncio
async def test_update_workflow_metadata(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Update workflow name, description, and tags."""
    owner = await seed_user(email="wf_updater@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Workflow Update Hub", slug="wf-update-hub", hub_type="workflow")
    headers = await _auth_headers(owner)

    create_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/workflows",
        json={
            "name": "Initial Workflow Name",
            "description": "Old desc",
            "tags_json": ["tag1"],
            "graph": _make_valid_graph(2),
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    wf_id = create_resp.json()["id"]

    patch_resp = await gateway_client.patch(
        f"/api/hubs/{hub.id}/workflows/{wf_id}",
        json={
            "name": "Updated Workflow Name",
            "description": "Updated desc",
            "tags_json": ["tag1", "tag2"],
        },
        headers=headers,
    )
    assert patch_resp.status_code == 200, f"Patch failed: {patch_resp.text}"
    data = patch_resp.json()
    assert data["name"] == "Updated Workflow Name"
    assert data["description"] == "Updated desc"
    assert data["tags_json"] == ["tag1", "tag2"]

    # Verify AuditLog
    stmt = select(AuditLog).where(
        AuditLog.hub_id == hub.id,
        AuditLog.resource_id == wf_id,
        AuditLog.action == "workflow_update",
    )
    audit = (await real_db_session.execute(stmt)).scalar_one_or_none()
    assert audit is not None


@pytest.mark.asyncio
async def test_workflow_draft_etag_and_optimistic_locking(
    gateway_client: AsyncClient, seed_user, seed_hub
):
    """Update draft graph with ETag checking and optimistic lock conflict verification."""
    owner = await seed_user(email="wf_etag@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Workflow ETag Hub", slug="wf-etag-hub", hub_type="workflow")
    headers = await _auth_headers(owner)

    create_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/workflows",
        json={"name": "ETag Workflow", "graph": _make_valid_graph(2)},
        headers=headers,
    )
    assert create_resp.status_code == 201
    wf_id = create_resp.json()["id"]

    # Publish draft v1 so optimistic locking is active on draft updates
    pub_resp = await gateway_client.post(f"/api/hubs/{hub.id}/workflows/{wf_id}/publish", headers=headers)
    assert pub_resp.status_code == 200

    # Fetch draft and get ETag
    draft_resp = await gateway_client.get(f"/api/hubs/{hub.id}/workflows/{wf_id}/draft", headers=headers)
    assert draft_resp.status_code == 200
    etag = draft_resp.headers.get("ETag")
    assert etag is not None

    new_graph = _make_valid_graph(3)

    # Updating without If-Match when published requires precondition
    missing_if_match_resp = await gateway_client.put(
        f"/api/hubs/{hub.id}/workflows/{wf_id}/draft",
        json=new_graph,
        headers=headers,
    )
    assert missing_if_match_resp.status_code == 428

    # Updating with wrong If-Match causes 409 Conflict
    wrong_headers = {**headers, "If-Match": 'W/"stale-etag-999"'}
    conflict_resp = await gateway_client.put(
        f"/api/hubs/{hub.id}/workflows/{wf_id}/draft",
        json=new_graph,
        headers=wrong_headers,
    )
    assert conflict_resp.status_code == 409

    # Updating with valid If-Match succeeds
    valid_headers = {**headers, "If-Match": etag}
    update_resp = await gateway_client.put(
        f"/api/hubs/{hub.id}/workflows/{wf_id}/draft",
        json=new_graph,
        headers=valid_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.headers.get("ETag") is not None


@pytest.mark.asyncio
async def test_publish_workflow_and_version_history(
    gateway_client: AsyncClient, seed_user, seed_hub
):
    """Publish draft graph as immutable version 1, modify draft, publish version 2, and list versions."""
    owner = await seed_user(email="wf_publisher@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Workflow Publish Hub", slug="wf-pub-hub", hub_type="workflow")
    headers = await _auth_headers(owner)

    create_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/workflows",
        json={
            "name": "Multi Version Flow",
            "graph": _make_valid_graph(2),
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    wf_id = create_resp.json()["id"]

    # Publish v1
    pub_1 = await gateway_client.post(f"/api/hubs/{hub.id}/workflows/{wf_id}/publish", headers=headers)
    assert pub_1.status_code == 200
    assert pub_1.json()["status"] == "published"
    pub_1_id = pub_1.json()["published_version_id"]
    assert pub_1_id is not None

    # Modify draft for v2
    draft_resp = await gateway_client.get(f"/api/hubs/{hub.id}/workflows/{wf_id}/draft", headers=headers)
    etag = draft_resp.headers.get("ETag")

    v2_graph = _make_valid_graph(3)
    update_resp = await gateway_client.put(
        f"/api/hubs/{hub.id}/workflows/{wf_id}/draft",
        json=v2_graph,
        headers={**headers, "If-Match": etag},
    )
    assert update_resp.status_code == 200

    # Publish v2
    pub_2 = await gateway_client.post(f"/api/hubs/{hub.id}/workflows/{wf_id}/publish", headers=headers)
    assert pub_2.status_code == 200
    pub_2_id = pub_2.json()["published_version_id"]
    assert pub_2_id is not None
    assert pub_2_id != pub_1_id

    # List versions
    versions_resp = await gateway_client.get(f"/api/hubs/{hub.id}/workflows/{wf_id}/versions", headers=headers)
    assert versions_resp.status_code == 200
    versions = versions_resp.json()
    assert len(versions) == 2
    version_numbers = [v["version_number"] for v in versions]
    assert 1 in version_numbers
    assert 2 in version_numbers

    # Get specific version detail
    v1_detail = await gateway_client.get(f"/api/hubs/{hub.id}/workflows/{wf_id}/versions/1", headers=headers)
    assert v1_detail.status_code == 200
    assert len(v1_detail.json()["graph_json"]["nodes"]) == 2


@pytest.mark.asyncio
async def test_diff_and_restore_historic_version(
    gateway_client: AsyncClient, seed_user, seed_hub
):
    """Diff graph versions and restore version 1 back as the active draft."""
    owner = await seed_user(email="wf_restore@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Workflow Restore Hub", slug="wf-restore-hub", hub_type="workflow")
    headers = await _auth_headers(owner)

    create_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/workflows",
        json={
            "name": "Restore Test Flow",
            "graph": _make_valid_graph(2),
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    wf_id = create_resp.json()["id"]

    # Publish v1
    await gateway_client.post(f"/api/hubs/{hub.id}/workflows/{wf_id}/publish", headers=headers)

    # Modify draft to v2 and publish
    draft_resp = await gateway_client.get(f"/api/hubs/{hub.id}/workflows/{wf_id}/draft", headers=headers)
    etag = draft_resp.headers.get("ETag")

    await gateway_client.put(
        f"/api/hubs/{hub.id}/workflows/{wf_id}/draft",
        json=_make_valid_graph(3),
        headers={**headers, "If-Match": etag},
    )
    await gateway_client.post(f"/api/hubs/{hub.id}/workflows/{wf_id}/publish", headers=headers)

    # Diff versions base=1, head=2
    diff_resp = await gateway_client.get(f"/api/hubs/{hub.id}/workflows/{wf_id}/diff?base=1&head=2", headers=headers)
    assert diff_resp.status_code == 200

    # Restore v1 as draft
    restore_resp = await gateway_client.post(f"/api/hubs/{hub.id}/workflows/{wf_id}/versions/1/restore", headers=headers)
    assert restore_resp.status_code == 200
    restored_graph = restore_resp.json()["graph_json"]
    assert len(restored_graph["nodes"]) == 2


@pytest.mark.asyncio
async def test_duplicate_workflow_intra_and_cross_hub(
    gateway_client: AsyncClient, seed_user, seed_hub
):
    """Duplicate workflow within the same hub and to another workflow hub."""
    owner = await seed_user(email="wf_dup_user@contained.ai", role="member")
    hub_1 = await seed_hub(owner=owner, name="Workflow Hub 1", slug="wf-hub-1-dup", hub_type="workflow")
    hub_2 = await seed_hub(owner=owner, name="Workflow Hub 2", slug="wf-hub-2-dup", hub_type="workflow")
    headers = await _auth_headers(owner)

    create_resp = await gateway_client.post(
        f"/api/hubs/{hub_1.id}/workflows",
        json={"name": "Source Workflow", "description": "Original source", "graph": _make_valid_graph(2)},
        headers=headers,
    )
    assert create_resp.status_code == 201
    wf_id = create_resp.json()["id"]

    # Duplicate intra-hub
    intra_dup = await gateway_client.post(
        f"/api/hubs/{hub_1.id}/workflows/{wf_id}/duplicate",
        json={},
        headers=headers,
    )
    assert intra_dup.status_code == 201
    assert intra_dup.json()["name"] == "Source Workflow (Copy)"
    assert intra_dup.json()["hub_id"] == hub_1.id

    # Duplicate cross-hub to hub_2
    cross_dup = await gateway_client.post(
        f"/api/hubs/{hub_1.id}/workflows/{wf_id}/duplicate",
        json={"target_hub_id": hub_2.id, "name_override": "Cross-Hub Workflow"},
        headers=headers,
    )
    assert cross_dup.status_code == 201
    assert cross_dup.json()["name"] == "Cross-Hub Workflow"
    assert cross_dup.json()["hub_id"] == hub_2.id


@pytest.mark.asyncio
async def test_export_and_import_workflow_portability(
    gateway_client: AsyncClient, seed_user, seed_hub
):
    """Export a workflow as JSON document and import it into another hub."""
    owner = await seed_user(email="wf_port@contained.ai", role="member")
    hub_source = await seed_hub(owner=owner, name="Source Hub", slug="wf-source-port", hub_type="workflow")
    hub_dest = await seed_hub(owner=owner, name="Dest Hub", slug="wf-dest-port", hub_type="workflow")
    headers = await _auth_headers(owner)

    create_resp = await gateway_client.post(
        f"/api/hubs/{hub_source.id}/workflows",
        json={
            "name": "Exportable Pipeline",
            "graph": _make_valid_graph(2),
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    wf_id = create_resp.json()["id"]

    # Export
    export_resp = await gateway_client.get(f"/api/hubs/{hub_source.id}/workflows/{wf_id}/export", headers=headers)
    assert export_resp.status_code == 200
    export_doc = export_resp.json()
    assert "workflow" in export_doc or "schema_version" in export_doc

    # Import into hub_dest
    import_resp = await gateway_client.post(
        f"/api/hubs/{hub_dest.id}/workflows/import",
        json={"document": export_doc, "name_override": "Imported Support Flow"},
        headers=headers,
    )
    assert import_resp.status_code == 201
    assert import_resp.json()["name"] == "Imported Support Flow"
    assert import_resp.json()["hub_id"] == hub_dest.id


@pytest.mark.asyncio
async def test_workflow_templates_list_and_instantiate(
    gateway_client: AsyncClient, seed_user, seed_hub
):
    """List workflow templates and instantiate one into a hub."""
    owner = await seed_user(email="wf_templates@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Template Hub", slug="wf-template-hub", hub_type="workflow")
    headers = await _auth_headers(owner)

    templates_resp = await gateway_client.get(f"/api/hubs/{hub.id}/workflows/templates", headers=headers)
    assert templates_resp.status_code == 200
    templates = templates_resp.json()
    if len(templates) > 0:
        template_key = templates[0]["key"]
        instantiate_resp = await gateway_client.post(
            f"/api/hubs/{hub.id}/workflows/templates/{template_key}/instantiate",
            json={},
            headers=headers,
        )
        assert instantiate_resp.status_code == 201
        wf = instantiate_resp.json()
        assert wf["hub_id"] == hub.id


@pytest.mark.asyncio
async def test_workflow_hub_scoping_isolation(
    gateway_client: AsyncClient, seed_user, seed_hub
):
    """Workflows belonging to Hub A cannot be read or mutated under Hub B."""
    user_a = await seed_user(email="wf_iso_a@contained.ai", role="member")
    hub_a = await seed_hub(owner=user_a, name="Hub A WF", slug="hub-a-wf-iso", hub_type="workflow")
    headers_a = await _auth_headers(user_a)

    user_b = await seed_user(email="wf_iso_b@contained.ai", role="member")
    hub_b = await seed_hub(owner=user_b, name="Hub B WF", slug="hub-b-wf-iso", hub_type="workflow")
    headers_b = await _auth_headers(user_b)

    create_resp = await gateway_client.post(
        f"/api/hubs/{hub_a.id}/workflows",
        json={"name": "Protected Flow A", "graph": _make_valid_graph(2)},
        headers=headers_a,
    )
    assert create_resp.status_code == 201
    wf_a_id = create_resp.json()["id"]

    # Hub B user cannot access or mutate
    get_from_b = await gateway_client.get(f"/api/hubs/{hub_b.id}/workflows/{wf_a_id}", headers=headers_b)
    assert get_from_b.status_code == 404

    patch_from_b = await gateway_client.patch(
        f"/api/hubs/{hub_b.id}/workflows/{wf_a_id}",
        json={"name": "Hijacked"},
        headers=headers_b,
    )
    assert patch_from_b.status_code == 404

    del_from_b = await gateway_client.delete(f"/api/hubs/{hub_b.id}/workflows/{wf_a_id}", headers=headers_b)
    assert del_from_b.status_code == 404


@pytest.mark.asyncio
async def test_validate_workflow_topology(
    gateway_client: AsyncClient, seed_user, seed_hub
):
    """Validate workflow topology without saving draft."""
    owner = await seed_user(email="wf_validator@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Validation Hub", slug="wf-val-hub", hub_type="workflow")
    headers = await _auth_headers(owner)

    create_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/workflows",
        json={"name": "Validation Test Flow", "graph": _make_valid_graph(2)},
        headers=headers,
    )
    assert create_resp.status_code == 201
    wf_id = create_resp.json()["id"]

    # Valid graph validation
    valid_graph = _make_valid_graph(2)
    val_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/workflows/{wf_id}/validate",
        json={"graph": valid_graph},
        headers=headers,
    )
    assert val_resp.status_code == 200
    assert "is_valid" in val_resp.json()


@pytest.mark.asyncio
async def test_delete_workflow_cascade(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Delete a workflow and verify cascade cleanup from Postgres."""
    owner = await seed_user(email="wf_deleter@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Workflow Delete Hub", slug="wf-del-hub", hub_type="workflow")
    headers = await _auth_headers(owner)

    create_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/workflows",
        json={"name": "Disposable Workflow", "graph": _make_valid_graph(2)},
        headers=headers,
    )
    assert create_resp.status_code == 201
    wf_id = create_resp.json()["id"]

    # Delete
    del_resp = await gateway_client.delete(f"/api/hubs/{hub.id}/workflows/{wf_id}", headers=headers)
    assert del_resp.status_code == 204

    # Subsequent GET returns 404
    get_resp = await gateway_client.get(f"/api/hubs/{hub.id}/workflows/{wf_id}", headers=headers)
    assert get_resp.status_code == 404

    # Verify PostgreSQL row cleanup
    db_wf = await real_db_session.get(WorkflowDefinition, wf_id)
    assert db_wf is None
