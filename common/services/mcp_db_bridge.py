"""Dynamic Database MCP Tool Bridge (Task 12_02).

Exposes registered external database connection profiles (`ExternalCredential`)
as executable MCP tools for LLM agents. Each credential generates three standard
tool definitions:

1. `db_schema_inspector`   — inspect tables/collections, columns, keys.
2. `db_query_executor`     — run a read-only SQL query, returning JSON rows.
3. `mongo_collection_query`— query a MongoDB collection by filter.

The bridge is registered through the existing Gateway MCP registry
(`gateway/api/mcp_manager.py`) and invoked by Agent Hub LLM agents via
`gateway/services/mcp_client.py`-style tool calls.
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.clients.postgres import get_sessionmaker
from common.models.database import ExternalCredential
from common.clients.db_connectors.pool_manager import get_connector

logger = logging.getLogger("common.services.mcp_db_bridge")

# ---------------------------------------------------------------------------
# Tool definition generators
# ---------------------------------------------------------------------------

def _schema_inspector_tool() -> Dict[str, Any]:
    return {
        "tool_name": "db_schema_inspector",
        "description": (
            "Inspect the schema of an external database connection: list tables/"
            "collections, columns, data types, primary keys, and foreign keys."
        ),
        "input_schema_json": {
            "type": "object",
            "properties": {
                "credential_id": {"type": "string", "description": "ExternalCredential UUID"},
                "table_name": {"type": "string", "description": "Optional specific table/collection"},
            },
            "required": ["credential_id"],
        },
    }


def _query_executor_tool() -> Dict[str, Any]:
    return {
        "tool_name": "db_query_executor",
        "description": (
            "Execute a read-only SQL query against an external relational database "
            "(Postgres/MySQL) and return the result rows as JSON."
        ),
        "input_schema_json": {
            "type": "object",
            "properties": {
                "credential_id": {"type": "string", "description": "ExternalCredential UUID"},
                "sql_query": {"type": "string", "description": "Read-only SELECT query"},
                "params": {"type": "object", "description": "Optional bound parameters"},
            },
            "required": ["credential_id", "sql_query"],
        },
    }


def _mongo_collection_query_tool() -> Dict[str, Any]:
    return {
        "tool_name": "mongo_collection_query",
        "description": (
            "Query a MongoDB collection by filter and return matching documents."
        ),
        "input_schema_json": {
            "type": "object",
            "properties": {
                "credential_id": {"type": "string", "description": "ExternalCredential UUID"},
                "collection": {"type": "string", "description": "Collection name"},
                "filter": {"type": "object", "description": "MongoDB filter document"},
                "limit": {"type": "integer", "description": "Max documents to return"},
            },
            "required": ["credential_id", "collection"],
        },
    }


def generate_db_tool_definitions(credential: ExternalCredential) -> List[Dict[str, Any]]:
    """Return the three standard MCP tool definitions for a credential."""
    db_type = (credential.db_type or "").lower()
    tools = [_schema_inspector_tool(), _query_executor_tool()]
    if db_type in {"mongodb", "mongo"}:
        tools.append(_mongo_collection_query_tool())
    return tools


# ---------------------------------------------------------------------------
# Tool execution dispatcher
# ---------------------------------------------------------------------------

async def _load_credential(session: AsyncSession, credential_id: str) -> Optional[ExternalCredential]:
    stmt = select(ExternalCredential).where(ExternalCredential.id == credential_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def execute_db_tool(
    tool_name: str,
    parameters: Dict[str, Any],
    *,
    hub_id: Optional[str] = None,
    session_factory: Optional[Any] = None,
) -> Dict[str, Any]:
    """Dispatch a database MCP tool call to the appropriate connector.

    Returns an MCP-style result dict:
    {"status": "success", "result": Any} or {"status": "error", "error": str}.
    """
    credential_id = parameters.get("credential_id", "")
    if not credential_id:
        return {"status": "error", "error": "Missing 'credential_id' parameter"}

    try:
        sf = session_factory or get_sessionmaker()
        async with sf() as session:  # type: AsyncSession
            cred = await _load_credential(session, credential_id)
            if not cred:
                return {"status": "error", "error": f"ExternalCredential '{credential_id}' not found"}

            # Enforce hub scoping when a hub_id is provided.
            if hub_id and cred.hub_id != hub_id:
                return {"status": "error", "error": "Credential is not accessible in this hub"}

            connector = await get_connector(cred)

            if tool_name == "db_schema_inspector":
                metadata = await connector.get_schema_metadata()
                return {"status": "success", "result": metadata}

            if tool_name == "db_query_executor":
                sql_query = parameters.get("sql_query", "")
                params = parameters.get("params") or {}
                rows = await connector.execute_query(
                    sql_query,
                    params=params or None,
                    timeout_s=int(parameters.get("timeout_s", 30)),
                    max_rows=int(parameters.get("max_rows", 500)),
                )
                return {"status": "success", "result": rows}

            if tool_name == "mongo_collection_query":
                collection = parameters.get("collection", "")
                mongo_filter = parameters.get("filter", {}) or {}
                limit = int(parameters.get("limit", 100))
                rows = await connector.execute_query(
                    collection,
                    params={"filter": mongo_filter, "limit": limit},
                    max_rows=limit,
                )
                return {"status": "success", "result": rows}

            return {"status": "error", "error": f"Unknown database tool '{tool_name}'"}
    except Exception as exc:  # noqa: BLE001 - surface any DB failure to the agent
        logger.warning("db tool '%s' failed: %s", tool_name, exc)
        return {"status": "error", "error": str(exc)}


def format_rows_as_markdown(rows: List[Dict[str, Any]]) -> str:
    """Format a list of row dicts as a Markdown table for agent context."""
    if not rows:
        return "_No rows returned._"
    headers = list(rows[0].keys())
    lines = ["| " + " | ".join(str(h) for h in headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
    return "\n".join(lines)
