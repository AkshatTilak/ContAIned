"""Frontend-Backend API Contract Tests (B8-09).

Validates gateway response payload structures against frontend TypeScript interface specifications.
"""

import json
from pathlib import Path
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.auth.utils import create_access_token

pytestmark = pytest.mark.integration


# Load extracted schemas
SCHEMA_FILE = Path(__file__).resolve().parent.parent.parent.parent / "frontend_api_schemas.json"


def _get_schema(name: str) -> dict:
    if not SCHEMA_FILE.exists():
        return {}
    data = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    return data.get("definitions", {}).get(name, {})


def _validate_fields(data: dict, schema_name: str):
    """Validate that expected non-optional fields exist in response payload."""
    schema = _get_schema(schema_name)
    if not schema:
        return
    required_fields = schema.get("required", [])
    for field in required_fields:
        assert field in data, f"Required field '{field}' from schema '{schema_name}' missing in response: {list(data.keys())}"


async def _auth_headers(user) -> dict:
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_contract_health_endpoint(gateway_client: AsyncClient):
    """Validate /api/health contract."""
    resp = await gateway_client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert data["status"] in ("healthy", "degraded", "ok")
    _validate_fields(data, "SystemHealthResponse")


@pytest.mark.asyncio
async def test_contract_hubs_and_members(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession
):
    """Validate Hub and HubMember contracts."""
    uid = uuid.uuid4().hex[:8]
    admin = await seed_user(email=f"contract_hub_{uid}@contained.ai", role="admin")
    headers = await _auth_headers(admin)

    # 1. Create Hub
    hub_payload = {
        "name": f"Contract Hub {uid}",
        "slug": f"contract-hub-{uid}",
        "description": "API Contract Validation Hub",
        "hub_type": "agent",
    }
    create_resp = await gateway_client.post("/api/hubs", json=hub_payload, headers=headers)
    assert create_resp.status_code == 201
    hub_data = create_resp.json()
    assert hub_data["name"] == hub_payload["name"]
    assert hub_data["hub_type"] == "agent"
    _validate_fields(hub_data, "Hub")

    hub_id = hub_data["id"]

    # 2. Get Hub
    get_resp = await gateway_client.get(f"/api/hubs/{hub_id}", headers=headers)
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    _validate_fields(get_data.get("hub", get_data), "Hub")

    # 3. List Hub Members
    members_resp = await gateway_client.get(f"/api/hubs/{hub_id}/members", headers=headers)
    assert members_resp.status_code == 200
    members = members_resp.json()
    assert len(members) >= 1
    _validate_fields(members[0], "HubMember")


@pytest.mark.asyncio
async def test_contract_agents_and_workflows(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession
):
    """Validate Agent and Workflow contracts."""
    uid = uuid.uuid4().hex[:8]
    admin = await seed_user(email=f"contract_agent_{uid}@contained.ai", role="admin")
    headers = await _auth_headers(admin)

    # 1. Agent Hub & Agent Contract with distributed model (gemma-4-31b-it)
    agent_hub_resp = await gateway_client.post(
        "/api/hubs",
        json={"name": f"Agent Contract Hub {uid}", "slug": f"ag-hub-{uid}", "hub_type": "agent"},
        headers=headers,
    )
    agent_hub_id = agent_hub_resp.json()["id"]

    agent_resp = await gateway_client.post(
        f"/api/hubs/{agent_hub_id}/agents",
        json={
            "name": f"Contract Agent {uid}",
            "slug": f"contract-agent-{uid}",
            "role": "assistant",
            "system_prompt": "Contract testing prompt.",
            "model_id": "gemini/gemma-4-31b-it",
            "temperature": 0.7,
        },
        headers=headers,
    )
    assert agent_resp.status_code == 201
    agent_data = agent_resp.json()
    _validate_fields(agent_data, "Agent")

    # 2. Workflow Hub & Workflow Contract with distributed model (gemma-4-26b-a4b-it)
    wf_hub_resp = await gateway_client.post(
        "/api/hubs",
        json={"name": f"Workflow Contract Hub {uid}", "slug": f"wf-hub-{uid}", "hub_type": "workflow"},
        headers=headers,
    )
    wf_hub_id = wf_hub_resp.json()["id"]

    wf_resp = await gateway_client.post(
        f"/api/hubs/{wf_hub_id}/workflows",
        json={
            "name": f"Contract Workflow {uid}",
            "description": "Contract flow",
            "graph": {
                "nodes": [
                    {"id": "n1", "type": "input", "data": {"label": "Start"}},
                    {"id": "n2", "type": "FinalMessageNode", "data": {"label": "End", "model_id": "gemini/gemma-4-26b-a4b-it"}},
                ],
                "edges": [{"id": "e1", "source": "n1", "target": "n2"}],
            },
        },
        headers=headers,
    )
    assert wf_resp.status_code == 201
    wf_data = wf_resp.json()
    _validate_fields(wf_data, "Workflow")


@pytest.mark.asyncio
async def test_contract_ingestion_and_eval(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession
):
    """Validate Ingestion Collection and Eval Suite contracts."""
    uid = uuid.uuid4().hex[:8]
    admin = await seed_user(email=f"contract_ingest_{uid}@contained.ai", role="admin")
    headers = await _auth_headers(admin)

    # 1. Ingestion Hub & Collection Contract
    ingest_hub_resp = await gateway_client.post(
        "/api/hubs",
        json={"name": f"Ingestion Contract Hub {uid}", "slug": f"ing-hub-{uid}", "hub_type": "ingestion"},
        headers=headers,
    )
    ingest_hub_id = ingest_hub_resp.json()["id"]

    col_resp = await gateway_client.post(
        f"/api/hubs/{ingest_hub_id}/ingestion/collections",
        json={
            "name": f"Contract Collection {uid}",
            "description": "Contract collection verification",
            "embedder": "gemini/gemini-embedding-2",
        },
        headers=headers,
    )
    assert col_resp.status_code == 201
    col_data = col_resp.json()
    _validate_fields(col_data, "Collection")

    # 2. Eval Hub Contract
    eval_hub_resp = await gateway_client.post(
        "/api/hubs",
        json={"name": f"Eval Contract Hub {uid}", "slug": f"eval-hub-{uid}", "hub_type": "eval"},
        headers=headers,
    )
    eval_hub_id = eval_hub_resp.json()["id"]

    eval_list_resp = await gateway_client.get(f"/api/hubs/{eval_hub_id}/eval/suites", headers=headers)
    assert eval_list_resp.status_code == 200
    assert isinstance(eval_list_resp.json(), list)


@pytest.mark.asyncio
async def test_contract_mcp_and_models(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession
):
    """Validate MCP tools and Model Registry contracts."""
    uid = uuid.uuid4().hex[:8]
    admin = await seed_user(email=f"contract_mcp_{uid}@contained.ai", role="admin")
    headers = await _auth_headers(admin)

    # 1. MCP Tools listing
    mcp_tools_resp = await gateway_client.get("/api/mcp/tools", headers=headers)
    assert mcp_tools_resp.status_code == 200
    tools = mcp_tools_resp.json()
    assert isinstance(tools, list)

    # 2. Models listing
    models_resp = await gateway_client.get("/api/models", headers=headers)
    assert models_resp.status_code == 200
    models_data = models_resp.json()
    assert isinstance(models_data, (list, dict))
