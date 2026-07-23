"""OpenAI-Compatible External API Gateway endpoints (`/v1/*`).

Provides standard OpenAI SDK compatible endpoints:
- `POST /v1/chat/completions`: Chat completions for models or agent endpoint slugs (streaming & non-streaming)
- `POST /v1/embeddings`: Text embeddings via inference service
- `GET /v1/models`: List available models and agent slugs
"""

import time
import json
import uuid
import logging
from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from common.clients.litellm import completion_with_fallback
from common.clients.inference import InferenceClient
from common.models.database import AgentDefinition, ModelRegistryModel
from gateway.auth.dependencies import get_db

router = APIRouter(prefix="/v1", tags=["OpenAI External API Gateway"])
logger = logging.getLogger("gateway.api.external")


# --- OpenAI Pydantic Schemas ---

class ChatMessage(BaseModel):
    role: str
    content: str
    name: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 2048
    stream: Optional[bool] = False
    top_p: Optional[float] = 1.0


class EmbeddingRequest(BaseModel):
    input: Union[str, List[str]]
    model: Optional[str] = None


@router.post("/chat/completions")
async def chat_completions(
    req: ChatCompletionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """OpenAI-compatible chat completion endpoint.
    
    Supports both model names (e.g. 'gemini/gemini-3.5-flash') and agent endpoint_slugs (e.g. 'research-agent').
    Supports streaming (`stream: true`) in standard SSE format.
    """
    created_timestamp = int(time.time())
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    # 1. Check if model matches an agent endpoint_slug
    stmt = select(AgentDefinition).where(
        AgentDefinition.endpoint_slug == req.model,
        AgentDefinition.is_active == True
    )
    res = await db.execute(stmt)
    agent = res.scalar_one_or_none()

    if agent:
        system_prompt = agent.system_prompt
        model_to_use = agent.model_id
        formatted_messages = [{"role": "system", "content": system_prompt}] + [
            {"role": m.role, "content": m.content} for m in req.messages
        ]
        temp = req.temperature if req.temperature is not None else (agent.temperature or 0.7)
        max_toks = req.max_tokens if req.max_tokens is not None else (agent.max_tokens or 2048)
    else:
        model_to_use = req.model
        formatted_messages = [{"role": m.role, "content": m.content} for m in req.messages]
        temp = req.temperature or 0.7
        max_toks = req.max_tokens or 2048

    # Store for middleware logging
    request.state.model_used = model_to_use

    # Handle streaming response
    if req.stream:
        async def stream_generator():
            try:
                res = await completion_with_fallback(
                    model=model_to_use,
                    messages=formatted_messages,
                    temperature=temp,
                    max_tokens=max_toks,
                    stream=True,
                )
                async for chunk in res:
                    delta_content = chunk.choices[0].delta.content or "" if chunk.choices else ""
                    chunk_data = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created_timestamp,
                        "model": req.model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": delta_content},
                                "finish_reason": chunk.choices[0].finish_reason if chunk.choices else None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(chunk_data)}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error("Streaming error in /v1/chat/completions: %s", e)
                err_chunk = {
                    "error": {
                        "message": str(e),
                        "type": "server_error",
                        "code": "internal_error",
                    }
                }
                yield f"data: {json.dumps(err_chunk)}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(stream_generator(), media_type="text/event-stream")

    # Non-streaming response
    try:
        res = await completion_with_fallback(
            model=model_to_use,
            messages=formatted_messages,
            temperature=temp,
            max_tokens=max_toks,
            stream=False,
        )

        content = res.choices[0].message.content if res.choices else ""
        prompt_tokens = getattr(res.usage, "prompt_tokens", 0) if hasattr(res, "usage") and res.usage else 0
        completion_tokens = getattr(res.usage, "completion_tokens", 0) if hasattr(res, "usage") and res.usage else 0
        total_tokens = prompt_tokens + completion_tokens

        request.state.input_tokens = prompt_tokens
        request.state.output_tokens = completion_tokens

        return JSONResponse(
            status_code=200,
            content={
                "id": completion_id,
                "object": "chat.completion",
                "created": created_timestamp,
                "model": req.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                },
            },
        )
    except Exception as e:
        logger.error("Completion error in /v1/chat/completions: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"message": str(e), "type": "server_error", "code": "internal_error"}},
        )


@router.post("/embeddings")
async def create_embeddings(
    req: EmbeddingRequest,
    db: AsyncSession = Depends(get_db),
):
    """OpenAI-compatible text embeddings endpoint."""
    input_texts = [req.input] if isinstance(req.input, str) else req.input
    
    model_name = req.model
    if not model_name:
        stmt = select(ModelRegistryModel).where(
            ModelRegistryModel.role == "embedding",
            ModelRegistryModel.is_enabled == True
        ).order_by(ModelRegistryModel.is_default.desc())
        res = await db.execute(stmt)
        default_embed = res.scalars().first()
        model_name = default_embed.model_id if default_embed else "jinaai/jina-embeddings-v3"

    try:
        client = InferenceClient()
        embeddings_data = []
        total_tokens = 0

        for idx, text in enumerate(input_texts):
            vec = await client.embed(text, model_id=model_name)
            embeddings_data.append({
                "object": "embedding",
                "embedding": vec,
                "index": idx,
            })
            total_tokens += len(text.split())

        return {
            "object": "list",
            "data": embeddings_data,
            "model": model_name,
            "usage": {
                "prompt_tokens": total_tokens,
                "total_tokens": total_tokens,
            },
        }
    except Exception as e:
        logger.error("Embeddings error in /v1/embeddings: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"message": str(e), "type": "server_error", "code": "internal_error"}},
        )


@router.get("/models")
async def list_models(
    db: AsyncSession = Depends(get_db),
):
    """OpenAI-compatible list models endpoint.
    
    Returns both registered LLM/embedding models and active agent endpoint_slugs.
    """
    models_list = []

    # 1. Registered models
    reg_stmt = select(ModelRegistryModel).where(ModelRegistryModel.is_enabled == True)
    reg_res = await db.execute(reg_stmt)
    reg_models = reg_res.scalars().all()
    for m in reg_models:
        models_list.append({
            "id": m.model_id,
            "object": "model",
            "created": int(time.time()),
            "owned_by": m.provider or "system",
        })

    # 2. Active agent slugs
    agent_stmt = select(AgentDefinition).where(AgentDefinition.is_active == True)
    agent_res = await db.execute(agent_stmt)
    agents = agent_res.scalars().all()
    for a in agents:
        slug = a.endpoint_slug or f"agent-{a.id[:8]}"
        models_list.append({
            "id": slug,
            "object": "model",
            "created": int(time.time()),
            "owned_by": "contained-agent",
            "permission": [],
        })

    return {
        "object": "list",
        "data": models_list,
    }
