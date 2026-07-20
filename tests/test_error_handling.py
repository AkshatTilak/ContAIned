"""Unit tests for ContAIned standardized error handling and trace ID propagation."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from common.observability.exceptions import (
    EntityNotFoundException,
    ValidationErrorException,
    DatabaseException,
)
from common.observability.middleware import TraceIdMiddleware, register_exception_handlers

# Setup test app
test_app = FastAPI()
test_app.add_middleware(TraceIdMiddleware)
register_exception_handlers(test_app)


@test_app.get("/test-not-found")
async def route_not_found():
    raise EntityNotFoundException("Test entity with ID 'xyz' was not found.")


@test_app.get("/test-validation")
async def route_validation():
    raise ValidationErrorException("Invalid payload field 'name'.")


@test_app.get("/test-db-error")
async def route_db_error():
    raise DatabaseException("Database transaction deadlock.")


@pytest.mark.asyncio
async def test_entity_not_found_exception_schema():
    """Verify EntityNotFoundException returns status 404 and standardized JSON schema."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as ac:
        res = await ac.get("/test-not-found")
        assert res.status_code == 404
        data = res.json()
        assert data["error_code"] == "ENTITY_NOT_FOUND"
        assert "not found" in data["message"].lower()
        assert "X-Request-ID" in res.headers
        assert data["trace_id"] == res.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_validation_exception_schema():
    """Verify ValidationErrorException returns status 400 and standardized JSON schema."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as ac:
        res = await ac.get("/test-validation")
        assert res.status_code == 400
        data = res.json()
        assert data["error_code"] == "VALIDATION_ERROR"
        assert "invalid payload" in data["message"].lower()
        assert "X-Request-ID" in res.headers


@pytest.mark.asyncio
async def test_trace_id_propagation_header():
    """Verify incoming X-Request-ID is preserved and propagated."""
    custom_trace_id = "trace-custom-999"
    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as ac:
        res = await ac.get("/test-db-error", headers={"X-Request-ID": custom_trace_id})
        assert res.status_code == 500
        assert res.headers.get("X-Request-ID") == custom_trace_id
        data = res.json()
        assert data["trace_id"] == custom_trace_id
        assert data["error_code"] == "DATABASE_ERROR"
