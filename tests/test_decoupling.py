"""Unit tests for microservice architectural decoupling."""

import sys
from pathlib import Path


def test_gateway_and_inference_decoupling():
    """Assert that gateway modules do not import inference, and inference modules do not import gateway."""
    root_dir = Path(__file__).resolve().parent.parent

    gateway_files = list((root_dir / "gateway").rglob("*.py"))
    inference_files = list((root_dir / "inference").rglob("*.py"))

    gateway_violating_files = []
    for f in gateway_files:
        content = f.read_text(encoding="utf-8")
        if "from inference" in content or "import inference" in content:
            gateway_violating_files.append(str(f))

    inference_violating_files = []
    for f in inference_files:
        content = f.read_text(encoding="utf-8")
        if "from gateway" in content or "import gateway" in content:
            inference_violating_files.append(str(f))

    assert len(gateway_violating_files) == 0, f"Gateway files import inference: {gateway_violating_files}"
    assert len(inference_violating_files) == 0, f"Inference files import gateway: {inference_violating_files}"
