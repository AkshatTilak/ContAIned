"""Standardized exception hierarchy and error response models for ContAIned platform."""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ErrorResponseSchema(BaseModel):
    """Standardized JSON error schema returned across all microservice REST APIs."""

    error_code: str = Field(..., description="Unique machine-readable error classification identifier")
    message: str = Field(..., description="Human-readable description of the error")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Structured contextual information")
    trace_id: Optional[str] = Field(default=None, description="Request correlation trace identifier")


class ContAInedException(Exception):
    """Base exception class for all platform-defined errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}


class EntityNotFoundException(ContAInedException):
    """Raised when a requested resource or database entity is not found."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            message=message,
            error_code="ENTITY_NOT_FOUND",
            status_code=404,
            details=details,
        )


class ValidationErrorException(ContAInedException):
    """Raised when input validation or business constraint fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400,
            details=details,
        )


class ExternalServiceException(ContAInedException):
    """Raised when an external API, database, or subservice call fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            message=message,
            error_code="EXTERNAL_SERVICE_ERROR",
            status_code=502,
            details=details,
        )


class DatabaseException(ContAInedException):
    """Raised when a database transaction or operation fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            status_code=500,
            details=details,
        )
