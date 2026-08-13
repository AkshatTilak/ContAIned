
import pytest
pytestmark = pytest.mark.unit
import pytest
import inspect
from projects.syntraflow.src.worker import process_ingestion_job

def test_process_ingestion_job_signature():
    """Verify that process_ingestion_job signature has default value for is_video_audio."""
    sig = inspect.signature(process_ingestion_job)
    param = sig.parameters["is_video_audio"]
    assert param.default == False
