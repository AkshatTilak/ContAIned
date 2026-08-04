from unittest.mock import patch
from contextlib import asynccontextmanager

@asynccontextmanager
async def noop(app):
    yield

with patch("gateway.core.setup.lifespan", noop):
    from gateway import main as m
    import importlib
    importlib.reload(m)
    from fastapi.testclient import TestClient
    c = TestClient(m.app)
    r = c.post("/auth/register", json={"email": "x@x.com", "password": "TestPass123!"})
    print("status:", r.status_code)
    print("body:", r.text)
