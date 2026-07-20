"""Explicit OpenAPI schema contracts for Gateway <-> Inference Server communication."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EmbeddingsRequest(BaseModel):
    """Payload format sent to POST /v1/embeddings."""

    texts: List[str] = Field(..., description="List of text strings to embed")
    model: Optional[str] = Field(default=None, description="Optional target embedding model ID")


class EmbeddingsResponse(BaseModel):
    """Response format returned by POST /v1/embeddings."""

    embeddings: List[List[float]] = Field(..., description="List of embedding vectors")
    model: str = Field(default="default", description="Model used for embedding generation")
    dimension: int = Field(..., description="Dimensionality of embedding vectors")


class OCRBlock(BaseModel):
    """Single layout block extracted by layout OCR."""

    type: str = Field(default="paragraph")
    content: str = Field(default="")
    bbox: Optional[List[float]] = None


class OCRResponse(BaseModel):
    """Response format returned by POST /v1/ocr."""

    text: str = Field(..., description="Full layout-preserving markdown text")
    blocks: List[Dict[str, Any]] = Field(default_factory=list)
    tables: List[Dict[str, Any]] = Field(default_factory=list)
    layout: Dict[str, Any] = Field(default_factory=dict)


class TranscriptionSegment(BaseModel):
    """Single timed audio segment in transcription output."""

    start: float = Field(..., description="Segment start timestamp in seconds")
    end: float = Field(..., description="Segment end timestamp in seconds")
    text: str = Field(..., description="Transcribed segment text")
    confidence: Optional[float] = Field(default=1.0)


class TranscriptionResponse(BaseModel):
    """Response format returned by POST /v1/transcribe."""

    text: str = Field(..., description="Full audio transcription text")
    segments: List[TranscriptionSegment] = Field(default_factory=list)
    emotion: str = Field(default="neutral")
    audio_events: List[str] = Field(default_factory=list)
    language: str = Field(default="en")


class InferenceHealthResponse(BaseModel):
    """Response format returned by GET /v1/health."""

    status: str = Field(default="healthy")
    gpu_available: bool = Field(default=False)
    loaded_models: List[str] = Field(default_factory=list)
