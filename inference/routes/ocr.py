"""Inference OCR router."""

from fastapi import APIRouter, File, UploadFile

from inference.core.vram_manager import VRAMManager

router = APIRouter(tags=["ocr"])
vram = VRAMManager.get_instance()


@router.post("/ocr")
async def perform_ocr(image: UploadFile = File(...)) -> dict:
    """Lazy-loads Baidu Unlimited-OCR and runs layout extraction on the uploaded page."""
    model = await vram.ensure_loaded("baidu-ocr")
    image_bytes = await image.read()
    result = await model.extract_layout(image_bytes)
    return result
