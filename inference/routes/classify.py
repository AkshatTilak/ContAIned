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
    """Lazy-loads Arch-Router-1.5B GGUF and categorizes complexity and routing list."""
    model = await vram.ensure_loaded("arch-router-1.5b")
    result = await model.classify_prompt(req.prompt)
    return result
