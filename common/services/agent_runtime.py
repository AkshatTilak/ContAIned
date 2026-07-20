"""Agent Runtime Manager with Redis Pub/Sub dynamic configuration sync."""

import asyncio
import logging
from typing import Any, Dict, Optional

from sqlalchemy import select
from common.clients.postgres import get_sessionmaker
from common.clients.redis import subscribe_channel
from common.models.database import AgentDefinition

logger = logging.getLogger("common.services.agent_runtime")


class AgentRuntimeManager:
    """In-memory agent configuration cache with real-time Redis sync capabilities."""

    _instance: Optional["AgentRuntimeManager"] = None

    def __init__(self) -> None:
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._listener_task: Optional[asyncio.Task] = None

    @classmethod
    def get_instance(cls) -> "AgentRuntimeManager":
        if cls._instance is None:
            cls._instance = AgentRuntimeManager()
        return cls._instance

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached agent configuration by agent_id."""
        return self._cache.get(agent_id)

    def set_agent_in_cache(self, agent_id: str, data: Dict[str, Any]) -> None:
        """Directly update cache (useful for mock/testing)."""
        self._cache[agent_id] = data

    async def reload_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Fetch updated agent definition from database and refresh memory cache."""
        SessionLocal = get_sessionmaker()
        async with SessionLocal() as db:
            stmt = select(AgentDefinition).where(AgentDefinition.id == agent_id)
            res = await db.execute(stmt)
            agent = res.scalar_one_or_none()

            if not agent:
                self._cache.pop(agent_id, None)
                logger.info("Agent %s deleted from database; removed from runtime cache.", agent_id)
                return None

            config = {
                "id": agent.id,
                "name": agent.name,
                "role": agent.role,
                "system_prompt": agent.system_prompt,
                "model_id": agent.model_id,
                "tools": agent.tools or [],
                "temperature": agent.temperature,
                "max_tokens": agent.max_tokens,
                "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
            }
            self._cache[agent_id] = config
            logger.info("Agent %s successfully reloaded into runtime cache.", agent_id)
            return config

    async def handle_sync_event(self, event: Dict[str, Any]) -> None:
        """Callback for incoming Redis agent-config-updates messages."""
        action = event.get("action")
        agent_id = event.get("agent_id")
        logger.info("Received Redis agent sync event: action=%s, agent_id=%s", action, agent_id)

        if not agent_id:
            return

        if action in ["created", "updated"]:
            await self.reload_agent(agent_id)
        elif action == "deleted":
            self._cache.pop(agent_id, None)
            logger.info("Agent %s purged from cache due to delete event.", agent_id)

    async def start_listener(self) -> None:
        """Start listening to Redis channel in background task."""
        if self._listener_task is None or self._listener_task.done():
            self._listener_task = asyncio.create_task(
                subscribe_channel("agent-config-updates", self.handle_sync_event)
            )
            logger.info("Agent runtime sync listener started.")

    async def stop_listener(self) -> None:
        """Cancel background listener task."""
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None
            logger.info("Agent runtime sync listener stopped.")
