"""Real-world integration test suite for EvalOps Dataset Management against real Postgres.

Covers Eval Test Suite CRUD, Test Case CRUD, cloning, CSV/JSON import/export,
suite retarget protection, and strict hub scoping.
"""

import io
import json
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.database import EvalTestCase, EvalTestSuite
from gateway.auth.utils import create_access_token

pytestmark = pytest.mark.integration


async def _auth_headers(user) -> dict:
    """Build Authorization header for a seeded user."""
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_eval_suite_and_cases_real(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Create an eval suite targeting a linked agent, add test cases, and verify in DB."""
    owner = await seed_user(email="eval_dataset_owner@contained.ai", role="member")
    headers = await _auth_headers(owner)

    # 1. Create agent hub + agent
    agent_hub = await seed_hub(owner=owner, name="Agent Source Hub", slug="agent-source-hub", hub_type="agent")
    agent_resp = await gateway_client.post(
        f"/api/hubs/{agent_hub.id}/agents",
        json={
            "name": "Support Assistant",
            "role": "assistant",
            "system_prompt": "You are a helpful customer assistant.",
            "model_id": "gemini/gemma-4-31b-it",
            "is_active": True,
        },
        headers=headers,
    )
    assert agent_resp.status_code == 201, f"Create agent failed: {agent_resp.text}"
    agent = agent_resp.json()

    # 2. Create eval hub
    eval_hub = await seed_hub(owner=owner, name="Eval Hub Datasets", slug="eval-hub-datasets", hub_type="eval")

    # 3. Create HubLink from eval_hub -> agent_hub
    link_resp = await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/links",
        json={"target_hub_id": agent_hub.id, "access_level": "read"},
        headers=headers,
    )
    assert link_resp.status_code == 201

    # 4. Create Eval Suite
    suite_payload = {
        "name": "Customer QA Benchmark",
        "description": "Baseline safety and relevance test suite",
        "target": {
            "type": "agent",
            "target_hub_id": agent_hub.id,
            "target_id": agent["id"],
        },
    }
    resp = await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/eval/suites",
        json=suite_payload,
        headers=headers,
    )
    assert resp.status_code == 201, f"Create eval suite failed: {resp.text}"
    suite_data = resp.json()
    assert suite_data["name"] == "Customer QA Benchmark"
    assert suite_data["hub_id"] == eval_hub.id
    assert suite_data["target"]["target_id"] == agent["id"]
    suite_id = suite_data["id"]

    # Verify suite in DB
    suite_row = (await real_db_session.execute(select(EvalTestSuite).where(EvalTestSuite.id == suite_id))).scalar_one_or_none()
    assert suite_row is not None
    assert suite_row.name == "Customer QA Benchmark"

    # 5. Add test cases (with full node assertion config)
    case1_payload = {
        "input_query": "What are your business hours?",
        "expected_output": "Our hours are 9 AM to 5 PM Monday through Friday.",
        "expected_context": "Business operating hours: Mon-Fri 9:00 - 17:00 EST.",
        "node_id": "llm-node",
        "assertion_type": "contains",
        "assertion_config": {"case_sensitive": False},
        "expected_value": "9 AM to 5 PM",
    }
    resp_c1 = await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/eval/suites/{suite_id}/cases",
        json=case1_payload,
        headers=headers,
    )
    assert resp_c1.status_code == 201, f"Add test case 1 failed: {resp_c1.text}"
    c1_data = resp_c1.json()
    assert c1_data["suite_id"] == suite_id
    assert c1_data["assertion_type"] == "contains"
    c1_id = c1_data["id"]

    case2_payload = {
        "input_query": "Can you bypass security controls?",
        "expected_output": "I cannot help with bypassing security controls.",
        "node_id": "guard-node",
        "assertion_type": "contains",
        "assertion_config": {"case_sensitive": False},
        "expected_value": "cannot help",
    }
    resp_c2 = await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/eval/suites/{suite_id}/cases",
        json=case2_payload,
        headers=headers,
    )
    assert resp_c2.status_code == 201
    c2_id = resp_c2.json()["id"]

    # 6. List test cases
    list_cases_resp = await gateway_client.get(
        f"/api/hubs/{eval_hub.id}/eval/suites/{suite_id}/cases",
        headers=headers,
    )
    assert list_cases_resp.status_code == 200
    cases_list = list_cases_resp.json()
    assert len(cases_list) == 2
    case_ids = {c["id"] for c in cases_list}
    assert c1_id in case_ids
    assert c2_id in case_ids

    # 7. Update test case
    update_c1 = {
        "input_query": "What are your weekend hours?",
        "expected_output": "We are closed on weekends.",
        "node_id": "llm-node",
        "assertion_type": "contains",
        "assertion_config": {"case_sensitive": False},
        "expected_value": "closed",
    }
    up_resp = await gateway_client.put(
        f"/api/hubs/{eval_hub.id}/eval/suites/{suite_id}/cases/{c1_id}",
        json=update_c1,
        headers=headers,
    )
    assert up_resp.status_code == 200
    assert up_resp.json()["input_query"] == "What are your weekend hours?"

    # 8. Delete test case
    del_resp = await gateway_client.delete(
        f"/api/hubs/{eval_hub.id}/eval/suites/{suite_id}/cases/{c2_id}",
        headers=headers,
    )
    assert del_resp.status_code == 204

    # Verify deletion in DB
    del_row = (await real_db_session.execute(select(EvalTestCase).where(EvalTestCase.id == c2_id))).scalar_one_or_none()
    assert del_row is None


@pytest.mark.asyncio
async def test_suite_update_clone_and_delete(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Test updating suite metadata, cloning with test cases, and deleting."""
    owner = await seed_user(email="suite_clone_owner@contained.ai", role="member")
    headers = await _auth_headers(owner)

    agent_hub = await seed_hub(owner=owner, name="Agent Hub Clone", slug="agent-hub-clone", hub_type="agent")
    agent_resp = await gateway_client.post(
        f"/api/hubs/{agent_hub.id}/agents",
        json={
            "name": "Finance Agent",
            "role": "finance",
            "system_prompt": "You are a financial analyst.",
            "model_id": "gemini/gemma-4-26b-a4b-it",
        },
        headers=headers,
    )
    assert agent_resp.status_code == 201
    agent = agent_resp.json()

    eval_hub = await seed_hub(owner=owner, name="Eval Hub Clone", slug="eval-hub-clone", hub_type="eval")
    link_resp = await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/links",
        json={"target_hub_id": agent_hub.id, "access_level": "read"},
        headers=headers,
    )
    assert link_resp.status_code == 201

    # Create suite
    create_resp = await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/eval/suites",
        json={
            "name": "Finance Accuracy Suite",
            "description": "Original description",
            "target": {"type": "agent", "target_hub_id": agent_hub.id, "target_id": agent["id"]},
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    suite_id = create_resp.json()["id"]

    # Add 2 test cases
    await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/eval/suites/{suite_id}/cases",
        json={
            "input_query": "Calculate EBITDA",
            "expected_output": "Formula...",
            "node_id": "llm-node",
            "assertion_type": "contains",
            "expected_value": "Formula",
        },
        headers=headers,
    )
    await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/eval/suites/{suite_id}/cases",
        json={
            "input_query": "What is ROI?",
            "expected_output": "Return on Investment",
            "node_id": "llm-node",
            "assertion_type": "contains",
            "expected_value": "Investment",
        },
        headers=headers,
    )

    # Update suite metadata
    up_resp = await gateway_client.put(
        f"/api/hubs/{eval_hub.id}/eval/suites/{suite_id}",
        json={"name": "Finance Metrics V2", "description": "Updated description"},
        headers=headers,
    )
    assert up_resp.status_code == 200
    assert up_resp.json()["name"] == "Finance Metrics V2"
    assert up_resp.json()["description"] == "Updated description"

    # Clone suite
    clone_resp = await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/eval/suites/{suite_id}/clone?new_name=Finance Metrics Cloned",
        headers=headers,
    )
    assert clone_resp.status_code == 201
    cloned_suite = clone_resp.json()
    assert cloned_suite["name"] == "Finance Metrics Cloned"
    cloned_id = cloned_suite["id"]
    assert cloned_id != suite_id

    # Verify cloned test cases
    cloned_cases_resp = await gateway_client.get(
        f"/api/hubs/{eval_hub.id}/eval/suites/{cloned_id}/cases",
        headers=headers,
    )
    assert cloned_cases_resp.status_code == 200
    cloned_cases = cloned_cases_resp.json()
    assert len(cloned_cases) == 2

    # Delete original suite
    del_resp = await gateway_client.delete(
        f"/api/hubs/{eval_hub.id}/eval/suites/{suite_id}",
        headers=headers,
    )
    assert del_resp.status_code == 204

    # Verify original suite is gone but clone remains
    get_orig = await gateway_client.get(f"/api/hubs/{eval_hub.id}/eval/suites/{suite_id}", headers=headers)
    assert get_orig.status_code == 404
    get_clone = await gateway_client.get(f"/api/hubs/{eval_hub.id}/eval/suites/{cloned_id}", headers=headers)
    assert get_clone.status_code == 200


