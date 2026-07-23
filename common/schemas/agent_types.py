"""Shared Pydantic models for scatter-gather agent orchestration.

These schemas define the contracts between GuardRoute's subagents
and the synthesis layer, ensuring structured handoff.
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


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
    latency_ms: float = Field(default=0.0, description="Execution latency in milliseconds")
    model_used: Optional[str] = Field(default=None, description="Name/ID of the model used")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    error_message: Optional[str] = Field(default=None, description="Error details if status is error/timeout")



class ClassificationResult(BaseModel):
    """Output from the task classifier (Arch-Router)."""

    complexity: TaskComplexity
    required_agents: list[str] = Field(
        description="List of subagent names needed for this task"
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


from datetime import datetime


class AgentCreate(BaseModel):
    """Schema for creating a new Agent Definition."""

    name: str = Field(..., min_length=1, max_length=100, description="Unique display name of the agent")
    role: str = Field(..., min_length=1, max_length=100, description="Agent domain role")
    system_prompt: str = Field(..., min_length=1, description="System prompt instructions")
    model_id: str = Field(..., description="Target model ID from Model Registry")
    tools: list[str] = Field(default_factory=list, description="Enabled tool names")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(default=2048, gt=0, description="Max response tokens")
    is_active: bool = Field(default=True, description="Activation status of the agent")
    endpoint_slug: Optional[str] = Field(default=None, description="Friendly URL slug for agent")


class AgentUpdate(BaseModel):
    """Schema for updating an existing Agent Definition."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    role: Optional[str] = Field(default=None, min_length=1, max_length=100)
    system_prompt: Optional[str] = Field(default=None, min_length=1)
    model_id: Optional[str] = Field(default=None)
    tools: Optional[list[str]] = Field(default=None)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    is_active: Optional[bool] = Field(default=None)
    endpoint_slug: Optional[str] = Field(default=None)


class AgentResponse(BaseModel):
    """Schema for Agent Definition API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    role: str
    system_prompt: str
    model_id: str
    tools: list[str]
    temperature: float
    max_tokens: int
    is_active: bool = True
    endpoint_slug: Optional[str] = None
    created_at: datetime
    updated_at: datetime

