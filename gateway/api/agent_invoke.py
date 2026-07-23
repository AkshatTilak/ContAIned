"""Agent Invocation, Smart Routing, and Invocation Logging REST API endpoints."""

import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from common.clients.litellm import completion_with_fallback
from common.clients.postgres import get_async_db
from common.models.database import AgentDefinition, AgentInvocationLog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from gateway.auth.dependencies import get_optional_user
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["agent-invocation"])
logger = logging.getLogger("gateway.api.agent_invoke")

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
    total_invocations: int
    avg_latency_ms: float
    total_input_tokens: int
    total_output_tokens: int
    status_counts: Dict[str, int]
    last_used: Optional[datetime] = None


# --- Helper for Fire-and-Forget Logging ---


async def log_invocation_background(
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
):
    """Background task to insert AgentInvocationLog record silently."""
    try:
        from common.clients.postgres import get_sessionmaker

        SessionLocal = get_sessionmaker()
        async with SessionLocal() as session:
            log_entry = AgentInvocationLog(
                id=str(uuid.uuid4()),
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
                created_at=datetime.utcnow(),
            )
            session.add(log_entry)
            await session.commit()
    except Exception as e:
        logger.warning(f"Failed to log agent invocation in background: {e}")


# --- Round Robin Counter ---
_rr_counter = 0


# --- Endpoints ---


@router.post("/agents/{agent_id}/invoke", response_model=AgentInvokeResponse)
async def invoke_agent(
    agent_id: str,
    payload: AgentInvokeRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
):
    """Invoke a specified agent by ID."""
    start_time = time.time()

    stmt = select(AgentDefinition).where(
        (AgentDefinition.id == agent_id) | (AgentDefinition.endpoint_slug == agent_id)
    )
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID or slug '{agent_id}' not found.",
        )

    if agent.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Agent '{agent.name}' is currently inactive and cannot be invoked.",
        )

    # Prepare message chain
    messages = [{"role": "system", "content": agent.system_prompt}]
    if payload.conversation_history:
        messages.extend(payload.conversation_history)
    messages.append({"role": "user", "content": payload.prompt})

    temp = payload.temperature if payload.temperature is not None else (agent.temperature or 0.7)
    max_tok = payload.max_tokens if payload.max_tokens is not None else (agent.max_tokens or 1000)
    user_id = current_user.get("sub") if current_user else None

    try:
        completion_res = await completion_with_fallback(
            model=agent.model_id,
            messages=messages,
            temperature=temp,
            max_tokens=max_tok,
        )
        latency_ms = (time.time() - start_time) * 1000.0

        content = completion_res.get("choices", [{}])[0].get("message", {}).get("content", "")
        model_used = completion_res.get("model", agent.model_id)
        usage = completion_res.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        # Trigger background logging
        asyncio.create_task(
            log_invocation_background(
                agent_id=agent_id,
                user_id=user_id,
                prompt=payload.prompt,
                response=content,
                model_used=model_used,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                status_str="success",
                route_decision="direct",
            )
        )

        return AgentInvokeResponse(
            agent_id=agent_id,
            response=content,
            model_used=model_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=round(latency_ms, 2),
            status="success",
        )

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.error(f"Error invoking agent {agent_id}: {e}")

        asyncio.create_task(
            log_invocation_background(
                agent_id=agent_id,
                user_id=user_id,
                prompt=payload.prompt,
                response=str(e),
                model_used=agent.model_id,
                input_tokens=0,
                output_tokens=0,
                latency_ms=latency_ms,
                status_str="error",
                route_decision="direct",
            )
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent invocation failed: {str(e)}",
        )


@router.post("/agents/{agent_id}/invoke/batch")
async def invoke_agent_batch(
    agent_id: str,
    payload: AgentBatchInvokeRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
):
    """Invoke an agent sequentially across a batch of prompts (max 20)."""
    results = []
    for prompt_text in payload.prompts:
        single_req = AgentInvokeRequest(prompt=prompt_text)
        res = await invoke_agent(
            agent_id=agent_id,
            payload=single_req,
            db=db,
            current_user=current_user,
        )
        results.append(res)
    return {"agent_id": agent_id, "total": len(results), "results": results}


