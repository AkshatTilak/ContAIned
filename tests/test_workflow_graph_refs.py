"""Unit tests for S6-06c: Qualified Node References & Graph Parser Update."""

import uuid
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from common.models.database import (
    Base,
    Hub,
    User,
    AgentDefinition,
    DatastoreBinding,
    HubLink,
)
from common.schemas.workflows import NodeReference
from projects.guardroute.src.core.graph_parser import (
    GraphParser,
    GraphValidationError,
    collect_references,
    validate_workflow_graph,
)


@pytest_asyncio.fixture
async def db_session():
    """In-memory SQLite database session fixture."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        user = User(id="user-1", email="test@example.com", display_name="Test User")
        session.add(user)
        await session.commit()
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_missing_reference(db_session: AsyncSession):
    """Test that node missing qualified reference fails with MISSING_REFERENCE."""
    hub_wf = Hub(id="hub-wf-1", name="WF Hub", slug="wf-hub", hub_type="workflow", owner_id="user-1")
    db_session.add(hub_wf)
    await db_session.commit()

    graph_bare = {
        "nodes": [
            {"id": "node_1", "type": "AgentNode", "data": {"agent_id": "agt-1"}},
            {"id": "node_2", "type": "ActionNode", "data": {"action": "reply"}},
        ],
        "edges": [{"source": "node_1", "target": "node_2"}],
    }

    res = await validate_workflow_graph(
        db_session,
        graph_json=graph_bare,
        source_hub_id="hub-wf-1",
        strict=False,
    )
    assert not res.is_valid
    codes = [e.code for e in res.errors]
    assert "MISSING_REFERENCE" in codes


@pytest.mark.asyncio
async def test_valid_linked_reference(db_session: AsyncSession):
    """Test that valid linked reference passes validation."""
    hub_wf = Hub(id="hub-wf-2", name="WF Hub 2", slug="wf-hub-2", hub_type="workflow", owner_id="user-1")
    hub_agt = Hub(id="hub-agt-2", name="Agent Hub 2", slug="agent-hub-2", hub_type="agent", owner_id="user-1")
    db_session.add_all([hub_wf, hub_agt])
    await db_session.flush()

    link = HubLink(
        id="link-wf2-agt2",
        source_hub_id="hub-wf-2",
        target_hub_id="hub-agt-2",
        access_level="read",
    )
    agent = AgentDefinition(
        id="agt-2",
        hub_id="hub-agt-2",
        name="Support Agent",
        role="assistant",
        system_prompt="Helpful assistant",
        model_id="gpt-4",
        is_active=True,
    )
    db_session.add_all([link, agent])
    await db_session.commit()

    graph_valid = {
        "nodes": [
            {
                "id": "node_1",
                "type": "AgentNode",
                "data": {
                    "reference": {
                        "type": "agent",
                        "hub_id": "hub-agt-2",
                        "resource_id": "agt-2",
                    }
                },
            },
            {"id": "node_2", "type": "ActionNode", "data": {"action": "reply"}},
        ],
        "edges": [{"source": "node_1", "target": "node_2"}],
    }

    res = await validate_workflow_graph(
        db_session,
        graph_json=graph_valid,
        source_hub_id="hub-wf-2",
        strict=False,
    )
    assert res.is_valid
    assert len(res.errors) == 0


@pytest.mark.asyncio
async def test_revoked_hub_link(db_session: AsyncSession):
    """Test that deleting/revoking a hub link makes validation fail with HUB_LINK_REQUIRED."""
    hub_wf = Hub(id="hub-wf-3", name="WF Hub 3", slug="wf-hub-3", hub_type="workflow", owner_id="user-1")
    hub_agt = Hub(id="hub-agt-3", name="Agent Hub 3", slug="agent-hub-3", hub_type="agent", owner_id="user-1")
    db_session.add_all([hub_wf, hub_agt])
    await db_session.flush()

    agent = AgentDefinition(
        id="agt-3",
        hub_id="hub-agt-3",
        name="Billing Agent",
        role="assistant",
        system_prompt="Billing assistant",
        model_id="gpt-4",
        is_active=True,
    )
    db_session.add(agent)
    await db_session.commit()

    graph = {
        "nodes": [
            {
                "id": "node_1",
                "type": "AgentNode",
                "data": {
                    "reference": {
                        "type": "agent",
                        "hub_id": "hub-agt-3",
                        "resource_id": "agt-3",
                    }
                },
            },
            {"id": "node_2", "type": "ActionNode", "data": {"action": "reply"}},
        ],
        "edges": [{"source": "node_1", "target": "node_2"}],
    }

    res = await validate_workflow_graph(
        db_session,
        graph_json=graph,
        source_hub_id="hub-wf-3",
        strict=False,
    )
    assert not res.is_valid
    codes = [e.code for e in res.errors]
    assert "HUB_LINK_REQUIRED" in codes or "HUB_LINK_REVOKED" in codes


@pytest.mark.asyncio
async def test_cross_hub_reference_mismatch(db_session: AsyncSession):
    """Test reference pairing a linked hub_id with another hub's resource_id fails with CROSS_HUB_REFERENCE_MISMATCH."""
    hub_wf = Hub(id="hub-wf-4", name="WF Hub 4", slug="wf-hub-4", hub_type="workflow", owner_id="user-1")
    hub_agt1 = Hub(id="hub-agt-4a", name="Agent Hub 4A", slug="agent-hub-4a", hub_type="agent", owner_id="user-1")
    hub_agt2 = Hub(id="hub-agt-4b", name="Agent Hub 4B", slug="agent-hub-4b", hub_type="agent", owner_id="user-1")
    db_session.add_all([hub_wf, hub_agt1, hub_agt2])
    await db_session.flush()

    link_4a = HubLink(
        id="link-wf4-agt4a",
        source_hub_id="hub-wf-4",
        target_hub_id="hub-agt-4a",
        access_level="read",
    )
    link_4b = HubLink(
        id="link-wf4-agt4b",
        source_hub_id="hub-wf-4",
        target_hub_id="hub-agt-4b",
        access_level="read",
    )
    # Agent actually belongs to hub-agt-4b, but node references hub-agt-4a
    agent = AgentDefinition(
        id="agt-4b-res",
        hub_id="hub-agt-4b",
        name="Misplaced Agent",
        role="assistant",
        system_prompt="Misplaced assistant",
        model_id="gpt-4",
        is_active=True,
    )
    db_session.add_all([link_4a, link_4b, agent])
    await db_session.commit()

    graph = {
        "nodes": [
            {
                "id": "node_1",
                "type": "AgentNode",
                "data": {
                    "reference": {
                        "type": "agent",
                        "hub_id": "hub-agt-4a",
                        "resource_id": "agt-4b-res",
                    }
                },
            },
            {"id": "node_2", "type": "ActionNode", "data": {"action": "reply"}},
        ],
        "edges": [{"source": "node_1", "target": "node_2"}],
    }

    res = await validate_workflow_graph(
        db_session,
        graph_json=graph,
        source_hub_id="hub-wf-4",
        strict=False,
    )
    assert not res.is_valid
    codes = [e.code for e in res.errors]
    assert "CROSS_HUB_REFERENCE_MISMATCH" in codes


