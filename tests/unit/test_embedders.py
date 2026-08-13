
import pytest
pytestmark = pytest.mark.unit
"""Unit tests for Syntraflow Embedders & Harrier 0.6B Integration (sub_07_02)."""

import pytest
from projects.syntraflow.src.embedders.registry import (
    EMBEDDER_REGISTRY,
    get_embedder_spec,
    list_supported_embedders,
)
from projects.syntraflow.src.embedders.harrier import HarrierEmbedder


def test_embedder_registry_lookup():
    spec = get_embedder_spec("harrier-0.6b")
    assert spec.model_id == "harrier-0.6b"
    assert spec.dimension == 768
    assert spec.modality == "text"
    assert spec.is_local is True


def test_list_supported_embedders():
    embedders = list_supported_embedders()
    model_ids = [e["model_id"] for e in embedders]
    assert "harrier-0.6b" in model_ids
    assert "jina-clip-v2" in model_ids


def test_harrier_embedder_single_text():
    embedder = HarrierEmbedder(dimension=768)
    vec = embedder.embed_text("Test document chunk for vector RAG")
    assert isinstance(vec, list)
    assert len(vec) == 768


def test_harrier_embedder_batch_text():
    embedder = HarrierEmbedder(dimension=768)
    texts = ["First chunk", "Second chunk", "Third chunk"]
    vecs = embedder.embed_text(texts)
    assert isinstance(vecs, list)
    assert len(vecs) == 3
    for v in vecs:
        assert len(v) == 768
