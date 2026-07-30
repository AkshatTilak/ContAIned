"""Pydantic v2 schemas for Workflow Hub definitions, versions, graphs, and run execution."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

from common.models.hub_enums import (
    WORKFLOW_STATUSES,
    WORKFLOW_RUN_STATUSES,
    WORKFLOW_RUN_TRIGGERS,
)


class NodeReference(BaseModel):
    """Qualified cross-hub resource reference on a workflow node."""
    model_config = ConfigDict(from_attributes=True)

    type: Literal["agent", "collection", "workflow", "mcp_tool"]
    hub_id: str
    resource_id: str

    @model_validator(mode="before")
    @classmethod
    def normalize_resource_id(cls, data: Any) -> Any:
        if isinstance(data, dict):
            res_id = (
                data.get("resource_id")
                or data.get("agent_id")
                or data.get("collection_id")
                or data.get("workflow_id")
                or data.get("mcp_tool_id")
            )
            if res_id and not data.get("resource_id"):
                data["resource_id"] = res_id
        return data


class WorkflowGraph(BaseModel):
    """Workflow ReactFlow graph structure."""
    model_config = ConfigDict(from_attributes=True)

    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    edges: List[Dict[str, Any]] = Field(default_factory=list)
    viewport: Optional[Dict[str, Any]] = None


class ValidationIssue(BaseModel):
    """Validation issue item."""
    model_config = ConfigDict(from_attributes=True)

    node_id: Optional[str] = None
    node_type: Optional[str] = None
    code: Optional[str] = None
    level: str = Field(default="error", description="error | warning")
    message: str
    field: Optional[str] = None
    reference: Optional[Dict[str, Any]] = None


class ValidationResult(BaseModel):
    """Validation result payload."""
    model_config = ConfigDict(from_attributes=True)

    is_valid: bool = False
    errors: List[ValidationIssue] = Field(default_factory=list)
    warnings: List[ValidationIssue] = Field(default_factory=list)


class WorkflowCreate(BaseModel):
    """Request payload to create a workflow."""
    name: str = Field(..., max_length=120)
    slug: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = None
    tags_json: List[str] = Field(default_factory=list)
    graph: Optional[WorkflowGraph] = None


class WorkflowUpdate(BaseModel):
    """Request payload to update workflow metadata."""
    name: Optional[str] = Field(default=None, max_length=120)
    slug: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = None
    tags_json: Optional[List[str]] = None
    status: Optional[str] = None

    @field_validator("status")
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in WORKFLOW_STATUSES:
            raise ValueError(f"Invalid workflow status: {v}. Must be one of {WORKFLOW_STATUSES}")
        return v


class WorkflowSummary(BaseModel):
    """Summary of a workflow."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    hub_id: str
    name: str
    slug: str
    description: Optional[str] = None
    tags_json: List[str] = Field(default_factory=list)
    status: str
    published_version_id: Optional[str] = None
    draft_version_id: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class WorkflowDetail(WorkflowSummary):
    """Detailed view of a workflow including version details and etag."""
    draft_version_number: Optional[int] = None
    published_version_number: Optional[int] = None
    version_etag: Optional[str] = None
    draft_graph: Optional[WorkflowGraph] = None
    published_graph: Optional[WorkflowGraph] = None


class WorkflowVersionSummary(BaseModel):
    """Summary of a workflow version."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    workflow_id: str
    version_number: int
    change_note: Optional[str] = None
    is_valid: bool = False
    created_by: Optional[str] = None
    created_at: datetime


class WorkflowVersionDetail(WorkflowVersionSummary):
    """Detailed view of a workflow version including full graph and validation results."""
    graph_json: Dict[str, Any]
    validation_json: Optional[Dict[str, Any]] = None


class WorkflowRunSummary(BaseModel):
    """Summary of a workflow run execution."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    hub_id: str
    workflow_id: str
    version_id: Optional[str] = None
    trigger: str
    status: str
    error_message: Optional[str] = None
    node_count: Optional[int] = None
    duration_ms: Optional[int] = None
    started_by: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None

    @field_validator("trigger")
    def validate_trigger(cls, v: str) -> str:
        if v not in WORKFLOW_RUN_TRIGGERS:
            raise ValueError(f"Invalid run trigger: {v}. Must be one of {WORKFLOW_RUN_TRIGGERS}")
        return v

    @field_validator("status")
    def validate_status(cls, v: str) -> str:
        if v not in WORKFLOW_RUN_STATUSES:
            raise ValueError(f"Invalid run status: {v}. Must be one of {WORKFLOW_RUN_STATUSES}")
        return v


class WorkflowRunDetail(WorkflowRunSummary):
    """Detailed view of a workflow run execution including inputs and outputs."""
    input_json: Optional[Dict[str, Any]] = None
    output_json: Optional[Dict[str, Any]] = None
