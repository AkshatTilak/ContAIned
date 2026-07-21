"""Unit and integration tests for V2 EvalOps synthetic generation and evaluation runner pipeline.
"""

import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock

from projects.evalops.src.generation.synthetic import generate_synthetic_test_cases
from projects.evalops.src.runner.consumer import process_agent_eval_run, publish_eval_trigger_event


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_synthetic_generation_pipeline(mock_db):
    agent_id = str(uuid.uuid4())

    mock_agent = MagicMock()
    mock_agent.id = agent_id
    mock_agent.name = "Test Agent"
    mock_agent.role = "Senior Developer"
    mock_agent.system_prompt = "You write Python."

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_agent
    mock_db.execute.return_value = mock_result

    mock_llm_response = MagicMock()
    mock_llm_response.choices = [
        MagicMock(
            message=MagicMock(
                content='[{"input_query": "How to create FastAPI route?", "expected_output": "Use @app.get()", "expected_context": "FastAPI docs"}]'
            )
        )
    ]

    with patch("projects.evalops.src.generation.synthetic.completion_with_fallback", new=AsyncMock(return_value=mock_llm_response)):
        res = await generate_synthetic_test_cases(
            db=mock_db,
            agent_id=agent_id,
            count=1
        )

    assert res["status"] == "success"
    assert res["agent_id"] == agent_id
    assert res["count"] == 1
    assert res["test_cases"][0]["input_query"] == "How to create FastAPI route?"


@pytest.mark.asyncio
async def test_eval_runner_execution(mock_db):
    agent_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    mock_history = MagicMock()
    mock_history.id = run_id
    mock_history.agent_id = agent_id
    mock_history.run_status = "pending"

    mock_agent = MagicMock()
    mock_agent.id = agent_id
    mock_agent.model_id = "gemini/gemini-3.5-flash"
    mock_agent.system_prompt = "Assist with benchmarks."

    # Return history on first execute, agent on second, suite on third, test cases on fourth
    res1 = MagicMock()
    res1.scalar_one_or_none.return_value = mock_history

    res2 = MagicMock()
    res2.scalar_one_or_none.return_value = mock_agent

    res3 = MagicMock()
    res3.scalar_one_or_none.return_value = "mock_suite_id"

    res4 = MagicMock()
    res4.scalars.return_value.all.return_value = []

    mock_db.execute.side_effect = [res1, res2, res3, res4]

    mock_session_context = AsyncMock()
    mock_session_context.__aenter__.return_value = mock_db
    mock_session_context.__aexit__.return_value = None

    with patch("projects.evalops.src.runner.consumer.get_sessionmaker", return_value=lambda: mock_session_context), \
         patch("projects.evalops.src.runner.consumer.completion_with_fallback", new=AsyncMock()):
        res = await process_agent_eval_run({
            "agent_id": agent_id,
            "run_id": run_id
        })

    assert res["status"] == "completed"
    assert res["run_id"] == run_id


def test_publish_eval_trigger_fallback():
    with patch("confluent_kafka.Producer", side_effect=Exception("Kafka Offline")):
        success = publish_eval_trigger_event("agent_123", "run_456")
        assert success is False
