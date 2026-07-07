"""Vector database client wrapper for Qdrant.

Shared across all projects and backends.
"""

import logging
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

from common.config.settings import settings

logger = logging.getLogger("common.qdrant")


class VectorClient:
    """Wrapper class for Qdrant client interactions."""

    def __init__(self) -> None:
        """Initializes the QdrantClient using settings configuration."""
        try:
            self._client = QdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY,
            )
        except Exception as e:
            logger.error("Failed to initialize Qdrant client: %s", e)
            raise RuntimeError("Vector store client initialization failed") from e

    def get_client(self) -> QdrantClient:
        """Access the underlying QdrantClient directly.

        Returns:
            The raw QdrantClient instance.
        """
        return self._client

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
