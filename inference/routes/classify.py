"""Inference task classification router."""

from fastapi import APIRouter
from pydantic import BaseModel

from inference.core.vram_manager import VRAMManager

router = APIRouter(tags=["classify"])
vram = VRAMManager.get_instance()


class ClassifyRequest(BaseModel):
    """Routing request payload containing prompt."""

    prompt: str


@router.post("/classify")
async def perform_classification(req: ClassifyRequest) -> dict:
    """Lazy-loads the active task classifier model and categorizes complexity and routing list."""
    from common.models.registry import get_active_model
    model_spec = await get_active_model("classifier")
    model = await vram.ensure_loaded(model_spec.model_id)
    result = await model.classify_prompt(req.prompt)
    return result
