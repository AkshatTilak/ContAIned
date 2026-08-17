"""OpenAI-Compatible External API Gateway endpoints (`/v1/*`) (S6-05d).

Provides standard OpenAI SDK compatible endpoints:
- `POST /v1/chat/completions`: Chat completions for models or hub-qualified agent strings ('{hub_slug}/{agent_slug}')
- `POST /v1/embeddings`: Text embeddings via inference service
- `GET /v1/models`: List available registry models and authorized qualified agent model strings
"""

import json
import logging
import time
import uuid
from typing import List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.clients.inference import InferenceClient
from common.clients.litellm import completion_with_fallback
from common.constants.roles import PLATFORM_ROLE_ADMIN
from common.models.database import AgentDefinition, Hub, HubMember, ModelRegistryModel, User
from common.schemas.agent_types import CollectionBinding
from gateway.api.external_resolution import resolve_qualified_agent
from gateway.api.agent_invoke import log_invocation_background
from gateway.auth.dependencies import get_db
from projects.guardroute.src.agents.collection_binding import resolve_bindings

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
    
    Supports model names (e.g. 'gemini/gemini-3.5-flash') and hub-qualified agent model strings ('{hub_slug}/{agent_slug}').
    Supports streaming (`stream: true`) in standard SSE format.
    """
    created_timestamp = int(time.time())
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    api_key_hub_id = getattr(request.state, "api_key_hub_id", None)
    api_key_user_id = getattr(request.state, "api_key_user_id", None) or getattr(request.state, "user_id", None)

    agent = None
    is_standard_provider = any(req.model.startswith(p) for p in ("openai/", "gemini/", "ollama/", "huggingface/", "vllm/", "anthropic/"))
    if "/" in req.model and not is_standard_provider:
        try:
            agent = await resolve_qualified_agent(
                db,
                model=req.model,
                api_key_hub_id=api_key_hub_id,
                api_key_user_id=api_key_user_id,
            )
        except HTTPException as e:
            if e.status_code == 404:
                return JSONResponse(
                    status_code=404,
                    content={
                        "error": {
                            "message": f"The model '{req.model}' does not exist.",
                            "type": "invalid_request_error",
                            "param": "model",
                            "code": "model_not_found",
                        }
                    },
                )
            elif e.status_code == 403:
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": {
                            "message": e.detail,
                            "type": "invalid_request_error",
                            "param": "model",
                            "code": getattr(e, "headers", {}).get("X-Error-Code", "unauthorized"),
                        }
                    },
                )
            raise e

        if agent is None and "/" in req.model:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "message": f"The model '{req.model}' does not exist.",
                        "type": "invalid_request_error",
                        "param": "model",
                        "code": "model_not_found",
                    }
                },
            )

    if agent:
        # Pre-validate agent collection bindings & hub links
        raw_bindings = [CollectionBinding(**b) for b in (agent.collection_bindings_json or [])]
        try:
            await resolve_bindings(db, source_hub_id=agent.hub_id, bindings=raw_bindings)
        except HTTPException as bind_err:
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "message": bind_err.detail,
                        "type": "invalid_request_error",
                        "param": "model",
                        "code": "hub_link_revoked",
                    }
                },
            )

        system_prompt = agent.system_prompt
        model_to_use = agent.model_id
        formatted_messages = [{"role": "system", "content": system_prompt}] + [
            {"role": m.role, "content": m.content} for m in req.messages
        ]
        temp = req.temperature if req.temperature is not None else (agent.temperature or 0.7)
        max_toks = req.max_tokens if req.max_tokens is not None else (agent.max_tokens or 2048)
    else:
        # Verify model exists in registry or carries valid provider prefix
        reg_stmt = select(ModelRegistryModel).where(
            ModelRegistryModel.model_id == req.model,
            ModelRegistryModel.is_enabled == True,
        )
        reg_model = (await db.execute(reg_stmt)).scalar_one_or_none()
        if not reg_model and not any(req.model.startswith(p) for p in ("openai/", "gemini/", "ollama/", "huggingface/", "vllm/", "anthropic/")):
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "message": f"The model '{req.model}' does not exist.",
                        "type": "invalid_request_error",
                        "param": "model",
                        "code": "model_not_found",
                    }
                },
            )
        model_to_use = req.model
        formatted_messages = [{"role": m.role, "content": m.content} for m in req.messages]
        temp = req.temperature or 0.7
        max_toks = req.max_tokens or 2048

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

                role_header = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created_timestamp,
                    "model": req.model,
                    "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
                }
                yield f"data: {json.dumps(role_header)}\n\n"

                if hasattr(res, "__aiter__"):
                    async for chunk in res:
                        content_chunk = getattr(chunk.choices[0].delta, "content", None) or ""
                        if content_chunk:
                            chunk_payload = {
                                "id": completion_id,
                                "object": "chat.completion.chunk",
                                "created": created_timestamp,
                                "model": req.model,
                                "choices": [{"index": 0, "delta": {"content": content_chunk}, "finish_reason": None}],
                            }
                            yield f"data: {json.dumps(chunk_payload)}\n\n"
                else:
                    for chunk in res:
                        content_chunk = getattr(chunk.choices[0].delta, "content", None) or ""
                        if content_chunk:
                            chunk_payload = {
                                "id": completion_id,
                                "object": "chat.completion.chunk",
                                "created": created_timestamp,
                                "model": req.model,
                                "choices": [{"index": 0, "delta": {"content": content_chunk}, "finish_reason": None}],
                            }
                            yield f"data: {json.dumps(chunk_payload)}\n\n"

                stop_chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created_timestamp,
                    "model": req.model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                yield f"data: {json.dumps(stop_chunk)}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error("Error during streaming completion: %s", e)
                err_body = {"error": {"message": str(e), "type": "server_error"}}
                yield f"data: {json.dumps(err_body)}\n\n"

        return StreamingResponse(stream_generator(), media_type="text/event-stream")

    # Non-streaming execution
    try:
        res = await completion_with_fallback(
            model=model_to_use,
            messages=formatted_messages,
            temperature=temp,
            max_tokens=max_toks,
            stream=False,
        )

        response_content = res.choices[0].message.content or ""
        in_tokens = getattr(res.usage, "prompt_tokens", 0)
        out_tokens = getattr(res.usage, "completion_tokens", 0)

        request.state.input_tokens = in_tokens
        request.state.output_tokens = out_tokens

        if agent:
            asyncio.create_task(
                log_invocation_background(
                    hub_id=agent.hub_id,
                    agent_id=agent.id,
                    user_id=api_key_user_id,
                    prompt=req.messages[-1].content if req.messages else "",
                    response=response_content,
                    model_used=model_to_use,
                    input_tokens=in_tokens,
                    output_tokens=out_tokens,
                    latency_ms=0.0,
                    status_str="success",
                    route_decision="external_v1",
                )
            )

        return {
            "id": completion_id,
            "object": "chat.completion",
            "created": created_timestamp,
            "model": req.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_content,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": in_tokens,
                "completion_tokens": out_tokens,
                "total_tokens": in_tokens + out_tokens,
            },
        }

    except Exception as e:
        logger.error("Chat completion error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference processing failed: {str(e)}",
        )


@router.post("/embeddings")
async def create_embeddings(
    req: EmbeddingRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Generate text embeddings for inputs."""
    inference = getattr(request.app.state, "syntraflow_inference", None)
    if not inference:
        inference = InferenceClient()

    texts = [req.input] if isinstance(req.input, str) else req.input
    try:
        embeddings = inference.embed_passages(texts)
        data = [
            {
                "object": "embedding",
                "embedding": emb,
                "index": idx,
            }
            for idx, emb in enumerate(embeddings)
        ]
        return {
            "object": "list",
            "data": data,
            "model": req.model or "default-embedding",
            "usage": {
                "prompt_tokens": sum(len(t.split()) for t in texts),
                "total_tokens": sum(len(t.split()) for t in texts),
            },
        }
    except Exception as e:
        logger.error("Embedding generation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Embedding generation failed: {str(e)}",
        )


