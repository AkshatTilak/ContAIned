"""Shared API request/response schemas.

Standardizes health check, error, and pagination payloads across backends.
"""

from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class HealthResponse(BaseModel):
    """Standard health check response schema."""

    status: str = Field(default="healthy", description="Status of the application (healthy, degraded, down)")
    version: str = Field(default="0.1.0", description="Application version number")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional health and resource details")


class ErrorResponse(BaseModel):
    """Standard error response payload."""

    error_code: str = Field(..., description="Unique error code identifier")
    message: str = Field(..., description="Human-readable error description")
    details: Optional[dict[str, Any]] = Field(default=None, description="Detailed error information or context")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard wrapper for paginated collections."""

    items: list[T] = Field(..., description="List of items in the current page")
    total: int = Field(..., description="Total number of items in the collection")
    page: int = Field(..., description="Current page number (1-indexed)")
    size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")
