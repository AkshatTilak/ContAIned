"""Inference server HTTP client.

Provides a typed async client for calling the inference server's
OpenAI-compatible API endpoints. Used by projects (syntraflow, guardroute)
to call model inference without loading models in the gateway process.
"""

import asyncio
import time
from typing import Any, Optional

import httpx

from common.config.settings import settings
from common.observability.logger import get_logger

logger = get_logger("inference-client")


class InferenceClient:
    """Async HTTP client for the inference server.

    All model inference (OCR, ASR, embeddings, classification) goes through
    this client. Projects never load GPU models directly.
    """

    def __init__(self, base_url: Optional[str] = None, timeout: Optional[float] = None):
        """Initializes client with settings configurations."""
        self.base_url = (base_url or settings.INFERENCE_SERVER_URL).rstrip("/")
        self.timeout = timeout or getattr(settings, "INFERENCE_TIMEOUT", 120.0)
        self._client: Optional[httpx.AsyncClient] = None
        
        # Circuit Breaker state
        self._consecutive_failures = 0
        self._is_degraded = False
        self._last_failure_time = 0.0
        self._degraded_cooldown = 30.0  # seconds
        self._max_failures = 5

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

    async def _execute_request_with_retry(
        self, method: str, path: str, **kwargs: Any
    ) -> httpx.Response:
        """Executes HTTP request with transient retry policies and circuit breaker checks."""
        # 1. Check Circuit Breaker
        if self._is_degraded:
            now = time.time()
            if now - self._last_failure_time < self._degraded_cooldown:
                logger.error("Circuit breaker: inference server is degraded. Request blocked.")
                raise RuntimeError("Inference server is degraded due to consecutive failures")
            else:
                logger.info("Circuit breaker: cooldown elapsed, attempting recovery request.")

        retries = 0
        max_retries = 3
        delay = 1.0

        while True:
            try:
                client = await self._get_client()
                if method.upper() == "GET":
                    resp = await client.get(path, **kwargs)
                elif method.upper() == "POST":
                    resp = await client.post(path, **kwargs)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                # Raise exception on transient 502/503/504 errors so they trigger retry
                if resp.status_code in (502, 503, 504):
                    resp.raise_for_status()

                # Successful request: Reset failure count and circuit breaker
                self._consecutive_failures = 0
                self._is_degraded = False
                return resp

            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                # Determine if the error is a transient network or server error
                is_transient = False
                if isinstance(e, httpx.HTTPStatusError):
                    if e.response.status_code in (502, 503, 504):
                        is_transient = True
                elif isinstance(e, (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout)):
                    is_transient = True

                if is_transient and retries < max_retries:
                    retries += 1
                    logger.warning(
                        "Inference client request failed (transient). Retry %d/%d in %.2f seconds. Error: %s",
                        retries, max_retries, delay, e
                    )
                    await asyncio.sleep(delay)
                    delay *= 2.0
                    continue

                # Permanent failure or all retries exhausted: update circuit breaker state
                self._consecutive_failures += 1
                self._last_failure_time = time.time()
                if self._consecutive_failures >= self._max_failures:
                    self._is_degraded = True
                    logger.error(
                        "Inference client: %d consecutive failures. Server marked as DEGRADED.",
                        self._consecutive_failures
                    )

                logger.error("Inference request failed: %s", e)
                raise RuntimeError("Inference server request failed") from e

    async def health(self) -> dict[str, Any]:
        """Check inference server health and loaded models."""
        resp = await self._execute_request_with_retry("GET", "/health")
        return resp.json()

    async def ocr(self, image_bytes: bytes, filename: str = "page.png") -> dict[str, Any]:
        """Extract text, tables, and layout from an image/PDF page.

        Args:
            image_bytes: Raw image or PDF page bytes.
            filename: Filename hint for content-type detection.

        Returns:
            Dict with keys: text, tables, layout.
        """
        resp = await self._execute_request_with_retry(
            "POST", "/infer/ocr", files={"image": (filename, image_bytes)}
        )
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
        payload: dict[str, Any] = {}
        if texts:
            payload["texts"] = texts
        # Images sent as base64 in JSON for simplicity
        if images:
            import base64
            payload["images"] = [base64.b64encode(img).decode() for img in images]
            
        resp = await self._execute_request_with_retry("POST", "/infer/embed", json=payload)
        return resp.json()["embeddings"]

    async def transcribe(self, audio_bytes: bytes, filename: str = "audio.wav") -> dict[str, Any]:
        """Transcribe audio file bytes to text segments.

        Args:
            audio_bytes: Raw audio file bytes.
            filename: Filename hint for format detection.

        Returns:
            Dict with keys:
                text: Full transcribed text string.
                segments: List of segment dicts with start, end, text, confidence.
                emotion: Detected speaker emotion (if supported by ASR model, else null).
                audio_events: List of detected events (if supported by ASR model, else null).
                language: Detected language code.
        """
        resp = await self._execute_request_with_retry(
            "POST", "/infer/transcribe", files={"audio": (filename, audio_bytes)}
        )
        return resp.json()

    async def classify(self, prompt: str) -> dict[str, Any]:
        """Classify task complexity and required agents using Arch-Router.

        Args:
            prompt: User prompt to classify.

        Returns:
            Dict with keys: complexity (simple/medium/complex),
            required_agents (list of agent names).
        """
        resp = await self._execute_request_with_retry(
            "POST", "/infer/classify", json={"prompt": prompt}
        )
        return resp.json()
