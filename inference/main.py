"""Main entry point for the Inference Server backend.

GPU-bound FastAPI server that serves all local models behind
a unified API. Manages VRAM lifecycle via VRAMManager.

Run: uvicorn inference.main:app --host 0.0.0.0 --port 8010
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI

from common.config.settings import settings
from common.observability.logger import get_logger, RequestIdMiddleware
from inference.core.vram_manager import VRAMManager

logger = get_logger("inference")

# Initialize VRAM manager singleton
vram = VRAMManager.get_instance(
    budget_mb=settings.VRAM_BUDGET_MB,
    idle_timeout=settings.CLASSIFIER_IDLE_TIMEOUT,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Inference server lifespan — starts VRAM cleanup loop."""
    await vram.start_cleanup_loop(interval=60)
    logger.info("Inference server started — VRAM budget: %d MB", vram._budget_mb)
    yield
    await vram.stop_cleanup_loop()
    logger.info("Inference server shut down")


app = FastAPI(
    title="Inference Server",
    description="GPU model serving for akshat-ai-platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(RequestIdMiddleware)


@app.get("/health")
async def health_check() -> dict:
    """Inference server health — reports loaded models and VRAM usage."""
    return {
        "status": "healthy",
        "loaded_models": vram.list_loaded(),
        "vram_used_mb": vram.used_mb,
    }


# Import loaders and routes
from inference.models.baidu_ocr import load_baidu_ocr
from inference.models.jina_clip import load_jina_clip
from inference.models.sensevoice import load_sensevoice
from inference.models.classifier import load_classifier

from inference.routes import ocr, embed, transcribe, classify

# Register loaders in VRAM manager
vram.register_loader("baidu-ocr", load_baidu_ocr, 5000)          # Est. 5 GB VRAM
vram.register_loader("jina-clip-v2", load_jina_clip, 1000)       # Est. 1 GB VRAM
vram.register_loader("sensevoice-small", load_sensevoice, 250)   # Est. 250 MB VRAM
vram.register_loader("arch-router-1.5b", load_classifier, 2000)  # Est. 2 GB VRAM


# --- Route registration ---
app.include_router(ocr.router, prefix="/infer")
app.include_router(embed.router, prefix="/infer")
app.include_router(transcribe.router, prefix="/infer")
app.include_router(classify.router, prefix="/infer")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "inference.main:app",
        host="0.0.0.0",
        port=settings.INFERENCE_SERVER_PORT,
        reload=settings.APP_ENV == "development",
    )
