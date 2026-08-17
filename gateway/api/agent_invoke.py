"""Agent Invocation, Smart Routing, and Invocation Logging REST API endpoints (S6-05c).

All routes are nested under /hubs/{hub_id}/agents and guarded by require_hub(hub_type="agent").
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.clients.litellm import completion_with_fallback
from common.clients.postgres import get_async_db, get_sessionmaker
from common.models.database import AgentDefinition, AgentInvocationLog
from common.schemas.agent_types import CollectionBinding
from gateway.auth.hub_context import HubContext, require_hub
from projects.guardroute.src.agents.agent_repository import get_agent as repo_get_agent
from projects.guardroute.src.agents.collection_binding import resolve_bindings

router = APIRouter(prefix="/hubs/{hub_id}/agents", tags=["agent-invocation"])
logger = logging.getLogger("gateway.api.agent_invoke")

# Per-hub round-robin counter for smart routing
_rr_counters: Dict[str, int] = {}


# --- Pydantic Schemas ---

class AgentInvokeRequest(BaseModel):
    prompt: str = Field(..., description="User prompt text")
    session_id: Optional[str] = Field(None, description="Optional session/conversation ID")
    conversation_history: Optional[List[Dict[str, str]]] = Field(
        default=None, description="Optional prior message history"
    )
    temperature: Optional[float] = Field(None, description="Temperature override")
    max_tokens: Optional[int] = Field(None, description="Max tokens override")
    stream: Optional[bool] = Field(False, description="Enable SSE streaming response")


class AgentInvokeResponse(BaseModel):
    agent_id: str
    response: str
    model_used: str
    input_tokens: Optional[int] = 0
    output_tokens: Optional[int] = 0
    latency_ms: float
    status: str = "success"


class AgentBatchInvokeRequest(BaseModel):
    prompts: List[str] = Field(..., max_length=20, description="List of prompts (max 20)")


class RouteRequest(BaseModel):
    prompt: str = Field(..., description="User prompt text")
    agent_id: Optional[str] = Field(None, description="Direct target agent ID")
    model_id: Optional[str] = Field(None, description="Direct target model string")
    routing_strategy: Optional[str] = Field("auto", description="auto | direct | round_robin")
    session_id: Optional[str] = Field(None, description="Optional session ID")
    stream: Optional[bool] = Field(False, description="Enable SSE streaming response")


class RouteResponse(BaseModel):
    response: str
    route_decision: str
    agent_used: Optional[str] = None
    model_used: str
    latency_ms: float
    input_tokens: Optional[int] = 0
    output_tokens: Optional[int] = 0


class AgentStatsResponse(BaseModel):
    agent_id: str
    hub_id: str
    total_invocations: int
    avg_latency_ms: float
    total_input_tokens: int
    total_output_tokens: int
    status_counts: Dict[str, int]
    last_used: Optional[datetime] = None


# --- Helper for Fire-and-Forget Logging ---

async def log_invocation_background(
    hub_id: str,
    agent_id: str,
    user_id: Optional[str],
    prompt: str,
    response: Optional[str],
    model_used: Optional[str],
    input_tokens: Optional[int],
    output_tokens: Optional[int],
    latency_ms: float,
    status_str: str = "success",
    route_decision: Optional[str] = "direct",
    metadata_json: Optional[Dict[str, Any]] = None,
):
    """Background task to insert AgentInvocationLog record with hub_id."""
    try:
        SessionLocal = get_sessionmaker()
        async with SessionLocal() as session:
            log_entry = AgentInvocationLog(
                id=str(uuid.uuid4()),
                hub_id=hub_id,
                agent_id=agent_id,
                user_id=user_id,
                prompt=prompt,
                response=response,
                model_used=model_used,
                input_tokens=input_tokens or 0,
                output_tokens=output_tokens or 0,
                latency_ms=latency_ms,
                status=status_str,
                route_decision=route_decision,
                metadata_json=metadata_json,
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            session.add(log_entry)
            await session.commit()
    except Exception as e:
        logger.error("Failed to write background invocation log: %s", e)


# --- Endpoint Implementations ---

@router.post("/{agent_id}/invoke")
async def invoke_agent(
    agent_id: str,
    req: AgentInvokeRequest,
    ctx: HubContext = Depends(require_hub(hub_type="agent", min_role="contributor")),
    db: AsyncSession = Depends(get_async_db),
):
    """Invoke an agent in a hub."""
    agent = await repo_get_agent(db, hub_id=ctx.hub_id, agent_id=agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found in this hub.",
        )

    if not agent.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Agent '{agent.name}' is inactive.",
            headers={"X-Error-Code": "AGENT_INACTIVE"},
        )

    # Resolve & validate collection bindings via Hub Links BEFORE streaming or executing
    raw_bindings = [CollectionBinding(**b) for b in (agent.collection_bindings_json or [])]
    resolved_bindings = await resolve_bindings(db, source_hub_id=ctx.hub_id, bindings=raw_bindings)

    messages = []
    if agent.system_prompt:
        messages.append({"role": "system", "content": agent.system_prompt})
    if req.conversation_history:
        messages.extend(req.conversation_history)
    messages.append({"role": "user", "content": req.prompt})

    temperature = req.temperature if req.temperature is not None else agent.temperature
    max_tokens = req.max_tokens if req.max_tokens is not None else agent.max_tokens

    if req.stream:
        async def event_generator():
            start_t = time.time()
            full_response_text = ""
            try:
                raw_response = await completion_with_fallback(
                    model=agent.model_id,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                )
                if hasattr(raw_response, "__aiter__"):
                    async for chunk in raw_response:
                        content_chunk = getattr(chunk.choices[0].delta, "content", None) or ""
                        if content_chunk:
                            full_response_text += content_chunk
                            chunk_payload = {
                                "agent_id": agent.id,
                                "delta": content_chunk,
                                "status": "in_progress",
                            }
                            yield f"data: {json.dumps(chunk_payload)}\n\n"
                else:
                    for chunk in raw_response:
                        content_chunk = getattr(chunk.choices[0].delta, "content", None) or ""
                        if content_chunk:
                            full_response_text += content_chunk
                            chunk_payload = {
                                "agent_id": agent.id,
                                "delta": content_chunk,
                                "status": "in_progress",
                            }
                            yield f"data: {json.dumps(chunk_payload)}\n\n"

                lat_ms = round((time.time() - start_t) * 1000, 2)
                end_payload = {
                    "agent_id": agent.id,
                    "delta": "",
                    "status": "completed",
                    "latency_ms": lat_ms,
                }
                yield f"data: {json.dumps(end_payload)}\n\n"
                yield "data: [DONE]\n\n"

                asyncio.create_task(
                    log_invocation_background(
                        hub_id=ctx.hub_id,
                        agent_id=agent.id,
                        user_id=ctx.user_id,
                        prompt=req.prompt,
                        response=full_response_text,
                        model_used=agent.model_id,
                        input_tokens=0,
                        output_tokens=0,
                        latency_ms=lat_ms,
                        status_str="success",
                        route_decision="direct",
                    )
                )
            except Exception as e:
                logger.error("Streaming invocation failed: %s", e)
                err_payload = {"error": str(e), "status": "failed"}
                yield f"data: {json.dumps(err_payload)}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    # Non-streaming call
    start_t = time.time()
    try:
        response = await completion_with_fallback(
            model=agent.model_id,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        latency_ms = round((time.time() - start_t) * 1000, 2)
        response_text = response.choices[0].message.content or ""
        in_tokens = getattr(response.usage, "prompt_tokens", 0)
        out_tokens = getattr(response.usage, "completion_tokens", 0)

        asyncio.create_task(
            log_invocation_background(
                hub_id=ctx.hub_id,
                agent_id=agent.id,
                user_id=ctx.user_id,
                prompt=req.prompt,
                response=response_text,
                model_used=agent.model_id,
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                latency_ms=latency_ms,
                status_str="success",
                route_decision="direct",
            )
        )

        return AgentInvokeResponse(
            agent_id=agent.id,
            response=response_text,
            model_used=agent.model_id,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            latency_ms=latency_ms,
            status="success",
        )
    except Exception as e:
        latency_ms = round((time.time() - start_t) * 1000, 2)
        asyncio.create_task(
            log_invocation_background(
                hub_id=ctx.hub_id,
                agent_id=agent.id,
                user_id=ctx.user_id,
                prompt=req.prompt,
                response=None,
                model_used=agent.model_id,
                input_tokens=0,
                output_tokens=0,
                latency_ms=latency_ms,
                status_str="failed",
                route_decision="direct",
            )
        )
        raise HTTPException(status_code=500, detail=f"Agent invocation failed: {str(e)}")


@router.post("/{agent_id}/batch-invoke")
async def batch_invoke_agent(
    agent_id: str,
    req: AgentBatchInvokeRequest,
    ctx: HubContext = Depends(require_hub(hub_type="agent", min_role="contributor")),
    db: AsyncSession = Depends(get_async_db),
):
    """Run batch invocation over a list of prompts."""
    agent = await repo_get_agent(db, hub_id=ctx.hub_id, agent_id=agent_id)
    if not agent or not agent.is_active:
        raise HTTPException(status_code=404, detail="Agent not found or inactive.")

    results = []
    for prompt in req.prompts:
        start_t = time.time()
        try:
            resp = completion_with_fallback(
                model=agent.model_id,
                messages=[{"role": "system", "content": agent.system_prompt}, {"role": "user", "content": prompt}],
                temperature=agent.temperature,
                max_tokens=agent.max_tokens,
            )
            lat = round((time.time() - start_t) * 1000, 2)
            results.append({"prompt": prompt, "response": resp.choices[0].message.content, "status": "success", "latency_ms": lat})
        except Exception as e:
            results.append({"prompt": prompt, "error": str(e), "status": "failed"})

    return {"agent_id": agent.id, "total": len(req.prompts), "results": results}


@router.post("/route", response_model=RouteResponse)
async def route_prompt(
    req: RouteRequest,
    ctx: HubContext = Depends(require_hub(hub_type="agent", min_role="contributor")),
    db: AsyncSession = Depends(get_async_db),
):
    """Route user prompt to candidate agents in the hub."""
    strategy = req.routing_strategy or "auto"
    target_agent = None

    if req.agent_id:
        target_agent = await repo_get_agent(db, hub_id=ctx.hub_id, agent_id=req.agent_id)

    if not target_agent:
        active_agents = select(AgentDefinition).where(
            AgentDefinition.hub_id == ctx.hub_id, AgentDefinition.is_active == True
        )
        candidates = (await db.execute(active_agents)).scalars().all()
        if not candidates:
            raise HTTPException(status_code=404, detail="No active agents available in hub.")

        if strategy == "round_robin":
            idx = _rr_counters.get(ctx.hub_id, 0) % len(candidates)
            _rr_counters[ctx.hub_id] = idx + 1
            target_agent = candidates[idx]
        else:
            target_agent = candidates[0]

    start_t = time.time()
    resp = completion_with_fallback(
        model=target_agent.model_id,
        messages=[{"role": "system", "content": target_agent.system_prompt}, {"role": "user", "content": req.prompt}],
        temperature=target_agent.temperature,
        max_tokens=target_agent.max_tokens,
    )
    lat_ms = round((time.time() - start_t) * 1000, 2)

    return RouteResponse(
        response=resp.choices[0].message.content or "",
        route_decision=f"{strategy}_selected_{target_agent.endpoint_slug}",
        agent_used=target_agent.id,
        model_used=target_agent.model_id,
        latency_ms=lat_ms,
        input_tokens=getattr(resp.usage, "prompt_tokens", 0),
        output_tokens=getattr(resp.usage, "completion_tokens", 0),
    )


@router.get("/{agent_id}/stats", response_model=AgentStatsResponse)
async def get_agent_stats(
    agent_id: str,
    ctx: HubContext = Depends(require_hub(hub_type="agent", min_role="viewer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Retrieve telemetry stats for an agent in a hub."""
    agent = await repo_get_agent(db, hub_id=ctx.hub_id, agent_id=agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")

    stmt = select(AgentInvocationLog).where(
        AgentInvocationLog.agent_id == agent_id, AgentInvocationLog.hub_id == ctx.hub_id
    )
    logs = (await db.execute(stmt)).scalars().all()

    total = len(logs)
    avg_lat = sum(l.latency_ms or 0.0 for l in logs) / total if total > 0 else 0.0
    in_tok = sum(l.input_tokens or 0 for l in logs)
    out_tok = sum(l.output_tokens or 0 for l in logs)

    counts = {}
    for l in logs:
        st = l.status or "unknown"
        counts[st] = counts.get(st, 0) + 1

    last_used = max((l.created_at for l in logs if l.created_at), default=None)

    return AgentStatsResponse(
        agent_id=agent.id,
        hub_id=ctx.hub_id,
        total_invocations=total,
        avg_latency_ms=round(avg_lat, 2),
        total_input_tokens=in_tok,
        total_output_tokens=out_tok,
        status_counts=counts,
        last_used=last_used,
    )


@router.get("/{agent_id}/logs")
async def get_agent_logs(
    agent_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    ctx: HubContext = Depends(require_hub(hub_type="agent", min_role="viewer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Retrieve invocation log history for an agent in a hub."""
    agent = await repo_get_agent(db, hub_id=ctx.hub_id, agent_id=agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")

    stmt = (
        select(AgentInvocationLog)
        .where(AgentInvocationLog.agent_id == agent_id, AgentInvocationLog.hub_id == ctx.hub_id)
        .order_by(AgentInvocationLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    logs = (await db.execute(stmt)).scalars().all()

    return {
        "agent_id": agent.id,
        "hub_id": ctx.hub_id,
        "items": [
            {
                "id": l.id,
                "prompt": l.prompt,
                "response": l.response,
                "model_used": l.model_used,
                "latency_ms": l.latency_ms,
                "status": l.status,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in logs
        ],
    }
