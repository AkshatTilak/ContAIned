"""Inference embeddings router."""

import base64
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from inference.core.vram_manager import VRAMManager

router = APIRouter(tags=["embed"])
vram = VRAMManager.get_instance()


class EmbedRequest(BaseModel):
    """Text and/or image embedding inputs."""

    texts: Optional[list[str]] = None
    images: Optional[list[str]] = None  # Base64 encoded images
    model: Optional[str] = None


@router.post("/embed")
async def perform_embedding(req: EmbedRequest) -> dict:
    """Lazy-loads requested embedding model (or active default) and computes embeddings."""
    if not req.texts and not req.images:
        raise HTTPException(status_code=400, detail="Must provide 'texts' or 'images'")

    target_model_id = req.model
    if not target_model_id:
        from common.models.registry import get_active_model
        model_spec = await get_active_model("embedding")
        target_model_id = model_spec.model_id

    model = await vram.ensure_loaded(target_model_id)
    embeddings = []

    if req.texts:
        text_embeds = await model.embed_texts(req.texts)
        embeddings.extend(text_embeds)

    if req.images:
        image_bytes_list = []
        for img_b64 in req.images:
            try:
                img_bytes = base64.b64decode(img_b64)
                image_bytes_list.append(img_bytes)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid base64 image encoding")

        img_embeds = await model.embed_images(image_bytes_list)
        embeddings.extend(img_embeds)

    return {"embeddings": embeddings}