@router.post("/route", response_model=RouteResponse)
async def route_request(
    payload: RouteRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
):
    """Unified smart routing endpoint (direct agent, direct model, auto classifier, round-robin)."""
    start_time = time.time()
    user_id = current_user.get("sub") if current_user else None
    strategy = payload.routing_strategy or "auto"

    target_agent_id: Optional[str] = payload.agent_id

    # 1. Direct Agent
    if target_agent_id:
        inv_res = await invoke_agent(
            agent_id=target_agent_id,
            payload=AgentInvokeRequest(prompt=payload.prompt, session_id=payload.session_id),
            db=db,
            current_user=current_user,
        )
        return RouteResponse(
            response=inv_res.response,
            route_decision="direct_agent",
            agent_used=target_agent_id,
            model_used=inv_res.model_used,
            latency_ms=inv_res.latency_ms,
            input_tokens=inv_res.input_tokens,
            output_tokens=inv_res.output_tokens,
        )

    # 2. Direct Model
    if payload.model_id:
        completion_res = await completion_with_fallback(
            model=payload.model_id,
            messages=[{"role": "user", "content": payload.prompt}],
        )
        latency_ms = (time.time() - start_time) * 1000.0
        content = completion_res.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = completion_res.get("usage", {})

        return RouteResponse(
            response=content,
            route_decision="direct_model",
            agent_used=None,
            model_used=payload.model_id,
            latency_ms=round(latency_ms, 2),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )

    # 3. Round Robin across active agents
    if strategy == "round_robin":
        stmt = select(AgentDefinition).where(AgentDefinition.is_active == True).order_by(AgentDefinition.created_at.asc())
        res = await db.execute(stmt)
        agents = res.scalars().all()

        if agents:
            global _rr_counter
            selected_agent = agents[_rr_counter % len(agents)]
            _rr_counter += 1

            inv_res = await invoke_agent(
                agent_id=selected_agent.id,
                payload=AgentInvokeRequest(prompt=payload.prompt),
                db=db,
                current_user=current_user,
            )
            return RouteResponse(
                response=inv_res.response,
                route_decision="round_robin",
                agent_used=selected_agent.id,
                model_used=inv_res.model_used,
                latency_ms=inv_res.latency_ms,
                input_tokens=inv_res.input_tokens,
                output_tokens=inv_res.output_tokens,
            )

    # 4. Auto classification fallback -> Default Completion Model
    default_model = "gemini/gemini-3.5-flash"

    stmt = select(AgentDefinition).where(AgentDefinition.is_active == True)
    res = await db.execute(stmt)
    agents = res.scalars().all()

    matched_agent = None
    prompt_lower = payload.prompt.lower()
    for a in agents:
        if a.name.lower() in prompt_lower or a.role.lower() in prompt_lower:
            matched_agent = a
            break

    if matched_agent:
        inv_res = await invoke_agent(
            agent_id=matched_agent.id,
            payload=AgentInvokeRequest(prompt=payload.prompt),
            db=db,
            current_user=current_user,
        )
        return RouteResponse(
            response=inv_res.response,
            route_decision="auto_agent_match",
            agent_used=matched_agent.id,
            model_used=inv_res.model_used,
            latency_ms=inv_res.latency_ms,
            input_tokens=inv_res.input_tokens,
            output_tokens=inv_res.output_tokens,
        )

    # Fallback to direct completion
    completion_res = await completion_with_fallback(
        model=default_model,
        messages=[{"role": "user", "content": payload.prompt}],
    )
    latency_ms = (time.time() - start_time) * 1000.0
    content = completion_res.get("choices", [{}])[0].get("message", {}).get("content", "")
    usage = completion_res.get("usage", {})

    return RouteResponse(
        response=content,
        route_decision="auto_fallback",
        agent_used=None,
        model_used=default_model,
        latency_ms=round(latency_ms, 2),
        input_tokens=usage.get("prompt_tokens", 0),
        output_tokens=usage.get("completion_tokens", 0),
    )


@router.get("/agents/{agent_id}/stats", response_model=AgentStatsResponse)
async def get_agent_stats(
    agent_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Retrieve analytics stats for a specific agent by ID."""
    stmt = select(AgentInvocationLog).where(AgentInvocationLog.agent_id == agent_id)
    res = await db.execute(stmt)
    logs = res.scalars().all()

    total = len(logs)
    if total == 0:
        return AgentStatsResponse(
            agent_id=agent_id,
            total_invocations=0,
            avg_latency_ms=0.0,
            total_input_tokens=0,
            total_output_tokens=0,
            status_counts={"success": 0, "error": 0},
            last_used=None,
        )

    total_latency = sum(l.latency_ms or 0.0 for l in logs)
    total_in_tokens = sum(l.input_tokens or 0 for l in logs)
    total_out_tokens = sum(l.output_tokens or 0 for l in logs)

    status_counts: Dict[str, int] = {}
    for l in logs:
        st = l.status or "success"
        status_counts[st] = status_counts.get(st, 0) + 1

    last_used = max((l.created_at for l in logs if l.created_at), default=None)

    return AgentStatsResponse(
        agent_id=agent_id,
        total_invocations=total,
        avg_latency_ms=round(total_latency / total, 2),
        total_input_tokens=total_in_tokens,
        total_output_tokens=total_out_tokens,
        status_counts=status_counts,
        last_used=last_used,
    )
