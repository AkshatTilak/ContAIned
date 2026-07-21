"""Unit tests for EvalOps attribution database schemas."""

import uuid
import pytest
from sqlalchemy import select

from common.clients.postgres import get_sessionmaker, close_postgres
from common.models.database import AgentDefinition, EvalTestSuite, EvalTestCase, EvalRunHistory


@pytest.mark.asyncio
async def test_eval_attribution_schema_crud():
    """Verify CRUD operations and foreign key cascades on Eval attribution models."""
    await close_postgres()
    SessionLocal = get_sessionmaker()

    async with SessionLocal() as db:
        agent_id = str(uuid.uuid4())
        agent = AgentDefinition(
            id=agent_id,
            name="Eval Test Agent",
            role="assistant",
            system_prompt="You evaluate test data.",
            model_id="gemini-3.5-flash",
        )
        db.add(agent)
        await db.commit()

        # 1. Create EvalTestSuite
        suite = EvalTestSuite(
            agent_id=agent_id,
            name="RAG Quality Benchmark",
            description="Test suite for evaluating retrieval relevance.",
        )
        db.add(suite)
        await db.commit()
        await db.refresh(suite)

        assert suite.id is not None
        assert suite.agent_id == agent_id

        # 2. Create EvalTestCase
        case = EvalTestCase(
            suite_id=suite.id,
            input_query="What is SyntraFlow?",
            expected_output="SyntraFlow is a dynamic RAG ingestion engine.",
            expected_context="SyntraFlow RAG docs.",
        )
        db.add(case)
        await db.commit()
        await db.refresh(case)

        assert case.id is not None
        assert case.suite_id == suite.id

        # 3. Create EvalRunHistory
        run = EvalRunHistory(
            agent_id=agent_id,
            suite_id=suite.id,
            faithfulness_score=0.92,
            relevance_score=0.88,
            duration_sec=1.45,
            run_status="completed",
            details_json={"total_cases": 1, "passed": 1},
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)

        assert run.id is not None
        assert run.faithfulness_score == 0.92

        # 4. Clean up
        await db.delete(agent)
        await db.commit()

        # Verify cascade deletion
        res = await db.execute(select(EvalTestSuite).where(EvalTestSuite.id == suite.id))
        assert res.scalar_one_or_none() is None
