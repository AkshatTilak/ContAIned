"""Pydantic schemas for the Model Registry.

Defines the structure and constraints of registry records.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class ModelRole(str, Enum):
    """Supported roles of models in the platform."""

    OCR = "ocr"
    ASR = "asr"
    EMBEDDING = "embedding"
    CLASSIFIER = "classifier"
    COMPLETION = "completion"


class ModelMode(str, Enum):
    """Deployment modes for a model."""

    LOCAL = "local"
    CLOUD = "cloud"
    AUTO = "auto"


class ModelSpec(BaseModel):
    """Pydantic model representing a registry entry.

    Describes metadata, parameters, and structural capabilities of a model.
    """

    id: Optional[int] = Field(default=None, description="Database unique identifier")
    role: ModelRole = Field(description="Role of the model (ocr, asr, etc.)")
    mode: ModelMode = Field(description="Deployment mode (local or cloud)")
    provider: str = Field(description="Model provider (huggingface, gemini, etc.)")
    model_id: str = Field(description="HuggingFace repo ID, API model string, or local path")
    display_name: str = Field(description="Human-readable model name")
    framework: Optional[str] = Field(default=None, description="Execution framework (transformers, litellm, etc.)")
    vram_mb: Optional[int] = Field(default=None, description="Estimated VRAM usage in MB; null for cloud models")
    vector_dim: Optional[int] = Field(default=None, description="Vector dimension size for embedding models; null otherwise")
    context_window: Optional[int] = Field(default=None, description="Maximum context window in tokens")
    quantization: Optional[str] = Field(default=None, description="Quantization level (fp16, q4_k_m, GGUF, etc.)")
    is_default: bool = Field(default=False, description="Whether this is the default option for the role")
    is_enabled: bool = Field(default=True, description="Whether the model is enabled for resolution")
    priority: int = Field(default=0, description="Fallback priority order (lower = higher priority)")
    metadata_json: Optional[dict[str, Any]] = Field(default_factory=dict, description="Additional custom metadata")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
