"""Shared fixtures and async SSE / WebSocket utilities for streaming integration tests.

Provides:
- In-process threaded Gateway server for real socket-level WebSocket and SSE streaming.
- SSE stream parsing and collection helpers.
- WebSocket async connection context manager via `websockets`.
- Event filtering and assertion utilities.
"""

import asyncio
import json
import socket
import threading
import time
from typing import Any, AsyncGenerator, Dict, List, Optional
import pytest
from httpx import AsyncClient
import uvicorn
import websockets

from gateway.auth.utils import create_access_token
from gateway.main import app


def _get_free_port() -> int:
    """Find an available port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def gateway_server_port():
    return _get_free_port()


@pytest.fixture(scope="session", autouse=True)
def run_gateway_server(gateway_server_port):
    """Run real Gateway instance on a dedicated TCP port in a background daemon thread."""
    thread = threading.Thread(
        target=uvicorn.run,
        args=(app,),
        kwargs={"host": "127.0.0.1", "port": gateway_server_port, "log_level": "warning"},
        daemon=True,
    )
    thread.start()

    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", gateway_server_port), timeout=0.1):
                break
        except (OSError, ConnectionRefusedError):
            time.sleep(0.1)

    yield f"http://127.0.0.1:{gateway_server_port}"


@pytest.fixture(autouse=True)
def reset_sse_starlette_event():
    """Ensure sse_starlette AppStatus.should_exit_event is created on current event loop."""
    try:
        import anyio
        from sse_starlette.sse import AppStatus
        AppStatus.should_exit_event = anyio.Event()
    except Exception:
        pass


@pytest.fixture
async def streaming_client(gateway_server_port):
    """Async HTTP client connected to the live threaded Gateway."""
    async with AsyncClient(base_url=f"http://127.0.0.1:{gateway_server_port}", timeout=15.0) as client:
        yield client


@pytest.fixture
def ws_url(gateway_server_port):
    """Base WebSocket URL for the live threaded Gateway."""
    return f"ws://127.0.0.1:{gateway_server_port}"


async def _auth_headers(user) -> dict:
    """Build Authorization header for a user."""
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


async def parse_sse_stream(stream_generator: AsyncGenerator[bytes, None]) -> AsyncGenerator[Dict[str, Any], None]:
    """Parse raw SSE chunk byte stream into structured event dicts: {'event': str, 'data': dict|str}."""
    current_event = "message"
    buffer = ""

    async for chunk in stream_generator:
        text = chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        buffer += text
        while "\n\n" in buffer:
            event_raw, buffer = buffer.split("\n\n", 1)
            lines = event_raw.strip().split("\n")
            data_lines = []
            for line in lines:
                if line.startswith("event:"):
                    current_event = line.replace("event:", "").strip()
                elif line.startswith("data:"):
                    data_lines.append(line.replace("data:", "").strip())

            if data_lines:
                data_str = "\n".join(data_lines)
                try:
                    parsed_data = json.loads(data_str)
                except Exception:
                    parsed_data = data_str

                yield {
                    "event": current_event,
                    "data": parsed_data,
                }
                current_event = "message"


async def collect_all_events(
    client: AsyncClient,
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    timeout_s: float = 8.0,
    max_events: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Connect to an SSE endpoint and collect events until stream completion or max_events reached."""
    events: List[Dict[str, Any]] = []

    async def _reader():
        if method.upper() == "POST":
            async with client.stream("POST", url, headers=headers, json=json_body, timeout=timeout_s) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    raise AssertionError(f"SSE stream {url} returned HTTP {response.status_code}: {body.decode('utf-8', errors='replace')}")
                async for evt in parse_sse_stream(response.aiter_bytes()):
                    events.append(evt)
                    if max_events and len(events) >= max_events:
                        break
                    if evt.get("data") == "[DONE]":
                        break
        else:
            async with client.stream("GET", url, headers=headers, timeout=timeout_s) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    raise AssertionError(f"SSE stream {url} returned HTTP {response.status_code}: {body.decode('utf-8', errors='replace')}")
                async for evt in parse_sse_stream(response.aiter_bytes()):
                    events.append(evt)
                    if max_events and len(events) >= max_events:
                        break
                    if evt.get("data") == "[DONE]":
                        break

    try:
        await asyncio.wait_for(_reader(), timeout=timeout_s)
    except asyncio.TimeoutError:
        pass

    return events


async def wait_for_event(
    client: AsyncClient,
    url: str,
    target_event: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    timeout_s: float = 8.0,
) -> Optional[Dict[str, Any]]:
    """Wait for a specific SSE event name on a streaming endpoint."""
    events = await collect_all_events(
        client, url, method=method, headers=headers, json_body=json_body, timeout_s=timeout_s
    )
    for evt in events:
        if evt.get("event") == target_event:
            return evt
    return None
