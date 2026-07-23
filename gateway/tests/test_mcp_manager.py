"""Tests for MCP Server Registry CRUD & Health Checks (S5-05a)."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from common.models.database import MCPServer
from gateway.services.mcp_client import encrypt_token, decrypt_token


def test_token_encryption_decryption():
    plain = "secret-token-123"
    encrypted = encrypt_token(plain)
    assert encrypted is not None
    assert encrypted != plain
    decrypted = decrypt_token(encrypted)
    assert decrypted == plain


def test_mcp_server_model_attributes():
    server = MCPServer(
        name="SyntraFlow (Internal)",
        url="http://localhost:8012",
        transport="sse",
        auth_type="none",
        is_internal=True,
        is_active=True,
        health_status="healthy",
    )
    assert server.name == "SyntraFlow (Internal)"
    assert server.is_internal is True
    assert server.health_status == "healthy"
