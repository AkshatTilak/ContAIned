"""Unit tests for S6-06f: Workflow Portability, Import/Export & Templates."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from common.models.database import Base, Hub, User, WorkflowDefinition, WorkflowVersion
from projects.guardroute.src.workflows.portability import (
    export_workflow,
    import_workflow,
    list_templates,
    instantiate_template,
    EXPORT_FORMAT_VERSION,
)


@pytest_asyncio.fixture
async def db_setup():
    """In-memory SQLite database setup fixture."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        user = User(id="user-port-1", email="portability@example.com", display_name="Port User")
        hub1 = Hub(id="hub-port-1", name="Port Hub 1", slug="port-hub-1", hub_type="workflow", owner_id="user-port-1")
        hub2 = Hub(id="hub-port-2", name="Port Hub 2", slug="port-hub-2", hub_type="workflow", owner_id="user-port-1")
        session.add_all([user, hub1, hub2])
        await session.commit()
        yield session, session_factory

    await engine.dispose()


@pytest.mark.asyncio
async def test_export_and_secret_sanitization(db_setup):
    """Test exporting a workflow and verifying secret fields are stripped."""
    session, sf = db_setup

    wf = WorkflowDefinition(id="wf-export-1", hub_id="hub-port-1", name="Export Flow", slug="export-flow", status="published")
    graph = {
        "nodes": [
            {"id": "n1", "type": "GatherNode", "data": {"label": "Gather", "api_key": "secret_123"}},
            {"id": "n2", "type": "FinalMessageNode", "data": {"label": "Output"}},
        ],
        "edges": [{"source": "n1", "target": "n2"}],
    }
    ver = WorkflowVersion(id="ver-export-1", workflow_id="wf-export-1", version_number=1, graph_json=graph, is_valid=True)
    wf.published_version_id = ver.id

    session.add_all([wf, ver])
    await session.commit()

    exported = await export_workflow(session, hub_id="hub-port-1", workflow_id="wf-export-1")
    assert exported["format"] == EXPORT_FORMAT_VERSION
    assert exported["workflow"]["name"] == "Export Flow"
    assert exported["version"]["graph"]["nodes"][0]["data"]["api_key"] is None
    assert len(exported["warnings"]) == 1


@pytest.mark.asyncio
async def test_import_workflow(db_setup):
    """Test importing a workflow export document into a target hub."""
    session, sf = db_setup

    document = {
        "format": EXPORT_FORMAT_VERSION,
        "source": {"hub_id": "hub-port-1", "hub_slug": "port-hub-1", "hub_type": "workflow"},
        "workflow": {"name": "Imported Flow", "slug": "imported-flow", "description": "Desc"},
        "version": {
            "graph": {
                "nodes": [
                    {"id": "n1", "type": "GatherNode", "data": {"label": "Gather"}},
                    {"id": "n2", "type": "FinalMessageNode", "data": {"label": "Output"}},
                ],
                "edges": [{"source": "n1", "target": "n2"}],
            }
        },
        "dependencies": [],
    }

    imported_wf = await import_workflow(
        session,
        target_hub_id="hub-port-2",
        document=document,
        actor_id="user-port-1",
    )
    assert imported_wf.hub_id == "hub-port-2"
    assert imported_wf.status == "draft"
    assert imported_wf.slug.startswith("imported-flow")


@pytest.mark.asyncio
async def test_list_and_instantiate_templates(db_setup):
    """Test listing seed templates and instantiating one."""
    session, sf = db_setup

    templates = await list_templates()
    assert len(templates) >= 3

    keys = [t["key"] for t in templates]
    assert "rag_qa" in keys
    assert "multi_agent_triage" in keys
    assert "classify_and_route" in keys

    wf = await instantiate_template(
        session,
        target_hub_id="hub-port-1",
        template_key="rag_qa",
        actor_id="user-port-1",
    )
    assert wf.name == "RAG QA Workflow"
    assert wf.hub_id == "hub-port-1"
