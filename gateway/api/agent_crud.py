"""Agent CRUD REST API Endpoints for Ingestion/Agent Hub (S6-05c).

All routes are nested under /hubs/{hub_id}/agents and guarded by require_hub(hub_type="agent").
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.clients.postgres import get_async_db
from common.clients.redis import publish_event
from common.models.database import AgentDefinition, AuditLog, ModelRegistryModel
from common.schemas.agent_types import AgentCreate, AgentResponse, AgentUpdate
from gateway.auth.hub_context import HubContext, require_hub
from projects.guardroute.src.agents.agent_repository import (
    create_agent as repo_create_agent,
    delete_agent as repo_delete_agent,
    generate_unique_slug,
    get_agent as repo_get_agent,
    list_agents as repo_list_agents,
    update_agent as repo_update_agent,
    slugify,
)
from projects.guardroute.src.agents.collection_binding import (
    inspect_binding_statuses,
    validate_bindings,
)

router = APIRouter(prefix="/hubs/{hub_id}/agents", tags=["agent-hub"])
logger = logging.getLogger("gateway.api.agent_crud")


async def _log_audit_event(
    session: AsyncSession,
    *,
    hub_id: Optional[str],
    actor_user_id: Optional[str],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    summary: Optional[str] = None,
    before_json: Optional[Dict[str, Any]] = None,
    after_json: Optional[Dict[str, Any]] = None,
) -> None:
    audit = AuditLog(
        id=str(uuid.uuid4()),
        hub_id=hub_id,
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        summary=summary,
        before_json=before_json,
        after_json=after_json,
        created_at=datetime.now(timezone.utc),
    )
    session.add(audit)


async def _to_agent_response(session: AsyncSession, agent: AgentDefinition, hub_slug: str) -> AgentResponse:
    bindings_resp = await inspect_binding_statuses(
        session,
        source_hub_id=agent.hub_id,
        bindings_raw=agent.collection_bindings_json or [],
    )
    return AgentResponse(
        id=agent.id,
        hub_id=agent.hub_id,
        hub_slug=hub_slug,
        name=agent.name,
        role=agent.role,
        system_prompt=agent.system_prompt,
        model_id=agent.model_id,
        tools=agent.tools or [],
        collection_bindings=bindings_resp,
        temperature=agent.temperature,
        max_tokens=agent.max_tokens,
        is_active=agent.is_active,
        endpoint_slug=agent.endpoint_slug,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


@router.get("", response_model=List[AgentResponse])
async def list_agents(
    is_active: Optional[bool] = Query(None),
    q: Optional[str] = Query(None),
    ctx: HubContext = Depends(require_hub(hub_type="agent", min_role="viewer")),
    db: AsyncSession = Depends(get_async_db),
) -> List[AgentResponse]:
    """Retrieve agent definitions for a hub."""
    agents = await repo_list_agents(db, hub_id=ctx.hub_id, is_active=is_active, q=q)
    return [await _to_agent_response(db, a, ctx.hub.slug) for a in agents]


@router.get("/available-models")
async def list_agent_models(
    ctx: HubContext = Depends(require_hub(hub_type="agent", min_role="viewer")),
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """Retrieve available models from Model Registry for Agent dropdowns."""
    stmt = select(ModelRegistryModel).where(
        ModelRegistryModel.role.in_(["completion", "classifier"]),
        ModelRegistryModel.is_enabled == True,
    )
    models = (await db.execute(stmt)).scalars().all()
    return {
        "models": [
            {
                "model_id": m.model_id,
                "display_name": m.display_name,
                "provider": m.provider,
                "role": m.role,
                "is_default": m.is_default,
            }
            for m in models
        ]
    }


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    payload: AgentCreate,
    ctx: HubContext = Depends(require_hub(hub_type="agent", min_role="contributor")),
    db: AsyncSession = Depends(get_async_db),
) -> AgentResponse:
    """Create a new agent definition in a hub."""
    # Pre-validate collection bindings via Hub Links
    if payload.collection_bindings:
        await validate_bindings(db, source_hub_id=ctx.hub_id, bindings=payload.collection_bindings)

    try:
        agent = await repo_create_agent(db, hub_id=ctx.hub_id, payload=payload)
        await _log_audit_event(
            db,
            hub_id=ctx.hub_id,
            actor_user_id=ctx.user_id,
            action="create",
            resource_type="agent",
            resource_id=agent.id,
            summary=f"Created agent '{agent.name}'",
            after_json={"id": agent.id, "name": agent.name, "endpoint_slug": agent.endpoint_slug},
        )
        await db.commit()
        await db.refresh(agent)

        await publish_event("agent-config-updates", {"action": "created", "hub_id": ctx.hub_id, "agent_id": agent.id})
        return await _to_agent_response(db, agent, ctx.hub.slug)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    ctx: HubContext = Depends(require_hub(hub_type="agent", min_role="viewer")),
    db: AsyncSession = Depends(get_async_db),
) -> AgentResponse:
    """Retrieve details for a specific agent by ID."""
    agent = await repo_get_agent(db, hub_id=ctx.hub_id, agent_id=agent_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")
    return await _to_agent_response(db, agent, ctx.hub.slug)


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    payload: AgentUpdate,
    ctx: HubContext = Depends(require_hub(hub_type="agent", min_role="contributor")),
    db: AsyncSession = Depends(get_async_db),
) -> AgentResponse:
    """Update an existing agent definition in a hub."""
    if payload.collection_bindings is not None:
        await validate_bindings(db, source_hub_id=ctx.hub_id, bindings=payload.collection_bindings)

    try:
        agent = await repo_update_agent(db, hub_id=ctx.hub_id, agent_id=agent_id, payload=payload)
        await _log_audit_event(
            db,
            hub_id=ctx.hub_id,
            actor_user_id=ctx.user_id,
            action="update",
            resource_type="agent",
            resource_id=agent.id,
            summary=f"Updated agent '{agent.id}'",
        )
        await db.commit()
        await db.refresh(agent)

        await publish_event("agent-config-updates", {"action": "updated", "hub_id": ctx.hub_id, "agent_id": agent.id})
        return await _to_agent_response(db, agent, ctx.hub.slug)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)


@router.patch("/{agent_id}/toggle", response_model=AgentResponse)
async def toggle_agent_status(
    agent_id: str,
    ctx: HubContext = Depends(require_hub(hub_type="agent", min_role="contributor")),
    db: AsyncSession = Depends(get_async_db),
) -> AgentResponse:
    """Toggle activation status of an agent."""
    agent = await repo_get_agent(db, hub_id=ctx.hub_id, agent_id=agent_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")

    agent.is_active = not agent.is_active
    await _log_audit_event(
        db,
        hub_id=ctx.hub_id,
        actor_user_id=ctx.user_id,
        action="update",
        resource_type="agent",
        resource_id=agent.id,
        summary=f"Toggled agent '{agent.id}' active status to {agent.is_active}",
    )
    await db.commit()
    await db.refresh(agent)

    await publish_event("agent-config-updates", {"action": "updated", "hub_id": ctx.hub_id, "agent_id": agent.id})
    return await _to_agent_response(db, agent, ctx.hub.slug)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    ctx: HubContext = Depends(require_hub(hub_type="agent", min_role="maintainer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Delete an agent definition."""
    deleted = await repo_delete_agent(db, hub_id=ctx.hub_id, agent_id=agent_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")

    await _log_audit_event(
        db,
        hub_id=ctx.hub_id,
        actor_user_id=ctx.user_id,
        action="delete",
        resource_type="agent",
        resource_id=agent_id,
        summary=f"Deleted agent '{agent_id}'",
    )
    await db.commit()

    await publish_event("agent-config-updates", {"action": "deleted", "hub_id": ctx.hub_id, "agent_id": agent_id})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{agent_id}/duplicate", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_agent(
    agent_id: str,
    ctx: HubContext = Depends(require_hub(hub_type="agent", min_role="contributor")),
    db: AsyncSession = Depends(get_async_db),
) -> AgentResponse:
    """Duplicate an existing agent within the hub."""
    original = await repo_get_agent(db, hub_id=ctx.hub_id, agent_id=agent_id)
    if not original:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")

    new_name = f"{original.name} (Copy)"
    slug = await generate_unique_slug(db, hub_id=ctx.hub_id, base_name=new_name)

    new_agent = AgentDefinition(
        id=str(uuid.uuid4()),
        hub_id=ctx.hub_id,
        name=new_name,
        role=original.role,
        system_prompt=original.system_prompt,
        model_id=original.model_id,
        tools=original.tools or [],
        collection_bindings_json=original.collection_bindings_json or [],
        temperature=original.temperature,
        max_tokens=original.max_tokens,
        is_active=original.is_active,
        endpoint_slug=slug,
    )
    db.add(new_agent)
    await _log_audit_event(
        db,
        hub_id=ctx.hub_id,
        actor_user_id=ctx.user_id,
        action="create",
        resource_type="agent",
        resource_id=new_agent.id,
        summary=f"Duplicated agent '{original.id}' to '{new_agent.id}'",
    )
    await db.commit()
    await db.refresh(new_agent)

    await publish_event("agent-config-updates", {"action": "created", "hub_id": ctx.hub_id, "agent_id": new_agent.id})
    return await _to_agent_response(db, new_agent, ctx.hub.slug)
