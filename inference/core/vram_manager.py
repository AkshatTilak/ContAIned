"""VRAM Manager — GPU memory budget arbiter.

Manages lazy loading and unloading of models to prevent OOM crashes.
Only one instance per inference server process (singleton).
"""

import asyncio
import time
from typing import Any, Optional

from common.config.settings import settings
from common.observability.logger import get_logger

logger = get_logger("vram-manager")


class ModelSlot:
    """Represents a loaded model in VRAM."""

    def __init__(self, name: str, model: Any, vram_mb: int):
        self.name = name
        self.model = model
        self.vram_mb = vram_mb
        self.last_used: float = time.time()
        self.load_count: int = 0

    def touch(self) -> None:
        """Update last-used timestamp."""
        self.last_used = time.time()


class VRAMManager:
    """Singleton VRAM budget arbiter for the inference server.

    Coordinates model loading/unloading to stay within GPU memory limits.
    Models are lazy-loaded on first request and unloaded after idle timeout.
    """

    _instance: Optional["VRAMManager"] = None

    def __init__(self, budget_mb: int = 20_000, idle_timeout: int = 300):
        self._slots: dict[str, ModelSlot] = {}
        self._budget_mb = budget_mb
        self._idle_timeout = idle_timeout
        self._lock = asyncio.Lock()
        self._loaders: dict[str, Any] = {}  # name -> loader callable
        self._cleanup_task: Optional[asyncio.Task] = None

    @classmethod
    def get_instance(cls, **kwargs) -> "VRAMManager":
        """Get or create the singleton VRAMManager."""
        if cls._instance is None:
            cls._instance = cls(**kwargs)
        return cls._instance

    def register_loader(self, name: str, loader_fn, vram_mb: int) -> None:
        """Register a model loader function.

        Args:
            name: Model identifier (e.g. 'qwen2.5-vl-7b').
            loader_fn: Async callable that returns the loaded model.
            vram_mb: Estimated VRAM usage in MB.
        """
        self._loaders[name] = {"fn": loader_fn, "vram_mb": vram_mb}
        logger.info("Registered model loader: %s (~%d MB)", name, vram_mb)

    async def ensure_loaded(self, name: str) -> Any:
        """Ensure a model is loaded in VRAM, loading it if necessary.

        If VRAM budget would be exceeded, evicts least-recently-used models first.

        Args:
            name: Model identifier.

        Returns:
            The loaded model instance.
        """
        async with self._lock:
            # Already loaded — just touch and return
            if name in self._slots:
                self._slots[name].touch()
                return self._slots[name].model

            if name not in self._loaders:
                raise ValueError(f"No loader registered for model: {name}")

            loader_info = self._loaders[name]
            needed_mb = loader_info["vram_mb"]

            # Evict models if needed to fit within budget
            await self._evict_to_fit(needed_mb)

            # Load the model
            logger.info("Loading model: %s (~%d MB)", name, needed_mb)
            start = time.time()
            model = await loader_info["fn"]()
            elapsed = time.time() - start

            slot = ModelSlot(name=name, model=model, vram_mb=needed_mb)
            slot.load_count += 1
            self._slots[name] = slot

            logger.info(
                "Model loaded: %s in %.2fs | VRAM used: %d/%d MB",
                name, elapsed, self.used_mb, self._budget_mb,
            )
            return model

    async def unload(self, name: str) -> None:
        """Explicitly unload a model from VRAM."""
        async with self._lock:
            if name in self._slots:
                slot = self._slots.pop(name)
                del slot.model
                logger.info("Unloaded model: %s | VRAM freed: ~%d MB", name, slot.vram_mb)

    async def _evict_to_fit(self, needed_mb: int) -> None:
        """Evict LRU models until there's room for needed_mb."""
        while self.used_mb + needed_mb > self._budget_mb and self._slots:
            lru_name = min(self._slots, key=lambda k: self._slots[k].last_used)
            slot = self._slots.pop(lru_name)
            del slot.model
            logger.info("Evicted model (LRU): %s | Freed: ~%d MB", lru_name, slot.vram_mb)

    @property
    def used_mb(self) -> int:
        """Current estimated VRAM usage in MB."""
        return sum(s.vram_mb for s in self._slots.values())

    def list_loaded(self) -> list[dict[str, Any]]:
        """List all currently loaded models."""
        return [
            {
                "name": s.name,
                "vram_mb": s.vram_mb,
                "last_used": s.last_used,
                "load_count": s.load_count,
            }
            for s in self._slots.values()
        ]

    async def cleanup_idle(self) -> None:
        """Unload models that have been idle beyond the timeout threshold."""
        async with self._lock:
            now = time.time()
            to_evict = [
                name for name, slot in self._slots.items()
                if (now - slot.last_used) > self._idle_timeout
            ]
            for name in to_evict:
                slot = self._slots.pop(name)
                del slot.model
                logger.info(
                    "Unloaded idle model: %s (idle %.0fs)", name, now - slot.last_used
                )

    async def start_cleanup_loop(self, interval: int = 60) -> None:
        """Start background loop that periodically cleans up idle models."""
        async def _loop():
            while True:
                await asyncio.sleep(interval)
                await self.cleanup_idle()

        self._cleanup_task = asyncio.create_task(_loop())
        logger.info("VRAM cleanup loop started (interval=%ds)", interval)

    async def stop_cleanup_loop(self) -> None:
        """Stop the background cleanup loop."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            logger.info("VRAM cleanup loop stopped")