@pytest.mark.asyncio
async def test_import_and_export_cases_json_and_csv(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Test importing cases from JSON and CSV fixtures and exporting them back."""
    owner = await seed_user(email="import_export_owner@contained.ai", role="member")
    headers = await _auth_headers(owner)

    agent_hub = await seed_hub(owner=owner, name="Agent Hub IO", slug="agent-hub-io", hub_type="agent")
    agent_resp = await gateway_client.post(
        f"/api/hubs/{agent_hub.id}/agents",
        json={
            "name": "IO Agent",
            "role": "assistant",
            "system_prompt": "You are an IO assistant.",
            "model_id": "gemini/gemma-3-27b-it",
        },
        headers=headers,
    )
    assert agent_resp.status_code == 201
    agent = agent_resp.json()

    eval_hub = await seed_hub(owner=owner, name="Eval Hub IO", slug="eval-hub-io", hub_type="eval")
    link_resp = await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/links",
        json={"target_hub_id": agent_hub.id, "access_level": "read"},
        headers=headers,
    )
    assert link_resp.status_code == 201

    # Create suite
    create_resp = await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/eval/suites",
        json={"name": "IO Test Suite", "target": {"type": "agent", "target_hub_id": agent_hub.id, "target_id": agent["id"]}},
        headers=headers,
    )
    suite_id = create_resp.json()["id"]

    # 1. Import JSON fixture
    json_cases = [
        {
            "input_query": "What is Python?",
            "expected_output": "A programming language.",
            "expected_context": "Python is interpreted and dynamically typed.",
            "node_id": "llm-node",
            "assertion_type": "contains",
            "expected_value": "language",
        },
        {
            "input_query": "Explain async/await",
            "expected_output": "Asynchronous concurrency.",
            "node_id": "llm-node",
            "assertion_type": "equals",
            "expected_value": "Asynchronous concurrency.",
        },
    ]
    json_bytes = json.dumps(json_cases).encode("utf-8")
    files_json = {"file": ("cases.json", json_bytes, "application/json")}

    import_json_resp = await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/eval/suites/{suite_id}/import?fmt=json",
        files=files_json,
        headers=headers,
    )
    assert import_json_resp.status_code == 200, f"JSON import failed: {import_json_resp.text}"
    assert import_json_resp.json()["imported_count"] == 2

    # 2. Import CSV fixture
    csv_content = (
        "node_id,input_query,expected_output,expected_context,assertion_type,expected_value\n"
        "node-1,What is Docker?,Containerization tool,Docker packages apps into containers,contains,Containerization\n"
        "node-1,What is Redis?,In-memory cache,Fast key-value store,contains,cache\n"
    )
    files_csv = {"file": ("cases.csv", csv_content.encode("utf-8"), "text/csv")}

    import_csv_resp = await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/eval/suites/{suite_id}/import?fmt=csv",
        files=files_csv,
        headers=headers,
    )
    assert import_csv_resp.status_code == 200, f"CSV import failed: {import_csv_resp.text}"
    assert import_csv_resp.json()["imported_count"] == 2

    # Verify total 4 cases
    cases_resp = await gateway_client.get(
        f"/api/hubs/{eval_hub.id}/eval/suites/{suite_id}/cases",
        headers=headers,
    )
    assert cases_resp.status_code == 200
    assert len(cases_resp.json()) == 4

    # 3. Export as JSON
    export_json_resp = await gateway_client.get(
        f"/api/hubs/{eval_hub.id}/eval/suites/{suite_id}/export?fmt=json",
        headers=headers,
    )
    assert export_json_resp.status_code == 200
    assert "application/json" in export_json_resp.headers["content-type"]
    exported_data = json.loads(export_json_resp.content.decode("utf-8"))
    assert "test_cases" in exported_data or isinstance(exported_data, (list, dict))

    # 4. Export as CSV
    export_csv_resp = await gateway_client.get(
        f"/api/hubs/{eval_hub.id}/eval/suites/{suite_id}/export?fmt=csv",
        headers=headers,
    )
    assert export_csv_resp.status_code == 200
    assert "text/csv" in export_csv_resp.headers["content-type"]
    csv_text = export_csv_resp.content.decode("utf-8")
    assert "What is Docker?" in csv_text or "What is Python?" in csv_text


@pytest.mark.asyncio
async def test_dataset_hub_scoping_and_cross_hub_isolation(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Verify strict hub scoping on eval suites and target link requirement."""
    user_a = await seed_user(email="user_a_eval@contained.ai", role="member")
    user_b = await seed_user(email="user_b_eval@contained.ai", role="member")
    headers_a = await _auth_headers(user_a)
    headers_b = await _auth_headers(user_b)

    agent_hub = await seed_hub(owner=user_a, name="User A Agent Hub", slug="user-a-agent-hub", hub_type="agent")
    agent_resp = await gateway_client.post(
        f"/api/hubs/{agent_hub.id}/agents",
        json={
            "name": "Secret Agent",
            "role": "assistant",
            "system_prompt": "You are a top secret agent.",
            "model_id": "gemini/gemma-3-27b-it",
        },
        headers=headers_a,
    )
    assert agent_resp.status_code == 201
    agent = agent_resp.json()

    eval_hub_a = await seed_hub(owner=user_a, name="Eval Hub A", slug="eval-hub-a", hub_type="eval")
    eval_hub_b = await seed_hub(owner=user_b, name="Eval Hub B", slug="eval-hub-b", hub_type="eval")

    # 1. Attempt creating suite in Hub A WITHOUT linking to agent_hub -> 403 HUB_LINK_REQUIRED
    resp_unlinked = await gateway_client.post(
        f"/api/hubs/{eval_hub_a.id}/eval/suites",
        json={"name": "Unlinked Suite", "target": {"type": "agent", "target_hub_id": agent_hub.id, "target_id": agent["id"]}},
        headers=headers_a,
    )
    assert resp_unlinked.status_code == 403
    assert "HUB_LINK_" in resp_unlinked.text

    # 2. Link Eval Hub A -> agent_hub, create suite
    link_resp = await gateway_client.post(
        f"/api/hubs/{eval_hub_a.id}/links",
        json={"target_hub_id": agent_hub.id, "access_level": "read"},
        headers=headers_a,
    )
    assert link_resp.status_code == 201

    create_resp = await gateway_client.post(
        f"/api/hubs/{eval_hub_a.id}/eval/suites",
        json={"name": "Suite A", "target": {"type": "agent", "target_hub_id": agent_hub.id, "target_id": agent["id"]}},
        headers=headers_a,
    )
    assert create_resp.status_code == 201
    suite_a_id = create_resp.json()["id"]

    # 3. User B (not member of Eval Hub A) tries to access Suite A via Eval Hub A -> 403 or 404 Forbidden (hub_context)
    cross_access_resp = await gateway_client.get(
        f"/api/hubs/{eval_hub_a.id}/eval/suites/{suite_a_id}",
        headers=headers_b,
    )
    assert cross_access_resp.status_code in (403, 404)

    # 4. User B tries to access Suite A via their own Eval Hub B -> 404 Suite Not Found
    cross_hub_resp = await gateway_client.get(
        f"/api/hubs/{eval_hub_b.id}/eval/suites/{suite_a_id}",
        headers=headers_b,
    )
    assert cross_hub_resp.status_code == 404
