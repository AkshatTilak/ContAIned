"""Real-world integration test suite for EvalOps Eval Hub Management & Dashboard Analytics.

Covers Eval Hub CRUD, Hub Linking and Target Discovery, and Dashboard Aggregations
(stats, trends, comparison, target rollups).
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.auth.utils import create_access_token

pytestmark = pytest.mark.integration


async def _auth_headers(user) -> dict:
    """Build Authorization header for a seeded user."""
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_eval_hub_crud_lifecycle(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession
):
    """Test full CRUD lifecycle of an Eval Hub."""
    owner = await seed_user(email="eval_hub_owner@contained.ai", role="member")
    headers = await _auth_headers(owner)

    # 1. Create Eval Hub
    create_payload = {
        "name": "Model Quality Hub",
        "slug": "model-quality-hub",
        "description": "Evaluation benchmarks for LLM apps",
        "hub_type": "eval",
    }
    create_resp = await gateway_client.post("/api/hubs", json=create_payload, headers=headers)
    assert create_resp.status_code == 201, f"Create eval hub failed: {create_resp.text}"
    hub_data = create_resp.json()
    assert hub_data["name"] == "Model Quality Hub"
    assert hub_data["slug"] == "model-quality-hub"
    assert hub_data["hub_type"] == "eval"
    hub_id = hub_data["id"]

    # 2. Get Eval Hub
    get_resp = await gateway_client.get(f"/api/hubs/{hub_id}", headers=headers)
    assert get_resp.status_code == 200
    hub_detail = get_resp.json()
    assert hub_detail["hub"]["id"] == hub_id
    assert hub_detail["hub"]["name"] == "Model Quality Hub"

    # 3. Update Eval Hub
    update_payload = {"name": "Model QA Hub V2", "description": "Updated description"}
    update_resp = await gateway_client.patch(f"/api/hubs/{hub_id}", json=update_payload, headers=headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Model QA Hub V2"

    # 4. Delete Eval Hub
    del_resp = await gateway_client.delete(f"/api/hubs/{hub_id}", headers=headers)
    assert del_resp.status_code in (200, 204)


@pytest.mark.asyncio
async def test_eval_hub_linking_and_target_discovery(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Verify linking an Eval Hub to Agent and Workflow hubs surfaces pickable targets."""
    owner = await seed_user(email="eval_target_picker@contained.ai", role="member")
    headers = await _auth_headers(owner)

    # 1. Create Agent Hub and Agent
    agent_hub = await seed_hub(owner=owner, name="Target Source Agent Hub", slug="target-source-agent-hub", hub_type="agent")
    agent_resp = await gateway_client.post(
        f"/api/hubs/{agent_hub.id}/agents",
        json={
            "name": "Target Assistant Agent",
            "role": "assistant",
            "system_prompt": "You are a target test agent.",
            "model_id": "gemini/gemma-3-27b-it",
        },
        headers=headers,
    )
    assert agent_resp.status_code == 201
    agent = agent_resp.json()

    # 2. Create Workflow Hub and Workflow
    wf_hub = await seed_hub(owner=owner, name="Target Source WF Hub", slug="target-source-wf-hub", hub_type="workflow")
    wf_resp = await gateway_client.post(
        f"/api/hubs/{wf_hub.id}/workflows",
        json={
            "name": "Target Pipeline WF",
            "canvas_nodes": [
                {"id": "in", "type": "input", "data": {"label": "In"}},
                {"id": "out", "type": "terminal", "data": {"label": "Out"}},
            ],
            "canvas_edges": [{"id": "e", "source": "in", "target": "out"}],
        },
        headers=headers,
    )
    assert wf_resp.status_code == 201
    wf = wf_resp.json()

    # 3. Create Eval Hub
    eval_hub = await seed_hub(owner=owner, name="Target Discovery Eval Hub", slug="target-discovery-eval-hub", hub_type="eval")

    # 4. Check targets before linking -> empty list
    targets_before = await gateway_client.get(f"/api/hubs/{eval_hub.id}/eval/targets", headers=headers)
    assert targets_before.status_code == 200
    assert len(targets_before.json()) == 0

    # 5. Link Eval Hub -> Agent Hub
    link1 = await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/links",
        json={"target_hub_id": agent_hub.id, "access_level": "read"},
        headers=headers,
    )
    assert link1.status_code == 201

    # 6. Link Eval Hub -> Workflow Hub
    link2 = await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/links",
        json={"target_hub_id": wf_hub.id, "access_level": "read"},
        headers=headers,
    )
    assert link2.status_code == 201

    # 7. Check targets after linking -> lists both agent and workflow
    targets_after = await gateway_client.get(f"/api/hubs/{eval_hub.id}/eval/targets", headers=headers)
    assert targets_after.status_code == 200
    targets_list = targets_after.json()
    assert len(targets_list) >= 2
    target_ids = {t["target_id"] for t in targets_list}
    assert agent["id"] in target_ids
    assert wf["id"] in target_ids


