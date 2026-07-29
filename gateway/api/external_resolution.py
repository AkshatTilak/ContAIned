"""Qualified External API Agent Resolution & Key Scoping (S6-05d).

Resolves '{hub_slug}/{agent_slug}' model strings for external OpenAI-compatible endpoints.
Failure semantics anti-enumeration: unauthorized or non-existent models yield 404 MODEL_NOT_FOUND.
"""

import logging
import re
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.constants.roles import PLATFORM_ROLE_ADMIN, hub_role_satisfies
from common.models.database import AgentDefinition, Hub, HubMember, User

logger = logging.getLogger("gateway.api.external_resolution")

QUALIFIED_MODEL_RE = re.compile(
    r"^(?P<hub_slug>[a-z0-9][a-z0-9-]{0,63})/(?P<agent_slug>[a-z0-9][a-z0-9-]{0,99})$"
)


async def resolve_qualified_agent(
    session: AsyncSession,
    *,
    model: str,
    api_key_hub_id: Optional[str] = None,
    api_key_user_id: Optional[str] = None,
) -> Optional[AgentDefinition]:
    """Resolves '{hub_slug}/{agent_slug}' model strings and applies key/user scoping.

    Returns None if `model` is not in '{hub_slug}/{agent_slug}' format (caller then treats as registry model).
    Raises 404 MODEL_NOT_FOUND or 403 for unauthorized access.
    """
    match = QUALIFIED_MODEL_RE.match(model.strip())
    if not match:
        return None

    hub_slug = match.group("hub_slug")
    agent_slug = match.group("agent_slug")

    # 1. Resolve Hub
    hub_stmt = select(Hub).where(
        Hub.slug == hub_slug,
        Hub.hub_type == "agent",
        Hub.is_archived == False,
    )
    hub = (await session.execute(hub_stmt)).scalar_one_or_none()
    if not hub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"The model '{model}' does not exist.",
            headers={"X-Error-Code": "MODEL_NOT_FOUND"},
        )

    # 2. Key Scoping Check
    if api_key_hub_id:
        if hub.id != api_key_hub_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"The model '{model}' does not exist.",
                headers={"X-Error-Code": "MODEL_NOT_FOUND"},
            )
    else:
        # Platform Key check
        if not api_key_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Platform key is not bound to a user.",
                headers={"X-Error-Code": "KEY_NOT_BOUND_TO_USER"},
            )
        user = await session.get(User, api_key_user_id)
        if not user or not user.status == "active":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"The model '{model}' does not exist.",
                headers={"X-Error-Code": "MODEL_NOT_FOUND"},
            )

        if user.platform_role != PLATFORM_ROLE_ADMIN:
            mem_stmt = select(HubMember).where(
                HubMember.hub_id == hub.id, HubMember.user_id == user.id
            )
            membership = (await session.execute(mem_stmt)).scalar_one_or_none()
            if not membership or not hub_role_satisfies(membership.hub_role, "contributor"):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"The model '{model}' does not exist.",
                    headers={"X-Error-Code": "MODEL_NOT_FOUND"},
                )

    # 3. Resolve Agent in Hub
    agent_stmt = select(AgentDefinition).where(
        AgentDefinition.hub_id == hub.id,
        AgentDefinition.endpoint_slug == agent_slug,
        AgentDefinition.is_active == True,
    )
    agent = (await session.execute(agent_stmt)).scalar_one_or_none()
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"The model '{model}' does not exist.",
            headers={"X-Error-Code": "MODEL_NOT_FOUND"},
        )

    return agent
