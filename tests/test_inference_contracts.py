"""Unit tests for Inference API contract models and InferenceClient validation."""

import pytest
from common.schemas.inference_contracts import (
    EmbeddingsRequest,
    EmbeddingsResponse,
    OCRResponse,
    TranscriptionResponse,
    TranscriptionSegment,
)


def test_embeddings_request_validation():
    """Verify EmbeddingsRequest schema validation."""
    req = EmbeddingsRequest(texts=["hello world", "test chunk"])
    assert len(req.texts) == 2
    assert req.model is None


def test_embeddings_response_validation():
    """Verify EmbeddingsResponse schema validation."""
    res = EmbeddingsResponse(embeddings=[[0.1, 0.2, 0.3]], model="jina-clip-v2", dimension=3)
    assert len(res.embeddings[0]) == 3
    assert res.dimension == 3


def test_ocr_response_validation():
    """Verify OCRResponse schema validation."""
    data = {
        "text": "# Header\nParagraph text",
        "blocks": [{"type": "header", "content": "Header"}],
        "tables": [],
        "layout": {},
    }
    ocr = OCRResponse.model_validate(data)
    assert ocr.text.startswith("# Header")
    assert len(ocr.blocks) == 1


def test_transcription_response_validation():
    """Verify TranscriptionResponse schema validation."""
    segment = TranscriptionSegment(start=0.0, end=5.0, text="Hello world", confidence=0.95)
    tx = TranscriptionResponse(text="Hello world", segments=[segment], language="en")
    assert tx.segments[0].start == 0.0
    assert tx.segments[0].confidence == 0.95
