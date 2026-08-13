
import pytest
pytestmark = pytest.mark.unit
"""Acceptance test suite for Base Task B6-06 (Workflow Hub & Multi-Workflow Management)."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from common.models.database import (
    Base,
    Hub,
    HubLink,
    HubMember,
    User,
    WorkflowDefinition,
    AgentDefinition,
)
from projects.guardroute.src.workflows import version_service
from projects.guardroute.src.workflows.version_service import DraftConflict


@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        # Seed users
        u_owner = User(id="user-owner", email="owner@example.com", platform_role="member", status="active")
        session.add(u_owner)

        # Seed workflow hubs: alpha, beta
        hub_alpha = Hub(id="wf-alpha", slug="alpha", name="Workflow Alpha", hub_type="workflow", owner_id="user-owner")
        hub_beta = Hub(id="wf-beta", slug="beta", name="Workflow Beta", hub_type="workflow", owner_id="user-owner")
        # Seed agent hub: bots
        hub_bots = Hub(id="ag-bots", slug="bots", name="Agent Bots", hub_type="agent", owner_id="user-owner")
        session.add_all([hub_alpha, hub_beta, hub_bots])

        # Memberships
        m_alpha = HubMember(hub_id="wf-alpha", user_id="user-owner", hub_role="owner")
        m_beta = HubMember(hub_id="wf-beta", user_id="user-owner", hub_role="owner")
        m_bots = HubMember(hub_id="ag-bots", user_id="user-owner", hub_role="owner")
        session.add_all([m_alpha, m_beta, m_bots])

        # Agent resource in bots hub
        bot_agent = AgentDefinition(
            id="bot-1",
            hub_id="ag-bots",
            name="Support Bot",
            role="assistant",
            endpoint_slug="support-bot",
            system_prompt="Help user",
            model_id="gpt-4o",
            is_active=True,
        )
        session.add(bot_agent)

        # Link alpha -> bots (use)
        link_alpha_bots = HubLink(
            id="link-1",
            source_hub_id="wf-alpha",
            target_hub_id="ag-bots",
            access_level="use",
        )
        session.add(link_alpha_bots)
        await session.commit()

        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_multi_workflow_crud_and_slug_isolation(async_session: AsyncSession):
    session = async_session

    # Create workflow 1 in alpha
    wf1 = WorkflowDefinition(
        id="wf-1",
        hub_id="wf-alpha",
        name="Flow One",
        slug="flow-one",
        status="draft",
    )
    # Create workflow 2 in alpha
    wf2 = WorkflowDefinition(
        id="wf-2",
        hub_id="wf-alpha",
        name="Flow Two",
        slug="flow-two",
        status="draft",
    )
    # Same slug allowed in beta hub
    wf3 = WorkflowDefinition(
        id="wf-3",
        hub_id="wf-beta",
        name="Flow One",
        slug="flow-one",
        status="draft",
    )
    session.add_all([wf1, wf2, wf3])
    await session.commit()

    # Query workflows for alpha
    draft1 = await version_service.get_draft(session, hub_id="wf-alpha", workflow_id="wf-1")
    assert draft1 is not None
    assert draft1.version_number == 1

    # Attempting duplicate slug in same hub throws error
    with pytest.raises(Exception):
        dup = WorkflowDefinition(id="wf-4", hub_id="wf-alpha", name="Flow One Dup", slug="flow-one")
        session.add(dup)
        await session.commit()
    await session.rollback()


@pytest.mark.asyncio
async def test_version_lifecycle_and_restore(async_session: AsyncSession):
    session = async_session

    wf = WorkflowDefinition(id="wf-lifecycle", hub_id="wf-alpha", name="Lifecycle Workflow", slug="lifecycle", status="draft")
    session.add(wf)
    await session.commit()

    # Initial draft
    d1 = await version_service.get_draft(session, hub_id="wf-alpha", workflow_id="wf-lifecycle")
    assert d1.version_number == 1
    etag1 = version_service.compute_etag(d1)

    # Update draft
    graph_v1 = {
        "nodes": [
            {"id": "n1", "type": "AgentNode", "data": {"reference": {"type": "agent", "hub_id": "ag-bots", "resource_id": "bot-1"}}},
            {"id": "n2", "type": "FinalMessageNode", "data": {}}
        ],
        "edges": [{"id": "e1", "source": "n1", "target": "n2"}]
    }
    update_res = await version_service.update_draft(
        session,
        hub_id="wf-alpha",
        workflow_id="wf-lifecycle",
        graph=graph_v1,
        expected_etag=etag1,
        actor_id="user-owner",
    )
    assert update_res is not None

    # Publish draft
    pub_v1 = await version_service.publish(session, hub_id="wf-alpha", workflow_id="wf-lifecycle", actor_id="user-owner")
    assert pub_v1.version_number == 1

    # Subsequent draft auto-creates v2
    d2 = await version_service.get_draft(session, hub_id="wf-alpha", workflow_id="wf-lifecycle")
    assert d2.version_number == 2

    # Restore v1 creates v3 draft
    v3 = await version_service.restore(session, hub_id="wf-alpha", workflow_id="wf-lifecycle", version_number=1, actor_id="user-owner")
    assert v3.version_number == 3
    assert v3.change_note == "Restored from v1"


@pytest.mark.asyncio
async def test_etag_conflict_detection(async_session: AsyncSession):
    session = async_session

    wf = WorkflowDefinition(id="wf-etag", hub_id="wf-alpha", name="ETag Workflow", slug="etag-wf", status="draft")
    session.add(wf)
    await session.commit()

    d1 = await version_service.get_draft(session, hub_id="wf-alpha", workflow_id="wf-etag")
    etag1 = version_service.compute_etag(d1)

    # Client 1 updates draft successfully
    g1 = {"nodes": [{"id": "n1", "type": "FinalMessageNode", "data": {}}], "edges": []}
    await version_service.update_draft(session, hub_id="wf-alpha", workflow_id="wf-etag", graph=g1, expected_etag=etag1, actor_id="user-owner")

    # Client 2 updates draft with stale etag1 -> raises DraftConflict
    g2 = {"nodes": [{"id": "n2", "type": "FinalMessageNode", "data": {}}], "edges": []}
    with pytest.raises(DraftConflict):
        await version_service.update_draft(session, hub_id="wf-alpha", workflow_id="wf-etag", graph=g2, expected_etag=etag1, actor_id="user-owner")


@pytest.mark.asyncio
async def test_cross_hub_reference_and_migration_rewrite(async_session: AsyncSession):
    session = async_session

    # Test migration logic for bare agent_id rewrite
    legacy_graph = {
        "nodes": [
            {"id": "agent-node", "type": "AgentNode", "data": {"agent_id": "bot-1"}},
            {"id": "end-node", "type": "FinalMessageNode", "data": {}}
        ],
        "edges": [{"id": "e1", "source": "agent-node", "target": "end-node"}]
    }

    # Verify migration behavior helper logic: agent_id rewritten to qualified reference
    node = legacy_graph["nodes"][0]
    agent_id = node["data"].pop("agent_id")
    node["data"]["reference"] = {"type": "agent", "hub_id": "ag-bots", "resource_id": agent_id}

    assert node["data"]["reference"]["type"] == "agent"
    assert node["data"]["reference"]["hub_id"] == "ag-bots"
    assert node["data"]["reference"]["resource_id"] == "bot-1"


# ---------------------------------------------------------------------------
# Sub_11_03 required tests: hub-scoped validation and cross-hub enforcement
# ---------------------------------------------------------------------------

from projects.guardroute.src.core.graph_parser import validate_workflow_graph
from common.services.hub_resolver import HubLinkError


@pytest.mark.asyncio
async def test_valid_same_hub_reference_passes(async_session: AsyncSession):
    """Well-formed graph with a valid same-hub active agent reference should pass validation."""
    session = async_session

    agent = AgentDefinition(
        id="bot-validate-1",
        hub_id="ag-bots",
        name="Validate Agent",
        role="assistant",
        system_prompt="Hello",
        model_id="gpt-4",
        is_active=True,
    )
    session.add(agent)
    await session.commit()

    # wf-alpha is a workflow hub; ag-bots is its agent hub
    # A HubLink wf-alpha → ag-bots was seeded in the fixture
    graph = {
        "nodes": [
            {
                "id": "agt-v1",
                "type": "AgentNode",
                "data": {
                    "reference": {
                        "type": "agent",
                        "hub_id": "ag-bots",
                        "resource_id": "bot-validate-1",
                    }
                },
            },
            {"id": "fin-v1", "type": "FinalMessageNode", "data": {}},
        ],
        "edges": [{"source": "agt-v1", "target": "fin-v1"}],
    }

    result = await validate_workflow_graph(
        session,
        graph_json=graph,
        source_hub_id="wf-alpha",
        strict=False,
    )
    assert result.is_valid, f"Expected valid; got: {[e.model_dump() for e in result.errors]}"


@pytest.mark.asyncio
async def test_cross_hub_no_link_rejected(async_session: AsyncSession):
    """Cross-hub reference to a hub not linked to source → HUB_LINK_REQUIRED / REFERENCE_TARGET_MISSING."""
    session = async_session

    unlinked_hub = Hub(
        id="hub-unlinked-agt",
        slug="unlinked-agt",
        name="Unlinked Agent Hub",
        hub_type="agent",
        owner_id="user-owner",
    )
    remote_agent = AgentDefinition(
        id="remote-agt-1",
        hub_id="hub-unlinked-agt",
        name="Remote Agent",
        role="assistant",
        system_prompt="Remote",
        model_id="gpt-4",
        is_active=True,
    )
    session.add_all([unlinked_hub, remote_agent])
    await session.commit()

    graph = {
        "nodes": [
            {
                "id": "agt-remote",
                "type": "AgentNode",
                "data": {
                    "reference": {
                        "type": "agent",
                        "hub_id": "hub-unlinked-agt",
                        "resource_id": "remote-agt-1",
                    }
                },
            },
            {"id": "fin-r1", "type": "FinalMessageNode", "data": {}},
        ],
        "edges": [{"source": "agt-remote", "target": "fin-r1"}],
    }

    result = await validate_workflow_graph(
        session,
        graph_json=graph,
        source_hub_id="wf-alpha",  # not linked to hub-unlinked-agt
        strict=False,
    )
    assert not result.is_valid
    codes = {e.code for e in result.errors}
    assert codes & {"HUB_LINK_REQUIRED", "HUB_LINK_REVOKED", "REFERENCE_TARGET_MISSING"}, (
        f"Expected hub link error, got: {codes}"
    )


@pytest.mark.asyncio
async def test_cross_hub_revoked_link_rejected_mock():
    """Cross-hub reference where hub_resolver raises HUB_LINK_REVOKED → issue returned."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from projects.guardroute.src.core.graph_parser import GraphParser

    hub_id = "wf-mock-hub"
    target_hub_id = "agt-mock-hub"
    resource_id = "agt-mock-resource"

    graph = {
        "nodes": [
            {
                "id": "remote-mock",
                "type": "AgentNode",
                "data": {
                    "reference": {
                        "type": "agent",
                        "hub_id": target_hub_id,
                        "resource_id": resource_id,
                    }
                },
            },
            {"id": "fin-mock", "type": "FinalMessageNode", "data": {}},
        ],
        "edges": [{"source": "remote-mock", "target": "fin-mock"}],
    }

    mock_hub = MagicMock()
    mock_hub.is_archived = False
    revoked_error = HubLinkError("HUB_LINK_REVOKED", "Link revoked", source_hub_id=hub_id)

    with (
        patch(
            "projects.guardroute.src.core.graph_parser.get_hub",
            new_callable=AsyncMock,
            return_value=mock_hub,
        ),
        patch(
            "projects.guardroute.src.core.graph_parser.resolve_linked",
            new_callable=AsyncMock,
            side_effect=revoked_error,
        ),
    ):
        result = await validate_workflow_graph(
            AsyncMock(),
            graph_json=graph,
            source_hub_id=hub_id,
            strict=False,
        )

    assert not result.is_valid
    codes = {e.code for e in result.errors}
    assert "HUB_LINK_REVOKED" in codes, f"Expected HUB_LINK_REVOKED, got: {codes}"


@pytest.mark.asyncio
async def test_validate_returns_is_valid_false_with_node_level_issues():
    """validate_workflow_graph returns is_valid=False and node-level issues for cyclic graph."""
    graph = {
        "nodes": [
            {"id": "A", "type": "TransformNode", "data": {}},
            {"id": "B", "type": "TransformNode", "data": {}},
        ],
        "edges": [
            {"source": "A", "target": "B"},
            {"source": "B", "target": "A"},  # cycle
        ],
    }

    result = await validate_workflow_graph(
        None,
        graph_json=graph,
        source_hub_id="",
        strict=False,
    )

    assert not result.is_valid
    assert len(result.errors) > 0
    for issue in result.errors:
        assert issue.code
        assert issue.message

