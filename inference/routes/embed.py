"""Inference embeddings router."""

import base64
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from inference.core.vram_manager import VRAMManager

router = APIRouter(tags=["embed"])
vram = VRAMManager.get_instance()


class EmbedRequest(BaseModel):
    """Text and/or image embedding inputs."""

    texts: Optional[list[str]] = None
    images: Optional[list[str]] = None  # Base64 encoded images


@router.post("/embed")
async def perform_embedding(req: EmbedRequest) -> dict:
    """Lazy-loads jina-clip-v2 and computes embeddings for texts/images."""
    if not req.texts and not req.images:
        raise HTTPException(status_code=400, detail="Must provide 'texts' or 'images'")

    from common.models.registry import get_active_model
    model_spec = await get_active_model("embedding")
    model = await vram.ensure_loaded(model_spec.model_id)
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
