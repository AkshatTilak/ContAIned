"""Pydantic schemas for Eval Hub evaluation test suites, test cases, and runs."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, model_validator

from common.models.database import NODE_ASSERTION_TYPES


class EvalTarget(BaseModel):
    """Polymorphic target for evaluation test suites and runs."""

    type: Literal["agent", "workflow"]
    target_hub_id: str
    target_id: str


class EvalSuiteCreate(BaseModel):
    """Payload to create an evaluation test suite."""

    name: str
    description: Optional[str] = None
    target: EvalTarget


class EvalSuiteUpdate(BaseModel):
    """Payload to update an evaluation test suite."""

    name: Optional[str] = None
    description: Optional[str] = None
    target: Optional[EvalTarget] = None


class EvalSuiteResponse(BaseModel):
    """Response payload for an evaluation test suite."""

    id: str
    hub_id: str
    name: str
    description: Optional[str] = None
    target: EvalTarget
    target_name: Optional[str] = None
    target_status: str = "ok"  # ok | link_revoked | missing
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class EvalTestCaseCreate(BaseModel):
    """Payload to create an evaluation test case."""

    input_query: str
    expected_output: Optional[str] = None
    expected_context: Optional[str] = None
    node_id: Optional[str] = None
    assertion_type: Optional[str] = None
    assertion_config: Optional[Dict[str, Any]] = None
    expected_value: Optional[str] = None

    @model_validator(mode="after")
    def validate_node_assertion(self) -> "EvalTestCaseCreate":
        has_node = self.node_id is not None
        has_type = self.assertion_type is not None
        has_exp = self.expected_value is not None

        if (has_node or has_type or has_exp) and not (has_node and has_type and has_exp):
            raise ValueError(
                "INCOMPLETE_NODE_ASSERTION: node_id, assertion_type, and expected_value must all be provided together"
            )

        if self.assertion_type is not None and self.assertion_type not in NODE_ASSERTION_TYPES:
            raise ValueError(
                f"Invalid assertion_type: {self.assertion_type}. Must be one of {NODE_ASSERTION_TYPES}"
            )

        return self


class EvalTestCaseResponse(BaseModel):
    """Response payload for an evaluation test case."""

    id: str
    suite_id: str
    input_query: str
    expected_output: Optional[str] = None
    expected_context: Optional[str] = None
    node_id: Optional[str] = None
    assertion_type: Optional[str] = None
    assertion_config: Optional[Dict[str, Any]] = None
    expected_value: Optional[str] = None
    created_at: Optional[str] = None


class EvalRunRequest(BaseModel):
    """Payload to request an evaluation run."""

    suite_id: str
    framework: Optional[str] = "both"
    metrics: Optional[List[str]] = None
    thresholds: Optional[Dict[str, float]] = None


class EvalRunResponse(BaseModel):
    """Response payload for an evaluation run request."""

    id: str
    hub_id: str
    suite_id: Optional[str] = None
    target: EvalTarget
    run_status: str = "queued"
    created_at: Optional[str] = None
