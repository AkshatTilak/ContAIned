
import pytest
pytestmark = pytest.mark.unit
"""Tests for agent tool bindings replacing standalone tool nodes (v7).

Covers:
- Removed standalone tool node types (retrieval / mcp_tool / database_query /
  db_store) are rejected with a clear validation error.
- Agent-node tool bindings are validated (unknown types, missing refs).
- The tool executor dispatches bindings to the underlying executors.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from common.models.database import Base, Hub, User
from common.schemas.workflows import ToolBinding
from projects.guardroute.src.core.graph_parser import (
    GraphParser,
    GraphValidationError,
    validate_workflow_graph,
)
from projects.guardroute.src.nodes.tool_executor import execute_agent_tools


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


# ---------------------------------------------------------------------------
# ToolBinding schema
# ---------------------------------------------------------------------------

def test_tool_binding_retrieval_requires_refs():
    with pytest.raises(ValueError):
        ToolBinding(type="retrieval", hub_id="h", collection_id=None)

    tb = ToolBinding(type="retrieval", hub_id="h", collection_id="c")
    assert tb.type == "retrieval"
    assert tb.enabled is True


def test_tool_binding_mcp_requires_refs():
    with pytest.raises(ValueError):
        ToolBinding(type="mcp", server_id="s", tool_name=None)

    tb = ToolBinding(type="mcp", server_id="s", tool_name="query")
    assert tb.tool_name == "query"


def test_tool_binding_db_requires_credential():
    with pytest.raises(ValueError):
        ToolBinding(type="db", credential_id=None)

    tb = ToolBinding(type="db", credential_id="cred-1")
    assert tb.credential_id == "cred-1"


def test_tool_binding_api_call_requires_url():
    with pytest.raises(ValueError):
        ToolBinding(type="api_call", url=None)

    tb = ToolBinding(type="api_call", url="https://api.example.com")
    assert tb.method == "GET"


# ---------------------------------------------------------------------------
# Removed standalone tool node types
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("removed_type", [
    "RetrievalNode", "retrieval",
    "MCPToolNode", "mcp_tool",
    "DatabaseQueryNode", "database_query",
    "DBStoreNode", "db_store",
])
def test_removed_node_types_rejected(removed_type):
    graph_json = {
        "nodes": [
            {"id": "n1", "type": "ClassifierNode"},
            {"id": "n2", "type": removed_type},
            {"id": "n3", "type": "SynthesisNode"},
        ],
        "edges": [
            {"id": "e1", "source": "n1", "target": "n2"},
            {"id": "e2", "source": "n2", "target": "n3"},
        ],
    }
    parser = GraphParser(graph_json)
    with pytest.raises(GraphValidationError, match="removed node type"):
        parser.validate_graph()


def test_removed_node_types_not_in_supported():
    for t in GraphParser.REMOVED_NODE_TYPES:
        assert t not in GraphParser.SUPPORTED_NODE_TYPES


# ---------------------------------------------------------------------------
# Agent tool binding validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validate_unknown_tool_type(db_session: AsyncSession):
    graph_json = {
        "nodes": [
            {"id": "agent", "type": "agent", "data": {"tools": [{"type": "bogus"}]}},
            {"id": "final", "type": "final_message"},
        ],
        "edges": [{"id": "e1", "source": "agent", "target": "final"}],
    }
    result = await validate_workflow_graph(
        db_session, graph_json=graph_json, source_hub_id="hub-1"
    )
    codes = {i.code for i in result.errors}
    assert "UNKNOWN_TOOL_TYPE" in codes


@pytest.mark.asyncio
async def test_validate_tool_missing_ref(db_session: AsyncSession):
    graph_json = {
        "nodes": [
            {"id": "agent", "type": "agent", "data": {"tools": [{"type": "retrieval"}]}},
            {"id": "final", "type": "final_message"},
        ],
        "edges": [{"id": "e1", "source": "agent", "target": "final"}],
    }
    result = await validate_workflow_graph(
        db_session, graph_json=graph_json, source_hub_id="hub-1"
    )
    codes = {i.code for i in result.errors}
    assert "TOOL_MISSING_REF" in codes


@pytest.mark.asyncio
async def test_validate_valid_tool_bindings(db_session: AsyncSession):
    """web_search and api_call tools need no cross-hub refs and validate clean."""
    graph_json = {
        "nodes": [
            {
                "id": "agent",
                "type": "agent",
                "data": {
                    "tools": [
                        {"type": "web_search", "enabled": True},
                        {"type": "api_call", "url": "https://api.example.com"},
                    ]
                },
            },
            {"id": "final", "type": "final_message"},
        ],
        "edges": [{"id": "e1", "source": "agent", "target": "final"}],
    }
    result = await validate_workflow_graph(
        db_session, graph_json=graph_json, source_hub_id="hub-1"
    )
    tool_codes = {i.code for i in result.errors if i.code in
                  ("UNKNOWN_TOOL_TYPE", "TOOL_MISSING_REF", "MALFORMED_TOOL")}
    assert tool_codes == set()


# ---------------------------------------------------------------------------
# Tool executor dispatch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_agent_tools_unknown_type():
    state = {"prompt": "hello", "hub_id": "hub-1"}
    out = await execute_agent_tools([{"type": "bogus"}], state)
    assert out["tool_count"] == 1
    assert out["tool_results"][0]["success"] is False


@pytest.mark.asyncio
async def test_execute_agent_tools_disabled_skipped():
    state = {"prompt": "hello", "hub_id": "hub-1"}
    out = await execute_agent_tools([{"type": "web_search", "enabled": False}], state)
    assert out["tool_count"] == 0


@pytest.mark.asyncio
async def test_execute_agent_tools_web_search(monkeypatch):
    async def fake_search(query):
        return {"results": [{"title": "x"}]}
    monkeypatch.setattr(
        "projects.guardroute.src.agents.search.run_web_search", fake_search
    )
    state = {"prompt": "hello", "hub_id": "hub-1"}
    out = await execute_agent_tools([{"type": "web_search", "enabled": True}], state)
    assert out["tool_count"] == 1
    assert out["tool_results"][0]["tool_type"] == "web_search"
    assert out["tool_results"][0]["success"] is True
