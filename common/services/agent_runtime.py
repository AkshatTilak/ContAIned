"""Agent Runtime Manager with Redis Pub/Sub dynamic configuration sync (S6-05a).

All cache operations are strictly keyed by (hub_id, agent_id).
"""

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

    def _key(self, hub_id: str, agent_id: str) -> str:
        return f"{hub_id}:{agent_id}"

    def get_agent(self, hub_id: str, agent_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached agent configuration by (hub_id, agent_id)."""
        return self._cache.get(self._key(hub_id, agent_id))

    def set_agent_in_cache(self, hub_id: str, agent_id: str, data: Dict[str, Any]) -> None:
        """Directly update cache for (hub_id, agent_id)."""
        self._cache[self._key(hub_id, agent_id)] = data

    def evict_hub(self, hub_id: str) -> int:
        """Purge all cached agents for a specific hub."""
        prefix = f"{hub_id}:"
        keys_to_del = [k for k in self._cache if k.startswith(prefix)]
        for k in keys_to_del:
            self._cache.pop(k, None)
        logger.info("Evicted %d agent cache entries for hub '%s'.", len(keys_to_del), hub_id)
        return len(keys_to_del)

    async def reload_agent(self, hub_id: str, agent_id: str) -> Optional[Dict[str, Any]]:
        """Fetch updated agent definition from database and refresh memory cache."""
        SessionLocal = get_sessionmaker()
        async with SessionLocal() as db:
            stmt = select(AgentDefinition).where(
                AgentDefinition.id == agent_id,
                AgentDefinition.hub_id == hub_id,
            )
            res = await db.execute(stmt)
            agent = res.scalar_one_or_none()

            key = self._key(hub_id, agent_id)
            if not agent:
                self._cache.pop(key, None)
                logger.info("Agent %s in hub %s deleted; removed from runtime cache.", agent_id, hub_id)
                return None

            config = {
                "id": agent.id,
                "hub_id": agent.hub_id,
                "endpoint_slug": agent.endpoint_slug,
                "name": agent.name,
                "role": agent.role,
                "system_prompt": agent.system_prompt,
                "model_id": agent.model_id,
                "tools": agent.tools or [],
                "collection_bindings": agent.collection_bindings_json or [],
                "temperature": agent.temperature,
                "max_tokens": agent.max_tokens,
                "is_active": agent.is_active,
                "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
            }
            self._cache[key] = config
            logger.info("Agent %s in hub %s successfully reloaded into runtime cache.", agent_id, hub_id)
            return config

    async def handle_sync_event(self, event: Dict[str, Any]) -> None:
        """Callback for incoming Redis agent-config-updates messages."""
        action = event.get("action")
        hub_id = event.get("hub_id")
        agent_id = event.get("agent_id")
        logger.info("Received Redis agent sync event: action=%s, hub_id=%s, agent_id=%s", action, hub_id, agent_id)

        if not hub_id:
            logger.warning("Agent sync event missing required 'hub_id', ignoring.")
            return

        if action == "hub_evicted":
            self.evict_hub(hub_id)
            return

        if not agent_id:
            return

        if action in ["created", "updated"]:
            await self.reload_agent(hub_id, agent_id)
        elif action == "deleted":
            self._cache.pop(self._key(hub_id, agent_id), None)
            logger.info("Agent %s (hub %s) purged from cache due to delete event.", agent_id, hub_id)

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