@pytest.mark.asyncio
async def test_eval_dashboard_stats_and_aggregation(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Test dashboard aggregation endpoints: stats, trends, comparison, and target summaries."""
    owner = await seed_user(email="eval_dashboard_user@contained.ai", role="member")
    headers = await _auth_headers(owner)

    # 1. Seed Hubs and Targets
    agent_hub = await seed_hub(owner=owner, name="Dash Agent Hub", slug="dash-agent-hub", hub_type="agent")
    agent_resp = await gateway_client.post(
        f"/api/hubs/{agent_hub.id}/agents",
        json={
            "name": "Dashboard Agent",
            "role": "analytics",
            "system_prompt": "You are a dashboard test assistant.",
            "model_id": "gemini/gemma-3-27b-it",
        },
        headers=headers,
    )
    agent = agent_resp.json()

    eval_hub = await seed_hub(owner=owner, name="Dashboard Eval Hub", slug="dash-eval-hub", hub_type="eval")
    await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/links",
        json={"target_hub_id": agent_hub.id, "access_level": "read"},
        headers=headers,
    )

    # 2. Create Suite and Case
    suite_resp = await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/eval/suites",
        json={
            "name": "Dashboard Suite",
            "target": {"type": "agent", "target_hub_id": agent_hub.id, "target_id": agent["id"]},
        },
        headers=headers,
    )
    suite_id = suite_resp.json()["id"]

    await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/eval/suites/{suite_id}/cases",
        json={
            "input_query": "Test query 1",
            "expected_output": "Test query 1 response",
            "node_id": "out",
            "assertion_type": "contains",
            "expected_value": "response",
        },
        headers=headers,
    )

    # 3. Trigger Eval Run
    run_resp = await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/eval/runs?async=false",
        json={"suite_id": suite_id},
        headers=headers,
    )
    assert run_resp.status_code == 202

    # 4. Test Dashboard Stats
    stats_resp = await gateway_client.get(f"/api/hubs/{eval_hub.id}/eval/dashboard/stats", headers=headers)
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert "total_runs" in stats
    assert stats["total_runs"] >= 1
    assert "avg_faithfulness" in stats or "pass_rate" in stats

    # 5. Test Dashboard Trends
    trends_resp = await gateway_client.get(f"/api/hubs/{eval_hub.id}/eval/dashboard/trends", headers=headers)
    assert trends_resp.status_code == 200
    trends = trends_resp.json()
    assert isinstance(trends, list)

    # 6. Test Dashboard Comparison
    comp_resp = await gateway_client.get(
        f"/api/hubs/{eval_hub.id}/eval/dashboard/comparison?target_ids={agent['id']}",
        headers=headers,
    )
    assert comp_resp.status_code == 200
    comparisons = comp_resp.json()
    assert isinstance(comparisons, list)
    assert len(comparisons) >= 1
    assert comparisons[0]["target_id"] == agent["id"]

    # 7. Test Dashboard Targets Rollup
    targets_resp = await gateway_client.get(f"/api/hubs/{eval_hub.id}/eval/dashboard/targets", headers=headers)
    assert targets_resp.status_code == 200
    targets_summary = targets_resp.json()
    assert isinstance(targets_summary, list)
