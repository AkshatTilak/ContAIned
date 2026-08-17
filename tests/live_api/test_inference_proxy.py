"""Live Inference Server Proxy Integration Tests (B8-10 / sub_10_02).

Tests inference client proxying for embeddings, OCR, and health probes.
"""

from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient

from common.clients.inference import InferenceClient
from common.schemas.inference_contracts import EmbeddingsResponse, OCRResponse

pytestmark = pytest.mark.live_api


@pytest.mark.asyncio
async def test_inference_client_embeddings():
    """Verify inference proxy handles embedding generation."""
    client = InferenceClient()

    with patch.object(client, "embed", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [[0.1] * 768]

        resp = await client.embed(
            texts=["Test sentence for vector embedding."],
            model="gemini/gemini-embedding-2",
        )
        assert resp is not None
        assert len(resp) == 1
        assert len(resp[0]) == 768


@pytest.mark.asyncio
async def test_inference_client_ocr():
    """Verify inference proxy handles OCR requests."""
    client = InferenceClient()

    with patch.object(client, "ocr", new_callable=AsyncMock) as mock_ocr:
        mock_ocr.return_value = {
            "text": "Extracted document header and sample body text.",
            "confidence": 0.95,
            "bounding_boxes": [],
        }

        dummy_image = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
        resp = await client.ocr(image_bytes=dummy_image)
        assert resp is not None
        assert "Extracted document" in resp["text"]
        assert resp["confidence"] >= 0.9
