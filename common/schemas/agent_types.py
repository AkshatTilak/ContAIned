"""Shared Pydantic models for scatter-gather agent orchestration.

These schemas define the contracts between GuardRoute's subagents
and the synthesis layer, ensuring structured handoff.
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class TaskComplexity(str, Enum):
    """Task complexity classification output from Arch-Router."""

    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


class SubAgentStatus(str, Enum):
    """Execution status of a subagent in the scatter phase."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    TIMEOUT = "timeout"
    ERROR = "error"


class SubAgentResult(BaseModel):
    """Structured output from a single subagent in the scatter-gather flow.

    Every subagent must return this schema, ensuring the gather/synthesis
    phase has consistent data to work with.
    """

    source: str = Field(description="Name of the subagent (e.g. 'retrieval', 'coding', 'web_search')")
    status: SubAgentStatus = Field(default=SubAgentStatus.PENDING)
    content_type: str = Field(default="text", description="Type of content: text, code, json, markdown")
    content: str = Field(default="", description="The actual output content")
    token_count: int = Field(default=0, description="Approximate token count of content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    error_message: Optional[str] = Field(default=None, description="Error details if status is error/timeout")


class ClassificationResult(BaseModel):
    """Output from the task classifier (Arch-Router)."""

    complexity: TaskComplexity
    required_agents: list[str] = Field(
        description="List of subagent names needed for this task"
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
