"""Annotated Starter MCP Server Template.

Implements both REST (/tools, /invoke) and JSON-RPC 2.0 (tools/list, tools/call)
specifications compatible with ContAIned MCP client and GuardRoute workflows.
"""

import argparse
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
import uvicorn

app = FastAPI(title="MCP Starter Template Server", version="1.0.0")

# --- Tool Definitions ---

TOOLS_REGISTRY = [
    {
        "name": "echo",
        "description": "Echoes back the provided message with optional uppercase transformation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Message string to echo",
                },
                "uppercase": {
                    "type": "boolean",
                    "description": "Whether to return the message in uppercase",
                    "default": False,
                },
            },
            "required": ["message"],
        },
    }
]


def execute_tool(tool_name: str, parameters: Dict[str, Any]) -> Any:
    """Core tool execution logic."""
    if tool_name == "echo":
        msg = parameters.get("message", "")
        if parameters.get("uppercase", False):
            msg = msg.upper()
        return {"echo": msg}
    raise ValueError(f"Unknown tool: {tool_name}")


# --- Pydantic Schemas ---

class RESTInvokeRequest(BaseModel):
    name: str
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    arguments: Optional[Dict[str, Any]] = Field(default_factory=dict)


class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = Field(default_factory=dict)
    id: Optional[Any] = 1


# --- Endpoints ---

@app.get("/")
async def health_check():
    """Health check endpoint for ContAIned MCP ping."""
    return {"status": "healthy", "server": "mcp-template-server", "version": "1.0.0"}


@app.get("/tools")
async def list_tools_rest():
    """REST endpoint for tool discovery."""
    return {"tools": TOOLS_REGISTRY}


@app.post("/invoke")
async def invoke_tool_rest(req: RESTInvokeRequest):
    """REST endpoint for tool execution."""
    params = req.parameters or req.arguments or {}
    try:
        result = execute_tool(req.name, params)
        return {"status": "success", "result": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")


@app.post("/")
async def handle_jsonrpc(req: JSONRPCRequest):
    """JSON-RPC 2.0 handler supporting tools/list and tools/call."""
    if req.method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req.id,
            "result": {"tools": TOOLS_REGISTRY},
        }
    elif req.method == "tools/call":
        params = req.params or {}
        tool_name = params.get("name")
        args = params.get("arguments") or params.get("parameters") or {}
        try:
            res = execute_tool(tool_name, args)
            return {
                "jsonrpc": "2.0",
                "id": req.id,
                "result": res,
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req.id,
                "error": {"code": -32603, "message": str(e)},
            }
    return {
        "jsonrpc": "2.0",
        "id": req.id,
        "error": {"code": -32601, "message": f"Method '{req.method}' not found"},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run MCP Template Server")
    parser.add_argument("--port", type=int, default=8091, help="Port to bind")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind")
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
