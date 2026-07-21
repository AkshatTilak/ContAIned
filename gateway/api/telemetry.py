"""Gateway Real-time Telemetry Streaming & Redis Pub/Sub Bridge.

Provides WebSocket and Server-Sent Events (SSE) endpoints streaming system health,
VRAM utilization, CPU/Memory metrics, and live processing events to the frontend dashboard.
"""

import asyncio
import json
import logging
import time
from typing import AsyncGenerator
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sse_starlette.sse import EventSourceResponse

from common.clients.redis import get_redis_client, publish_event
from common.config.settings import settings

router = APIRouter(prefix="/telemetry", tags=["telemetry"])
logger = logging.getLogger("gateway.api.telemetry")

TELEMETRY_CHANNEL = "telemetry-system-health"


async def _get_gpu_metrics() -> tuple[int, int, bool]:
    """Retrieves GPU VRAM metrics via PyTorch or nvidia-smi fallback."""
    try:
        import torch
        if torch.cuda.is_available():
            vram_used = int(torch.cuda.memory_allocated() / (1024 * 1024))
            vram_total = int(torch.cuda.get_device_properties(0).total_memory / (1024 * 1024))
            return vram_used, vram_total, True
    except Exception:
        pass

    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            if lines and "," in lines[0]:
                used, total = lines[0].split(",")
                return int(used.strip()), int(total.strip()), True
    except Exception:
        pass

    return 0, getattr(settings, "VRAM_BUDGET_MB", 8000), False


async def collect_system_metrics() -> dict:
    """Collects system health, CPU, memory, disk, GPU VRAM, active agent, and job metrics."""
    try:
        import psutil
        cpu_percent = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        mem_percent = mem.percent
        disk_percent = psutil.disk_usage("/").percent
    except Exception:
        cpu_percent = 0.0
        mem_percent = 0.0
        disk_percent = 0.0

    vram_used, vram_total, gpu_available = await _get_gpu_metrics()

    active_agents = 0
    active_jobs_count = 0

    try:
        from common.clients.postgres import get_sessionmaker
        from sqlalchemy import text
        session_factory = get_sessionmaker()
        async with session_factory() as session:
            agents_res = await session.execute(text("SELECT COUNT(*) FROM agent_definitions"))
            active_agents = agents_res.scalar() or 0

            jobs_res = await session.execute(
                text("SELECT COUNT(*) FROM syntraflow_jobs WHERE status = 'processing'")
            )
            active_jobs_count = jobs_res.scalar() or 0
    except Exception as e:
        logger.debug(f"Telemetry database count query skipped: {e}")

    return {
        "event": "telemetry_update",
        "timestamp": time.time(),
        "cpu_usage_percent": cpu_percent,
        "memory_usage_percent": mem_percent,
        "disk_usage_percent": disk_percent,
        "vram_usage_mb": vram_used,
        "vram_total_mb": vram_total,
        "gpu_available": gpu_available,
        "active_agents": active_agents,
        "active_jobs_count": active_jobs_count,
        "status": "healthy",
    }


async def broadcast_telemetry_loop():
    """Background task that periodically samples system metrics and publishes to Redis."""
    while True:
        try:
            metrics = await collect_system_metrics()
            await publish_event(TELEMETRY_CHANNEL, metrics)
        except Exception as e:
            logger.debug(f"Telemetry loop publish skipped: {e}")
        await asyncio.sleep(3)


@router.websocket("/ws")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    """WebSocket streaming endpoint for real-time telemetry updates."""
    await websocket.accept()
    logger.info("WebSocket telemetry client connected.")

    pubsub = None
    try:
        r = get_redis_client()
        pubsub = r.pubsub() if r else None
        if pubsub:
            await pubsub.subscribe(TELEMETRY_CHANNEL)
    except Exception as e:
        logger.warning(f"Could not initialize Redis pubsub: {e}")
        pubsub = None

    try:
        # Send initial telemetry update immediately
        initial_metrics = await collect_system_metrics()
        await websocket.send_text(json.dumps(initial_metrics))

        while True:
            if pubsub:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    data_str = message["data"].decode("utf-8") if isinstance(message["data"], bytes) else message["data"]
                    await websocket.send_text(data_str)
                else:
                    await asyncio.sleep(1.0)
            else:
                # Fallback sampling if Redis pubsub unavailable
                metrics = await collect_system_metrics()
                await websocket.send_text(json.dumps(metrics))
                await asyncio.sleep(3.0)
    except WebSocketDisconnect:
        logger.info("WebSocket telemetry client disconnected.")
    except Exception as e:
        logger.warning(f"WebSocket telemetry connection error: {e}")
    finally:
        if pubsub:
            try:
                await pubsub.unsubscribe(TELEMETRY_CHANNEL)
            except Exception:
                pass


async def sse_telemetry_generator() -> AsyncGenerator[dict, None]:
    """Generator for Server-Sent Events telemetry streaming."""
    pubsub = None
    try:
        r = get_redis_client()
        pubsub = r.pubsub() if r else None
        if pubsub:
            await pubsub.subscribe(TELEMETRY_CHANNEL)
    except Exception as e:
        logger.warning(f"Could not initialize Redis pubsub for SSE: {e}")
        pubsub = None

    try:
        # Yield initial message
        initial_metrics = await collect_system_metrics()
        yield {"event": "telemetry", "data": json.dumps(initial_metrics)}

        while True:
            if pubsub:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    data_str = message["data"].decode("utf-8") if isinstance(message["data"], bytes) else message["data"]
                    yield {"event": "telemetry", "data": data_str}
                else:
                    await asyncio.sleep(1.0)
            else:
                metrics = await collect_system_metrics()
                yield {"event": "telemetry", "data": json.dumps(metrics)}
                await asyncio.sleep(3.0)
    except asyncio.CancelledError:
        logger.info("SSE telemetry stream cancelled.")
    finally:
        if pubsub:
            try:
                await pubsub.unsubscribe(TELEMETRY_CHANNEL)
            except Exception:
                pass


@router.get("/stream")
async def sse_telemetry_endpoint():
    """SSE endpoint for streaming telemetry data."""
    return EventSourceResponse(sse_telemetry_generator())
