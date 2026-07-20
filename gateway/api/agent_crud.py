"""Agent CRUD REST API Endpoints for Gateway Agent Hub."""

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.clients.postgres import get_async_db
from common.models.database import AgentDefinition, ModelRegistryModel
from common.schemas.agent_types import AgentCreate, AgentResponse, AgentUpdate

router = APIRouter(prefix="/agents", tags=["agents"])
logger = logging.getLogger("gateway.api.agent_crud")


@router.get("", response_model=List[AgentResponse])
async def list_agents(db: AsyncSession = Depends(get_async_db)) -> List[AgentResponse]:
    """Retrieve all defined agents."""
    stmt = select(AgentDefinition).order_by(AgentDefinition.name.asc())
    result = await db.execute(stmt)
    agents = result.scalars().all()
    return [AgentResponse.model_validate(a) for a in agents]


@router.get("/models")
async def list_agent_models(db: AsyncSession = Depends(get_async_db)) -> dict:
    """Retrieve available completion models from Model Registry for Agent dropdowns."""
    stmt = select(ModelRegistryModel).where(
        ModelRegistryModel.role.in_(["completion", "classifier"]),
        ModelRegistryModel.is_enabled == True,
    )
    result = await db.execute(stmt)
    models = result.scalars().all()
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


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_async_db)) -> AgentResponse:
    """Retrieve details for a specific agent by ID."""
    stmt = select(AgentDefinition).where(AgentDefinition.id == agent_id)
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID '{agent_id}' not found.",
        )
    return AgentResponse.model_validate(agent)


from common.clients.redis import publish_event


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    payload: AgentCreate, db: AsyncSession = Depends(get_async_db)
) -> AgentResponse:
    """Create a new agent definition."""
    agent_id = str(uuid.uuid4())
    now = datetime.utcnow()

    new_agent = AgentDefinition(
        id=agent_id,
        name=payload.name,
        role=payload.role,
        system_prompt=payload.system_prompt,
        model_id=payload.model_id,
        tools=payload.tools,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        created_at=now,
        updated_at=now,
    )
    db.add(new_agent)
    try:
        await db.commit()
        await db.refresh(new_agent)
        logger.info("Created agent '%s' (ID: %s)", new_agent.name, agent_id)
        await publish_event("agent-config-updates", {"action": "created", "agent_id": agent_id})
        return AgentResponse.model_validate(new_agent)
    except Exception as e:
        await db.rollback()
        logger.error("Failed to create agent: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create agent definition: {str(e)}",
        )


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str, payload: AgentUpdate, db: AsyncSession = Depends(get_async_db)
) -> AgentResponse:
    """Update configurations for an existing agent."""
    stmt = select(AgentDefinition).where(AgentDefinition.id == agent_id)
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID '{agent_id}' not found.",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(agent, field, value)

    agent.updated_at = datetime.utcnow()

    try:
        await db.commit()
        await db.refresh(agent)
        logger.info("Updated agent '%s' (ID: %s)", agent.name, agent_id)
        await publish_event("agent-config-updates", {"action": "updated", "agent_id": agent_id})
        return AgentResponse.model_validate(agent)
    except Exception as e:
        await db.rollback()
        logger.error("Failed to update agent %s: %s", agent_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update agent definition: {str(e)}",
        )


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str, db: AsyncSession = Depends(get_async_db)) -> dict:
    """Delete an agent definition."""
    stmt = select(AgentDefinition).where(AgentDefinition.id == agent_id)
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID '{agent_id}' not found.",
        )

    await db.delete(agent)
    try:
        await db.commit()
        logger.info("Deleted agent '%s' (ID: %s)", agent.name, agent_id)
        await publish_event("agent-config-updates", {"action": "deleted", "agent_id": agent_id})
        return {"status": "success", "id": agent_id}
    except Exception as e:
        await db.rollback()
        logger.error("Failed to delete agent %s: %s", agent_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete agent definition: {str(e)}",
        )
