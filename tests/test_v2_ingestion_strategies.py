"""Unit tests for SyntraFlow Ingestion Strategies, Chunkers, Processors, and API.
"""

import pytest
from projects.syntraflow.src.ingestion.strategies import (
    BaseChunker,
    BasePreProcessor,
    BasePostProcessor,
    ChunkerConfig,
)
from projects.syntraflow.src.ingestion.chunkers import (
    RecursiveCharacterChunking,
    FixedSizeChunking,
    SemanticChunking,
)
from projects.syntraflow.src.ingestion.processors import (
    OCRNoiseReduction,
    LanguageFilter,
    MetadataExtractor,
    SummaryTagger,
)


def test_chunker_interfaces():
    config = ChunkerConfig(chunk_size=100, chunk_overlap=10)
    rec_chunker = RecursiveCharacterChunking(config)
    fix_chunker = FixedSizeChunking(config)

    sample_text = "ContAIned platform version 2 provides modular RAG pipelines and custom LLM routing." * 5
    
    rec_chunks = rec_chunker.chunk(sample_text)
    assert len(rec_chunks) > 0
    assert "text" in rec_chunks[0]

    fix_chunks = fix_chunker.chunk(sample_text)
    assert len(fix_chunks) > 0


def test_pre_processors():
    ocr_proc = OCRNoiseReduction()
    raw_bytes = b"Sample text ==== with **** noise \x00 symbols."
    cleaned = ocr_proc.process(raw_bytes)
    assert b"====" not in cleaned
    assert b"****" not in cleaned

    lang_proc = LanguageFilter()
    raw_lang_bytes = b"Normalized text \x00 with null bytes."
    cleaned_lang = lang_proc.process(raw_lang_bytes)
    assert b"\x00" not in cleaned_lang


def test_post_processors():
    meta_proc = MetadataExtractor()
    chunk = {"text": "ContAIned is built by AI engineering teams.", "metadata": {}}
    enriched = meta_proc.enrich(chunk)
    assert "metadata" in enriched
    assert "entities" in enriched["metadata"]

    summary_proc = SummaryTagger()
    summarized = summary_proc.enrich({"text": "ContAIned platform is scalable and modular.", "metadata": {}})
    assert "summary" in summarized["metadata"]
    assert "tags" in summarized["metadata"]
