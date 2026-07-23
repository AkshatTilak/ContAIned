"""Tests for OpenAI-compatible External API Gateway endpoints (`/v1/*`)."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from common.models.database import APIKeyModel
from gateway.api.api_keys import hash_api_key
from gateway.auth.dependencies import get_db
from gateway.main import app


class MockResult:
    """Mock for SQLAlchemy execute() result that returns empty by default."""

    def __init__(self, scalar_value=None, all_values=None):
        self._scalar_value = scalar_value
        self._all_values = all_values or []

    def scalar_one_or_none(self):
        return self._scalar_value

    def scalars(self):
        return self

    def all(self):
        return self._all_values

    def scalar(self):
        return 0


class MockDB:
    """Lightweight mock for FastAPI Depends(get_db) async session.
    
    Returns empty results for all queries — individual tests should
    patch endpoint-level functions if they need real data back.
    """

    def __init__(self):
        self.keys = []

    def add(self, item):
        if not hasattr(item, "id") or item.id is None:
            item.id = 1
        self.keys.append(item)

    async def execute(self, stmt):
        # Return empty results for all queries — the endpoint handlers
        # have fallback paths for when no models/agents are found.
        return MockResult()

    async def commit(self):
        pass

    async def refresh(self, item):
        pass


mock_db = MockDB()


class MockMiddlewareSession:
    """Async session mock for the middleware's own get_sessionmaker() context.
    
    The middleware does:
        session_factory = get_sessionmaker()
        async with session_factory() as db:
            res = await db.execute(stmt)
            api_key_obj = res.scalar_one_or_none()
    """

    def __init__(self, db_ref):
        self.db_ref = db_ref

    async def execute(self, stmt):
        target_key = self.db_ref.keys[0] if self.db_ref.keys else None
        return MockResult(scalar_value=target_key)

    async def commit(self):
        pass

    def add(self, item):
        pass


class MockSessionFactory:
    """Mimics get_sessionmaker() return value — callable that returns an async CM."""

    def __init__(self, session):
        self._session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        pass


@pytest.fixture(autouse=True)
def setup_mock_db():
    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    middleware_session = MockMiddlewareSession(mock_db)
    mock_factory = MockSessionFactory(middleware_session)

    with patch("gateway.auth.api_key_middleware.get_sessionmaker", return_value=mock_factory), \
         patch("gateway.auth.api_key_middleware.get_redis_client", return_value=None):
        yield

    app.dependency_overrides.clear()
    mock_db.keys.clear()


client = TestClient(app)


@pytest.fixture
def valid_api_key():
    raw_key = "sk-test-key-123456789"
    hashed = hash_api_key(raw_key)

    key_obj = APIKeyModel(
        id=1,
        key=hashed,
        prefix="sk-test-",
        name="Test Key",
        rate_limit=60,
        is_active=True,
    )
    mock_db.keys.clear()
    mock_db.add(key_obj)
    return raw_key


def test_v1_models_endpoint(valid_api_key):
    """Models endpoint should return an empty list when no models/agents are registered."""
    headers = {"Authorization": f"Bearer {valid_api_key}"}
    response = client.get("/v1/models", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert isinstance(data["data"], list)
    assert len(data["data"]) == 0  # No models registered in test DB


@patch("gateway.api.external.completion_with_fallback")
def test_v1_chat_completions_success(mock_completion, valid_api_key):
    """Chat completions should route to the direct model path when no agent matches."""
    class MockChoice:
        def __init__(self):
            self.message = type("Message", (), {"content": "Hello! How can I assist you today?"})()

    class MockUsage:
        def __init__(self):
            self.prompt_tokens = 10
            self.completion_tokens = 8

    class MockRes:
        def __init__(self):
            self.choices = [MockChoice()]
            self.usage = MockUsage()

    mock_completion.return_value = MockRes()

    headers = {"Authorization": f"Bearer {valid_api_key}"}
    payload = {
        "model": "gemini/gemini-3.5-flash",
        "messages": [{"role": "user", "content": "Hello"}],
        "temperature": 0.7,
        "max_tokens": 100,
    }

    response = client.post("/v1/chat/completions", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "chat.completion"
    assert data["choices"][0]["message"]["content"] == "Hello! How can I assist you today?"
    assert data["usage"]["total_tokens"] == 18
    assert "X-RateLimit-Limit" in response.headers


def test_v1_auth_unauthorized():
    """Missing auth header should return 401."""
    response = client.get("/v1/models")
    assert response.status_code == 401
    assert "error" in response.json()


def test_v1_invalid_key():
    """An invalid key should return 401."""
    empty_session = MockMiddlewareSession(MockDB())  # empty keys → returns None
    empty_factory = MockSessionFactory(empty_session)

    with patch("gateway.auth.api_key_middleware.get_sessionmaker", return_value=empty_factory), \
         patch("gateway.auth.api_key_middleware.get_redis_client", return_value=None):
        headers = {"Authorization": "Bearer sk-invalid-key-xyz"}
        response = client.get("/v1/models", headers=headers)
        assert response.status_code == 401
        assert "error" in response.json()
