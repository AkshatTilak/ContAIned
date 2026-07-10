"""Inference transcription (ASR) router."""

from fastapi import APIRouter, File, UploadFile

from inference.core.vram_manager import VRAMManager

router = APIRouter(tags=["transcribe"])
vram = VRAMManager.get_instance()


@router.post("/transcribe")
async def perform_transcription(audio: UploadFile = File(...)) -> dict:
    """Lazy-loads the active ASR model and transcribes speech audio track."""
    from common.models.registry import get_active_model
    model_spec = await get_active_model("asr")
    model = await vram.ensure_loaded(model_spec.model_id)
    audio_bytes = await audio.read()
    result = await model.transcribe_audio(audio_bytes)
    return result