@router.get("/models")
async def list_models(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """List available registry models and authorized qualified agent model strings ('{hub_slug}/{agent_slug}')."""
    now = int(time.time())
    data = []

    # 1. Add Model Registry entries
    reg_stmt = select(ModelRegistryModel).where(ModelRegistryModel.is_enabled == True)
    reg_models = (await db.execute(reg_stmt)).scalars().all()
    for m in reg_models:
        data.append(
            {
                "id": m.model_id,
                "object": "model",
                "created": now,
                "owned_by": m.provider,
                "role": m.role,
            }
        )

    # 2. Add Hub-Qualified Agent entries
    api_key_hub_id = getattr(request.state, "api_key_hub_id", None)
    api_key_user_id = getattr(request.state, "api_key_user_id", None) or getattr(request.state, "user_id", None)

    if api_key_hub_id:
        hub_stmt = select(Hub).where(Hub.id == api_key_hub_id, Hub.hub_type == "agent", Hub.is_archived == False)
        hubs = (await db.execute(hub_stmt)).scalars().all()
    else:
        if api_key_user_id:
            user = await db.get(User, api_key_user_id)
            if user and user.platform_role == PLATFORM_ROLE_ADMIN:
                hub_stmt = select(Hub).where(Hub.hub_type == "agent", Hub.is_archived == False)
                hubs = (await db.execute(hub_stmt)).scalars().all()
            else:
                mem_stmt = select(Hub).join(HubMember, HubMember.hub_id == Hub.id).where(
                    HubMember.user_id == api_key_user_id,
                    Hub.hub_type == "agent",
                    Hub.is_archived == False,
                )
                hubs = (await db.execute(mem_stmt)).scalars().all()
        else:
            hubs = []

    for h in hubs:
        agent_stmt = select(AgentDefinition).where(AgentDefinition.hub_id == h.id, AgentDefinition.is_active == True)
        agents = (await db.execute(agent_stmt)).scalars().all()
        for a in agents:
            if a.endpoint_slug:
                model_id = f"{h.slug}/{a.endpoint_slug}"
                data.append(
                    {
                        "id": model_id,
                        "object": "model",
                        "created": int(a.created_at.timestamp()) if a.created_at else now,
                        "owned_by": "contained-agent",
                    }
                )

    return {"object": "list", "data": data}
