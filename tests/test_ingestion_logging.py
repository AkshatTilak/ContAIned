"""Unit tests for Syntraflow Ingestion Pipeline Logging & Metrics (sub_07_03)."""

import logging
import pytest
from projects.syntraflow.src.ingestion.logging_context import log_pipeline_stage


def test_log_pipeline_stage_success(caplog):
    caplog.set_level(logging.INFO, logger="syntraflow.ingestion")
    
    with log_pipeline_stage("test_parsing", document_id="doc-123", hub_id="hub-456"):
        pass

    assert "Starting ingestion stage 'test_parsing' [doc_id=doc-123] [hub_id=hub-456]..." in caplog.text
    assert "Completed ingestion stage 'test_parsing' [doc_id=doc-123] [hub_id=hub-456] in" in caplog.text


def test_log_pipeline_stage_failure(caplog):
    caplog.set_level(logging.ERROR, logger="syntraflow.ingestion")

    with pytest.raises(ValueError, match="Simulated parsing error"):
        with log_pipeline_stage("test_chunking", document_id="doc-999"):
            raise ValueError("Simulated parsing error")

    assert "Failed ingestion stage 'test_chunking' [doc_id=doc-999]" in caplog.text
    assert "Simulated parsing error" in caplog.text
