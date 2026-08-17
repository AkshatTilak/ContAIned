"""Sample Calculator MCP Server.

Implements REST (/tools, /invoke) and JSON-RPC 2.0 endpoints for arithmetic tools.
"""

import argparse
import math
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

app = FastAPI(title="Sample Calculator MCP Server", version="1.0.0")

TOOLS_REGISTRY = [
    {
        "name": "add",
        "description": "Calculates the sum of two numbers (a + b).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "a": {"type": "number", "description": "First number"},
                "b": {"type": "number", "description": "Second number"},
            },
            "required": ["a", "b"],
        },
    },
    {
        "name": "subtract",
        "description": "Calculates the difference between two numbers (a - b).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "a": {"type": "number", "description": "Minuend"},
                "b": {"type": "number", "description": "Subtrahend"},
            },
            "required": ["a", "b"],
        },
    },
    {
        "name": "multiply",
        "description": "Calculates the product of two numbers (a * b).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "a": {"type": "number", "description": "First factor"},
                "b": {"type": "number", "description": "Second factor"},
            },
            "required": ["a", "b"],
        },
    },
    {
        "name": "divide",
        "description": "Divides a by b (a / b).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "a": {"type": "number", "description": "Numerator"},
                "b": {"type": "number", "description": "Denominator (non-zero)"},
            },
            "required": ["a", "b"],
        },
    },
    {
        "name": "power",
        "description": "Calculates base raised to exponent power (base ^ exponent).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "base": {"type": "number", "description": "Base number"},
                "exponent": {"type": "number", "description": "Exponent value"},
            },
            "required": ["base", "exponent"],
        },
    },
]


def execute_calculator_tool(tool_name: str, parameters: Dict[str, Any]) -> Any:
    """Execute arithmetic operation."""
    if tool_name == "add":
        a = float(parameters.get("a", 0))
        b = float(parameters.get("b", 0))
        return {"result": a + b}
    elif tool_name == "subtract":
        a = float(parameters.get("a", 0))
        b = float(parameters.get("b", 0))
        return {"result": a - b}
    elif tool_name == "multiply":
        a = float(parameters.get("a", 0))
        b = float(parameters.get("b", 0))
        return {"result": a * b}
    elif tool_name == "divide":
        a = float(parameters.get("a", 0))
        b = float(parameters.get("b", 1))
        if b == 0:
            raise ValueError("Division by zero is undefined.")
        return {"result": a / b}
    elif tool_name == "power":
        base = float(parameters.get("base", 0))
        exponent = float(parameters.get("exponent", 1))
        return {"result": math.pow(base, exponent)}
    raise ValueError(f"Unknown calculator tool: {tool_name}")


class RESTInvokeRequest(BaseModel):
    name: str
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    arguments: Optional[Dict[str, Any]] = Field(default_factory=dict)


class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = Field(default_factory=dict)
    id: Optional[Any] = 1


@app.get("/")
async def health_check():
    return {"status": "healthy", "server": "sample-calculator-server", "version": "1.0.0"}


@app.get("/tools")
async def list_tools_rest():
    return {"tools": TOOLS_REGISTRY}


@app.post("/invoke")
async def invoke_tool_rest(req: RESTInvokeRequest):
    params = req.parameters or req.arguments or {}
    try:
        result = execute_calculator_tool(req.name, params)
        return {"status": "success", "result": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calculator execution error: {str(e)}")


@app.post("/")
async def handle_jsonrpc(req: JSONRPCRequest):
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
            res = execute_calculator_tool(tool_name, args)
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
    parser = argparse.ArgumentParser(description="Run Sample Calculator MCP Server")
    parser.add_argument("--port", type=int, default=8092, help="Port to bind")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind")
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
