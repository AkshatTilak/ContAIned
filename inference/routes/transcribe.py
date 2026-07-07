"""Inference transcription (ASR) router."""

from fastapi import APIRouter, File, UploadFile

from inference.core.vram_manager import VRAMManager

router = APIRouter(tags=["transcribe"])
vram = VRAMManager.get_instance()


@router.post("/transcribe")
async def perform_transcription(audio: UploadFile = File(...)) -> dict:
    """Lazy-loads SenseVoice-Small and transcribes speech audio track."""
    model = await vram.ensure_loaded("sensevoice-small")
    audio_bytes = await audio.read()
    result = await model.transcribe_audio(audio_bytes)
    return result
