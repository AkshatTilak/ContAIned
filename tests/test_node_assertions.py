"""Unit & integration tests for intermediate workflow node trace assertions (S6-07c)."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from common.models.database import (
    Base,
    EvalFlowTrace,
    EvalTestCase,
    Hub,
    User,
)
from projects.evalops.src.runner.block_assertion_engine import BlockAssertionEngine, evaluate_node_assertions
from projects.evalops.src.runner.trace_reader import TraceRecord, load_run_traces


@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        u = User(id="usr-1", email="usr1@example.com", platform_role="member", status="active")
        h1 = Hub(id="hub-eval-1", slug="eval-1", name="Eval Hub", hub_type="eval", owner_id="usr-1")
        h2 = Hub(id="hub-eval-2", slug="eval-2", name="Other Hub", hub_type="eval", owner_id="usr-1")
        session.add_all([u, h1, h2])

        # Seed traces for run-100 in hub-eval-1
        t1 = EvalFlowTrace(
            id="tr-1",
            hub_id="hub-eval-1",
            run_id="run-100",
            node_id="node-router",
            node_type="RouterNode",
            sequence=1,
            input_state={"query": "Hello"},
            output_state={"target_agent": "support_bot", "status": "ok"},
            latency_ms=120.0,
        )
        t2 = EvalFlowTrace(
            id="tr-2",
            hub_id="hub-eval-1",
            run_id="run-100",
            node_id="node-retrieval",
            node_type="RetrievalNode",
            sequence=2,
            input_state={"query": "Hello"},
            output_state={"documents": ["doc1", "doc2"], "secret_key": "[REDACTED]"},
            latency_ms=250.0,
        )
        t3 = EvalFlowTrace(
            id="tr-3",
            hub_id="hub-eval-1",
            run_id="run-100",
            node_id="node-retrieval",
            node_type="RetrievalNode",
            sequence=3,
            input_state={"query": "Retry"},
            output_state={"documents": ["doc1", "doc2", "doc3"]},
            latency_ms=310.0,
        )
        session.add_all([t1, t2, t3])
        await session.commit()
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_trace_reader_hub_isolation(async_session: AsyncSession):
    session = async_session

    # Traces for hub-eval-1 must be returned
    traces1 = await load_run_traces(session, hub_id="hub-eval-1", run_id="run-100")
    assert len(traces1) == 3
    assert traces1[0].node_id == "node-router"

    # Traces for wrong hub_id must return empty list
    traces2 = await load_run_traces(session, hub_id="hub-eval-2", run_id="run-100")
    assert len(traces2) == 0


def test_block_assertion_engine_operators():
    engine = BlockAssertionEngine()
    tr = TraceRecord(
        node_id="node-test",
        node_type="AgentNode",
        sequence=1,
        input_state={},
        output_state={"response": "The sky is blue", "count": 42},
        latency_ms=150.0,
        timestamp=None,
    )

    # 1. equals
    res1 = engine.evaluate_single_trace(
        tr, "equals", {"field_path": "response"}, "The sky is blue", "eval-run-1"
    )
    assert res1.passed is True

    # 2. contains
    res2 = engine.evaluate_single_trace(
        tr, "contains", {"field_path": "response"}, "blue", "eval-run-1"
    )
    assert res2.passed is True

    # 3. not_contains
    res3 = engine.evaluate_single_trace(
        tr, "not_contains", {"field_path": "response"}, "red", "eval-run-1"
    )
    assert res3.passed is True

    # 4. regex
    res4 = engine.evaluate_single_trace(
        tr, "regex", {"field_path": "response"}, r"sky\s+is\s+blue", "eval-run-1"
    )
    assert res4.passed is True

    # 5. latency_under
    res5 = engine.evaluate_single_trace(
        tr, "latency_under", {}, "200.0", "eval-run-1"
    )
    assert res5.passed is True

    res5_fail = engine.evaluate_single_trace(
        tr, "latency_under", {}, "100.0", "eval-run-1"
    )
    assert res5_fail.passed is False


def test_block_assertion_engine_redacted_field():
    engine = BlockAssertionEngine()
    tr = TraceRecord(
        node_id="node-sec",
        node_type="ActionNode",
        sequence=1,
        input_state={},
        output_state={"api_key": "[REDACTED]"},
        latency_ms=50.0,
        timestamp=None,
    )

    res = engine.evaluate_single_trace(
        tr, "equals", {"field_path": "api_key"}, "secret-123", "eval-run-1"
    )
    assert res.passed is False
    assert res.metric_reason == "FIELD_REDACTED"


@pytest.mark.asyncio
async def test_evaluate_node_assertions_unexecuted_and_agent_target(async_session: AsyncSession):
    session = async_session

    c_missing = EvalTestCase(
        id="tc-missing",
        suite_id="s1",
        input_query="Q",
        node_id="nonexistent-node",
        assertion_type="equals",
        assertion_config={"field_path": "output"},
        expected_value="val",
    )
    c_agent = EvalTestCase(
        id="tc-agent",
        suite_id="s1",
        input_query="Q",
        node_id="node-1",
        assertion_type="contains",
        expected_value="val",
    )

    # 1. Unexecuted node -> NODE_NOT_EXECUTED
    results_missing = await evaluate_node_assertions(
        session,
        hub_id="hub-eval-1",
        run_id="run-100",
        eval_run_id="eval-run-1",
        cases=[c_missing],
    )
    assert len(results_missing) == 1
    assert results_missing[0].passed is False
    assert "NODE_NOT_EXECUTED" in results_missing[0].metric_reason

    # 2. Agent target node assertion -> NODE_ASSERTION_ON_AGENT_TARGET
    results_agent = await evaluate_node_assertions(
        session,
        hub_id="hub-eval-1",
        run_id="run-100",
        eval_run_id="eval-run-1",
        cases=[c_agent],
        is_agent_target=True,
    )
    assert len(results_agent) == 1
    assert results_agent[0].passed is False
    assert results_agent[0].metric_reason == "NODE_ASSERTION_ON_AGENT_TARGET"
