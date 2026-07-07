"""Vector database client wrapper for Qdrant.

Shared across all projects and backends.
"""

import logging
from typing import Any, Optional

from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

from common.config.settings import settings

logger = logging.getLogger("common.qdrant")


class VectorClient:
    """Wrapper class for Qdrant client interactions."""

    def __init__(self) -> None:
        """Initializes both QdrantClient and AsyncQdrantClient using settings."""
        try:
            self._client = QdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY,
                timeout=settings.QDRANT_TIMEOUT,
                retries=settings.QDRANT_RETRIES,
            )
            self._async_client = AsyncQdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY,
                timeout=settings.QDRANT_TIMEOUT,
                retries=settings.QDRANT_RETRIES,
            )
            logger.info("Qdrant sync/async clients initialized.")
        except Exception as e:
            logger.error("Failed to initialize Qdrant client: %s", e)
            raise RuntimeError("Vector store client initialization failed") from e

    def get_client(self) -> QdrantClient:
        """Access the underlying QdrantClient directly.

        Returns:
            The raw QdrantClient instance.
        """
        return self._client

    def get_async_client(self) -> AsyncQdrantClient:
        """Access the underlying AsyncQdrantClient directly.

        Returns:
            The raw AsyncQdrantClient instance.
        """
        return self._async_client

    def search_similarity(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 5,
    ) -> list[Any]:
        """Perform similarity search on Qdrant.

        Args:
            collection_name: The name of the target vector collection.
            query_vector: The query embedding vector.
            limit: Maximum number of records to return.

        Returns:
            A list of search results.
        """
        try:
            results = self._client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
            )
            return results
        except (UnexpectedResponse, ValueError) as e:
            logger.error("Similarity search failed in Qdrant: %s", e)
            raise RuntimeError("Query failed inside Vector DB") from e

    async def async_search_similarity(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 5,
    ) -> list[Any]:
        """Perform asynchronous similarity search on Qdrant.

        Args:
            collection_name: The name of the target vector collection.
            query_vector: The query embedding vector.
            limit: Maximum number of records to return.

        Returns:
            A list of search results.
        """
        try:
            results = await self._async_client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
            )
            return results
        except (UnexpectedResponse, ValueError) as e:
            logger.error("Async similarity search failed in Qdrant: %s", e)
            raise RuntimeError("Query failed inside Vector DB") from e

    async def get_vector_dimension(self, db: Optional[Any] = None) -> int:
        """Get the active embedding model's vector dimension from the model registry.

        Falls back to 1024 if not found.
        """
        try:
            from common.models.registry import get_active_model
            model_spec = await get_active_model("embedding", db=db)
            if model_spec and model_spec.vector_dim:
                return model_spec.vector_dim
        except Exception as e:
            logger.warning("Failed to retrieve embedding vector dimension from registry: %s", e)
        return 1024
