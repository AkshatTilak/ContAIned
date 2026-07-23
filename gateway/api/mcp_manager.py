"""API router for MCP Integration Hub (S5-05a, S5-05b, S5-05c, S5-05d)."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from common.clients.postgres import get_async_db
from common.models.database import MCPServer, MCPToolCache
from common.observability.logger import get_logger
from gateway.services.mcp_client import (
    check_server_health,
    decrypt_token,
    discover_tools,
    encrypt_token,
    invoke_tool,
)

logger = get_logger("gateway.api.mcp_manager")

router = APIRouter(prefix="/mcp", tags=["MCP Integration Hub"])


# --- Pydantic Schemas ---

class MCPServerCreate(BaseModel):
    name: str = Field(..., max_length=100)
    url: str = Field(..., max_length=500)
    transport: str = Field("sse", description="sse / stdio / streamable_http")
    auth_type: str = Field("none", description="none / bearer / api_key")
    auth_token: Optional[str] = None


class MCPServerUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    url: Optional[str] = Field(None, max_length=500)
    transport: Optional[str] = None
    auth_type: Optional[str] = None
    auth_token: Optional[str] = None
    is_active: Optional[bool] = None


class MCPServerResponse(BaseModel):
    id: str
    name: str
    url: str
    transport: str
    auth_type: str
    is_internal: bool
    is_active: bool
    health_status: str
    last_health_check: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    tool_count: int = 0


class MCPToolResponse(BaseModel):
    id: str
    server_id: str
    server_name: str
    tool_name: str
    description: Optional[str] = None
    input_schema_json: Optional[Dict[str, Any]] = None
    is_enabled: bool
    last_synced: datetime


class ToolInvokeRequest(BaseModel):
    server_id: str
    tool_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ToolTestRequest(BaseModel):
    parameters: Dict[str, Any] = Field(default_factory=dict)


# --- Helper Methods ---

async def sync_server_tools_db(server: MCPServer, session: AsyncSession) -> List[MCPToolCache]:
    """Helper function to discover tools from a server and update DB cache."""
    discovered = await discover_tools(server)

    # Fetch existing cached tools for server
    res = await session.execute(
        select(MCPToolCache).where(MCPToolCache.server_id == server.id)
    )
    existing_tools = {t.tool_name: t for t in res.scalars().all()}

    synced_tools: List[MCPToolCache] = []
    now = datetime.utcnow()

    for item in discovered:
        t_name = item["tool_name"]
        if t_name in existing_tools:
            tool_obj = existing_tools[t_name]
            tool_obj.description = item.get("description")
            tool_obj.input_schema_json = item.get("input_schema_json")
            tool_obj.last_synced = now
        else:
            tool_obj = MCPToolCache(
                server_id=server.id,
                tool_name=t_name,
                description=item.get("description"),
                input_schema_json=item.get("input_schema_json"),
                is_enabled=True,
                last_synced=now,
            )
            session.add(tool_obj)
        synced_tools.append(tool_obj)

    await session.commit()
    return synced_tools


async def register_mcp_server(
    session: AsyncSession,
    name: str,
    url: str,
    transport: str = "sse",
    auth_type: str = "none",
    auth_token: Optional[str] = None,
    is_internal: bool = False,
) -> MCPServer:
    """Utility function to programmatically register an MCP server."""
    res = await session.execute(select(MCPServer).where(MCPServer.name == name))
    existing = res.scalar_one_or_none()

    if existing:
        existing.url = url
        existing.transport = transport
        existing.auth_type = auth_type
        if auth_token:
            existing.auth_token_encrypted = encrypt_token(auth_token)
        existing.is_internal = is_internal
        existing.is_active = True
        await session.commit()
        await session.refresh(existing)
        server_obj = existing
    else:
        server_obj = MCPServer(
            name=name,
            url=url,
            transport=transport,
            auth_type=auth_type,
            auth_token_encrypted=encrypt_token(auth_token) if auth_token else None,
            is_internal=is_internal,
            is_active=True,
            health_status="unknown",
        )
        session.add(server_obj)
        await session.commit()
        await session.refresh(server_obj)

    # Health check & tool discovery
    health, _ = await check_server_health(server_obj)
    server_obj.health_status = health
    server_obj.last_health_check = datetime.utcnow()
    await session.commit()

    if health == "healthy":
        try:
            await sync_server_tools_db(server_obj, session)
        except Exception as e:
            logger.warning("Auto-sync tools failed for %s: %s", name, e)

    return server_obj


# --- API Endpoints ---

@router.get("/servers", response_model=List[MCPServerResponse])
async def list_mcp_servers(db: AsyncSession = Depends(get_async_db)):
    """List all registered MCP servers with health status and tool count."""
    res = await db.execute(select(MCPServer).order_by(MCPServer.created_at.desc()))
    servers = res.scalars().all()

    result = []
    for s in servers:
        tool_res = await db.execute(
            select(MCPToolCache).where(MCPToolCache.server_id == s.id)
        )
        tools = tool_res.scalars().all()
        result.append(
            MCPServerResponse(
                id=s.id,
                name=s.name,
                url=s.url,
                transport=s.transport,
                auth_type=s.auth_type,
                is_internal=s.is_internal,
                is_active=s.is_active,
                health_status=s.health_status,
                last_health_check=s.last_health_check,
                created_at=s.created_at,
                updated_at=s.updated_at,
                tool_count=len(tools),
            )
        )
    return result


@router.post("/servers", response_model=MCPServerResponse, status_code=status.HTTP_201_CREATED)
async def create_mcp_server(
    payload: MCPServerCreate, db: AsyncSession = Depends(get_async_db)
):
    """Register an external MCP server."""
    res = await db.execute(select(MCPServer).where(MCPServer.name == payload.name))
    if res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An MCP server with name '{payload.name}' is already registered.",
        )

    server = await register_mcp_server(
        session=db,
        name=payload.name,
        url=payload.url,
        transport=payload.transport,
        auth_type=payload.auth_type,
        auth_token=payload.auth_token,
        is_internal=False,
    )

    tool_res = await db.execute(
        select(MCPToolCache).where(MCPToolCache.server_id == server.id)
    )
    tools = tool_res.scalars().all()

    return MCPServerResponse(
        id=server.id,
        name=server.name,
        url=server.url,
        transport=server.transport,
        auth_type=server.auth_type,
        is_internal=server.is_internal,
        is_active=server.is_active,
        health_status=server.health_status,
        last_health_check=server.last_health_check,
        created_at=server.created_at,
        updated_at=server.updated_at,
        tool_count=len(tools),
    )


@router.put("/servers/{server_id}", response_model=MCPServerResponse)
async def update_mcp_server(
    server_id: str, payload: MCPServerUpdate, db: AsyncSession = Depends(get_async_db)
):
    """Update configuration for a registered MCP server."""
    res = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    server = res.scalar_one_or_none()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="MCP server not found"
        )

    if payload.name and payload.name != server.name:
        dup = await db.execute(select(MCPServer).where(MCPServer.name == payload.name))
        if dup.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Server name '{payload.name}' already exists.",
            )
        server.name = payload.name

    if payload.url:
        server.url = payload.url
    if payload.transport:
        server.transport = payload.transport
    if payload.auth_type:
        server.auth_type = payload.auth_type
    if payload.auth_token is not None:
        server.auth_token_encrypted = encrypt_token(payload.auth_token)
    if payload.is_active is not None:
        server.is_active = payload.is_active

    server.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(server)

    tool_res = await db.execute(
        select(MCPToolCache).where(MCPToolCache.server_id == server.id)
    )
    tools = tool_res.scalars().all()

    return MCPServerResponse(
        id=server.id,
        name=server.name,
        url=server.url,
        transport=server.transport,
        auth_type=server.auth_type,
        is_internal=server.is_internal,
        is_active=server.is_active,
        health_status=server.health_status,
        last_health_check=server.last_health_check,
        created_at=server.created_at,
        updated_at=server.updated_at,
        tool_count=len(tools),
    )


@router.delete("/servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mcp_server(server_id: str, db: AsyncSession = Depends(get_async_db)):
    """Delete an external MCP server registration (blocks deletion of internal servers)."""
    res = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    server = res.scalar_one_or_none()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="MCP server not found"
        )

    if server.is_internal:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete internal system MCP server.",
        )

    await db.delete(server)
    await db.commit()


@router.post("/servers/{server_id}/health")
async def trigger_health_check(server_id: str, db: AsyncSession = Depends(get_async_db)):
    """Trigger manual health check for a server."""
    res = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    server = res.scalar_one_or_none()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="MCP server not found"
        )

    status_str, err = await check_server_health(server)
    server.health_status = status_str
    server.last_health_check = datetime.utcnow()
    await db.commit()

    return {"server_id": server.id, "health_status": status_str, "error": err}


@router.get("/servers/{server_id}/tools", response_model=List[MCPToolResponse])
async def discover_and_sync_tools(
    server_id: str, db: AsyncSession = Depends(get_async_db)
):
    """Discover tools from a server and update DB cache."""
    res = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    server = res.scalar_one_or_none()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="MCP server not found"
        )

    synced = await sync_server_tools_db(server, db)
    return [
        MCPToolResponse(
            id=t.id,
            server_id=t.server_id,
            server_name=server.name,
            tool_name=t.tool_name,
            description=t.description,
            input_schema_json=t.input_schema_json,
            is_enabled=t.is_enabled,
            last_synced=t.last_synced,
        )
        for t in synced
    ]


@router.get("/tools", response_model=List[MCPToolResponse])
async def list_all_tools(db: AsyncSession = Depends(get_async_db)):
    """Get aggregated list of all cached tools across active servers."""
    query = (
        select(MCPToolCache, MCPServer.name)
        .join(MCPServer, MCPServer.id == MCPToolCache.server_id)
        .where(MCPServer.is_active == True)
        .order_by(MCPServer.name, MCPToolCache.tool_name)
    )
    res = await db.execute(query)
    rows = res.all()

    return [
        MCPToolResponse(
            id=tool.id,
            server_id=tool.server_id,
            server_name=server_name,
            tool_name=tool.tool_name,
            description=tool.description,
            input_schema_json=tool.input_schema_json,
            is_enabled=tool.is_enabled,
            last_synced=tool.last_synced,
        )
        for tool, server_name in rows
    ]


@router.put("/tools/{tool_id}/toggle")
async def toggle_mcp_tool(tool_id: str, db: AsyncSession = Depends(get_async_db)):
    """Enable or disable a specific cached tool."""
    res = await db.execute(select(MCPToolCache).where(MCPToolCache.id == tool_id))
    tool = res.scalar_one_or_none()
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="MCP tool not found"
        )

    tool.is_enabled = not tool.is_enabled
    await db.commit()
    return {"id": tool.id, "tool_name": tool.tool_name, "is_enabled": tool.is_enabled}


@router.post("/tools/invoke")
async def invoke_mcp_tool(payload: ToolInvokeRequest, db: AsyncSession = Depends(get_async_db)):
    """Invoke a registered MCP tool by server_id and tool_name."""
    res = await db.execute(select(MCPServer).where(MCPServer.id == payload.server_id))
    server = res.scalar_one_or_none()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="MCP server not found"
        )
    if not server.is_active:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"MCP server '{server.name}' is inactive.",
        )

    return await invoke_tool(server, payload.tool_name, payload.parameters)


@router.post("/servers/{server_id}/tools/{tool_name}/test")
async def test_mcp_tool(
    server_id: str,
    tool_name: str,
    payload: ToolTestRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """Inline test execution for a tool on a specific server."""
    res = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    server = res.scalar_one_or_none()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="MCP server not found"
        )

    return await invoke_tool(server, tool_name, payload.parameters)
