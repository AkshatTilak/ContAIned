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
    """Inference server lifespan — starts VRAM cleanup loop and registers loaders."""
    await vram.start_cleanup_loop(interval=60)
    logger.info("Inference server started — VRAM budget: %d MB", vram._budget_mb)
    
    # Dynamically register model loaders from the DB registry on startup
    await register_loaders_from_db()
    
    yield
    await vram.stop_cleanup_loop()
    logger.info("Inference server shut down")


app = FastAPI(
    title="Inference Server",
    description="GPU model serving for contained-ai-platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(RequestIdMiddleware)


async def register_loaders_from_db() -> None:
    """Query enabled local models from DB Model Registry and register them in VRAMManager."""
    try:
        from sqlalchemy import select
        from common.clients.postgres import get_sessionmaker
        from common.models.database import ModelRegistryModel
        
        from inference.models.baidu_ocr import load_baidu_ocr
        from inference.models.jina_clip import load_jina_clip
        from inference.models.sensevoice import load_sensevoice
        from inference.models.classifier import load_classifier
        from inference.models.glm_ocr import load_glm_ocr

        loader_mapping = {
            "THUDM/GLM-OCR": load_glm_ocr,
            "paddleocr": load_baidu_ocr,
            "baidu-ocr": load_baidu_ocr,
            "FunAudioLLM/SenseVoiceSmall": load_sensevoice,
            "Arch-Router-1.5B": load_classifier,
            "jinaai/jina-clip-v2": load_jina_clip,
        }

        session_factory = get_sessionmaker()
        async with session_factory() as session:
            result = await session.execute(
                select(ModelRegistryModel)
                .where(ModelRegistryModel.mode == "local")
                .where(ModelRegistryModel.is_enabled == True)
            )
            models = result.scalars().all()
            
            # Reset loaders
            vram._loaders.clear()
            vram._semaphores.clear()
            
            for model in models:
                loader_fn = loader_mapping.get(model.model_id)
                if loader_fn:
                    vram_mb = model.vram_mb or 1000
                    # Register under various identifier patterns for robustness
                    vram.register_loader(model.model_id, loader_fn, vram_mb)
                    vram.register_loader(model.model_id.lower(), loader_fn, vram_mb)
                    vram.register_loader(model.display_name.lower(), loader_fn, vram_mb)
                else:
                    logger.warning(
                        "No local loader found for model: %s (role=%s)",
                        model.model_id, model.role
                    )
            logger.info("Dynamic model loaders registered: %s", list(vram._loaders.keys()))
    except Exception as e:
        logger.error("Failed to dynamically register model loaders from DB registry: %s. Falling back to hardcoded defaults.", e)
        # Fallback registration
        from inference.models.baidu_ocr import load_baidu_ocr
        from inference.models.jina_clip import load_jina_clip
        from inference.models.sensevoice import load_sensevoice
        from inference.models.classifier import load_classifier
        from inference.models.glm_ocr import load_glm_ocr

        vram.register_loader("baidu-ocr", load_baidu_ocr, 5000)
        vram.register_loader("jina-clip-v2", load_jina_clip, 1000)
        vram.register_loader("sensevoice-small", load_sensevoice, 250)
        vram.register_loader("arch-router-1.5b", load_classifier, 2000)
        vram.register_loader("THUDM/GLM-OCR", load_glm_ocr, 2000)


@app.post("/reload")
async def reload_registry() -> dict:
    """Reload model loaders dynamically from the Model Registry database."""
    await register_loaders_from_db()
    return {
        "status": "success",
        "message": "Model registry loaders reloaded successfully.",
        "registered_models": list(vram._loaders.keys())
    }


@app.get("/health")
async def health_check() -> dict:
    """Inference server health — reports loaded models and VRAM usage."""
    device = settings.DEVICE
    if device == "auto":
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"

    return {
        "status": "healthy",
        "loaded_models": vram.list_loaded(),
        "vram_used_mb": vram.used_mb,
        "vram_budget_mb": vram._budget_mb,
        "device": device,
        "registered_models": list(vram._loaders.keys()),
        "latency_metrics": vram.get_latency_summary(),
    }


# Import routes (loaders are now loaded inside register_loaders_from_db)
from inference.routes import ocr, embed, transcribe, classify

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
