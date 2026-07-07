"""Inference server HTTP client.

Provides a typed async client for calling the inference server's
OpenAI-compatible API endpoints. Used by projects (syntraflow, guardroute)
to call model inference without loading models in the gateway process.
"""

from typing import Any, Optional

import httpx

from common.observability.logger import get_logger

logger = get_logger("inference-client")


class InferenceClient:
    """Async HTTP client for the inference server.

    All model inference (OCR, ASR, embeddings, classification) goes through
    this client. Projects never load GPU models directly.
    """

    def __init__(self, base_url: str = "http://localhost:8010", timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP connection."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def health(self) -> dict[str, Any]:
        """Check inference server health and loaded models."""
        client = await self._get_client()
        resp = await client.get("/health")
        resp.raise_for_status()
        return resp.json()

    async def ocr(self, image_bytes: bytes, filename: str = "page.png") -> dict[str, Any]:
        """Extract text, tables, and layout from an image/PDF page.

        Args:
            image_bytes: Raw image or PDF page bytes.
            filename: Filename hint for content-type detection.

        Returns:
            Dict with keys: text, tables, layout.
        """
        client = await self._get_client()
        resp = await client.post(
            "/infer/ocr",
            files={"image": (filename, image_bytes)},
        )
        resp.raise_for_status()
        return resp.json()


    async def embed(
        self, texts: list[str] | None = None, images: list[bytes] | None = None
    ) -> list[list[float]]:
        """Generate embeddings for text and/or images using jina-clip-v2.

        Args:
            texts: List of text strings to embed.
            images: List of raw image bytes to embed.

        Returns:
            List of embedding vectors.
        """
        client = await self._get_client()
        payload: dict[str, Any] = {}
        if texts:
            payload["texts"] = texts
        # Images sent as base64 in JSON for simplicity
        if images:
            import base64
            payload["images"] = [base64.b64encode(img).decode() for img in images]
        resp = await client.post("/infer/embed", json=payload)
        resp.raise_for_status()
        return resp.json()["embeddings"]

    async def transcribe(self, audio_bytes: bytes, filename: str = "audio.wav") -> dict[str, Any]:
        """Transcribe audio using Whisper-v3-turbo.

        Args:
            audio_bytes: Raw audio file bytes.
            filename: Filename hint for format detection.

        Returns:
            Dict with keys: text, segments (with timestamps).
        """
        client = await self._get_client()
        resp = await client.post(
            "/infer/transcribe",
            files={"audio": (filename, audio_bytes)},
        )
        resp.raise_for_status()
        return resp.json()

    async def classify(self, prompt: str) -> dict[str, Any]:
        """Classify task complexity and required agents using Arch-Router.

        Args:
            prompt: User prompt to classify.

        Returns:
            Dict with keys: complexity (simple/medium/complex),
            required_agents (list of agent names).
        """
        client = await self._get_client()
        resp = await client.post(
            "/infer/classify",
            json={"prompt": prompt},
        )
        resp.raise_for_status()
        return resp.json()