@pytest.mark.asyncio
async def test_v5_topology_constraints_preserved(db_session: AsyncSession):
    """Test preservation of V5 cycle and non-terminal leaf constraints."""
    # Cycle graph
    cycle_graph = {
        "nodes": [
            {"id": "node_1", "type": "AgentNode", "data": {}},
            {"id": "node_2", "type": "AgentNode", "data": {}},
        ],
        "edges": [
            {"source": "node_1", "target": "node_2"},
            {"source": "node_2", "target": "node_1"},
        ],
    }

    res_cycle = await validate_workflow_graph(
        db_session,
        graph_json=cycle_graph,
        source_hub_id="hub-wf-1",
        strict=False,
    )
    assert not res_cycle.is_valid
    codes = [e.code for e in res_cycle.errors]
    assert "CYCLE_DETECTED" in codes

    # Non-terminal leaf graph
    leaf_graph = {
        "nodes": [
            {"id": "node_1", "type": "AgentNode", "data": {}},
        ],
        "edges": [],
    }

    res_leaf = await validate_workflow_graph(
        db_session,
        graph_json=leaf_graph,
        source_hub_id="hub-wf-1",
        strict=False,
    )
    assert not res_leaf.is_valid
    codes = [e.code for e in res_leaf.errors]
    assert "NON_TERMINAL_LEAF" in codes

    # Strict mode raises exception
    with pytest.raises(GraphValidationError):
        await validate_workflow_graph(
            db_session,
            graph_json=leaf_graph,
            source_hub_id="hub-wf-1",
            strict=True,
        )


def test_collect_references_helper():
    """Test collect_references extracts references from graph JSON."""
    graph = {
        "nodes": [
            {
                "id": "node_agent",
                "type": "AgentNode",
                "data": {
                    "reference": {
                        "type": "agent",
                        "hub_id": "hub-agt",
                        "resource_id": "agt-1",
                    }
                },
            },
            {
                "id": "node_multi",
                "type": "MultiAgentNode",
                "data": {
                    "references": [
                        {"type": "agent", "hub_id": "hub-agt", "resource_id": "agt-2"},
                        {"type": "agent", "hub_id": "hub-agt", "resource_id": "agt-3"},
                    ]
                },
            },
            {
                "id": "node_action",
                "type": "ActionNode",
                "data": {"action": "reply"},
            },
        ],
    }

    extracted = collect_references(graph)
    assert len(extracted) == 3
    node_ids = [item[0] for item in extracted]
    assert node_ids == ["node_agent", "node_multi", "node_multi"]
    assert extracted[0][1].resource_id == "agt-1"
    assert extracted[1][1].resource_id == "agt-2"
    assert extracted[2][1].resource_id == "agt-3"
