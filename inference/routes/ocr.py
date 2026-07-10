"""Inference OCR router."""

from fastapi import APIRouter, File, UploadFile

from inference.core.vram_manager import VRAMManager

router = APIRouter(tags=["ocr"])
vram = VRAMManager.get_instance()


@router.post("/ocr")
async def perform_ocr(image: UploadFile = File(...)) -> dict:
    """Lazy-loads the active OCR model and runs layout extraction on the uploaded page."""
    from common.models.registry import get_active_model
    model_spec = await get_active_model("ocr")
    model = await vram.ensure_loaded(model_spec.model_id)
    image_bytes = await image.read()
    result = await model.extract_layout(image_bytes)
    return result
