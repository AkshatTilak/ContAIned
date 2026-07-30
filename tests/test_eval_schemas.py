"""Unit tests for Eval Hub polymorphic schemas and database models."""

import pytest
from pydantic import ValidationError

from common.schemas.evalops import (
    EvalTarget,
    EvalSuiteCreate,
    EvalTestCaseCreate,
    EvalRunRequest,
)
from common.models.database import (
    EvalTestSuite,
    EvalTestCase,
    EvalRunHistory,
    EVAL_TARGET_TYPES,
    NODE_ASSERTION_TYPES,
)


def test_eval_target_schema_valid():
    target = EvalTarget(type="agent", target_hub_id="hub-1", target_id="agt-1")
    assert target.type == "agent"
    assert target.target_hub_id == "hub-1"

    wf_target = EvalTarget(type="workflow", target_hub_id="hub-2", target_id="wf-1")
    assert wf_target.type == "workflow"


def test_eval_target_schema_invalid_type():
    with pytest.raises(ValidationError):
        EvalTarget(type="invalid_target", target_hub_id="hub-1", target_id="id-1")


def test_eval_suite_create_schema():
    suite_req = EvalSuiteCreate(
        name="Regression Suite",
        description="Eval suite for workflow",
        target=EvalTarget(type="workflow", target_hub_id="hub-wf", target_id="wf-123")
    )
    assert suite_req.name == "Regression Suite"
    assert suite_req.target.type == "workflow"


def test_eval_test_case_create_node_assertion_validation():
    # 1. Whole-response test case (no node assertion) -> Valid
    c1 = EvalTestCaseCreate(input_query="Hello", expected_output="Hi")
    assert c1.node_id is None

    # 2. Complete node assertion -> Valid
    c2 = EvalTestCaseCreate(
        input_query="Hello",
        node_id="node-agent-1",
        assertion_type="contains",
        expected_value="success"
    )
    assert c2.node_id == "node-agent-1"
    assert c2.assertion_type == "contains"

    # 3. Incomplete node assertion (missing expected_value) -> Invalid
    with pytest.raises(ValidationError) as excinfo:
        EvalTestCaseCreate(
            input_query="Hello",
            node_id="node-agent-1",
            assertion_type="contains"
        )
    assert "INCOMPLETE_NODE_ASSERTION" in str(excinfo.value)

    # 4. Invalid assertion type -> Invalid
    with pytest.raises(ValidationError):
        EvalTestCaseCreate(
            input_query="Hello",
            node_id="node-agent-1",
            assertion_type="invalid_assertion",
            expected_value="val"
        )


def test_eval_constants():
    assert "agent" in EVAL_TARGET_TYPES
    assert "workflow" in EVAL_TARGET_TYPES
    assert "contains" in NODE_ASSERTION_TYPES
    assert "latency_under" in NODE_ASSERTION_TYPES
