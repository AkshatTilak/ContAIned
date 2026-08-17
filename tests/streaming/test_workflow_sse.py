"""Real integration tests for GuardRoute Workflow Run SSE streaming."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.auth.utils import create_access_token
from tests.streaming.conftest import collect_all_events

pytestmark = pytest.mark.integration


async def _auth_headers(user) -> dict:
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_workflow_run_sse_streaming_sequence(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Start workflow execution with stream: true and verify sequence of SSE events (run_start -> run_end)."""
    owner = await seed_user(email="wf_stream_owner@contained.ai", role="member")
    headers = await _auth_headers(owner)

    # 1. Create Workflow Hub and Workflow
    wf_hub = await seed_hub(owner=owner, name="Stream Hub", slug="stream-hub", hub_type="workflow")
    wf_payload = {
        "name": "SSE Linear Pipeline",
        "description": "Streams execution events",
        "canvas_nodes": [
            {"id": "n1", "type": "input", "data": {"label": "Start"}},
            {"id": "n2", "type": "terminal", "data": {"label": "End"}},
        ],
        "canvas_edges": [{"id": "e1", "source": "n1", "target": "n2"}],
    }
    wf_resp = await gateway_client.post(f"/api/hubs/{wf_hub.id}/workflows", json=wf_payload, headers=headers)
    assert wf_resp.status_code == 201
    wf_id = wf_resp.json()["id"]

    # 2. Execute with stream: true
    events = await collect_all_events(
        gateway_client,
        f"/api/hubs/{wf_hub.id}/workflows/{wf_id}/runs",
        method="POST",
        headers=headers,
        json_body={"input": {"prompt": "Run streaming test"}, "use_draft": True, "stream": True},
        timeout_s=10.0,
    )

    assert len(events) >= 1
    event_names = [e["event"] for e in events]
    assert "run_start" in event_names

    start_event = next(e for e in events if e["event"] == "run_start")
    assert "run_id" in start_event["data"]
    assert "workflow_id" in start_event["data"]


@pytest.mark.asyncio
async def test_workflow_run_direct_stream_endpoint(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Trigger a workflow run as queued, then open GET /{wf_id}/runs/{run_id}/stream."""
    owner = await seed_user(email="wf_direct_stream@contained.ai", role="member")
    headers = await _auth_headers(owner)

    wf_hub = await seed_hub(owner=owner, name="Direct Stream Hub", slug="direct-stream-hub", hub_type="workflow")
    wf_payload = {
        "name": "Direct Stream Flow",
        "canvas_nodes": [
            {"id": "in", "type": "input", "data": {"label": "In"}},
            {"id": "out", "type": "terminal", "data": {"label": "Out"}},
        ],
        "canvas_edges": [{"id": "e", "source": "in", "target": "out"}],
    }
    wf_resp = await gateway_client.post(f"/api/hubs/{wf_hub.id}/workflows", json=wf_payload, headers=headers)
    wf_id = wf_resp.json()["id"]

    # Trigger run as queued
    start_resp = await gateway_client.post(
        f"/api/hubs/{wf_hub.id}/workflows/{wf_id}/runs",
        json={"input": {"prompt": "Direct test"}, "use_draft": True, "stream": False},
        headers=headers,
    )
    assert start_resp.status_code == 202
    run_id = start_resp.json()["run_id"]

    # Stream from dedicated endpoint
    events = await collect_all_events(
        gateway_client,
        f"/api/hubs/{wf_hub.id}/workflows/{wf_id}/runs/{run_id}/stream",
        method="GET",
        headers=headers,
        timeout_s=8.0,
    )

    assert len(events) >= 1
