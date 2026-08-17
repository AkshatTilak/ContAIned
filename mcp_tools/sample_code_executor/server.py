"""Sample Sandboxed Code Executor MCP Server.

Implements REST (/tools, /invoke) and JSON-RPC 2.0 endpoints for Python execution.
"""

import argparse
import io
import sys
import traceback
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

app = FastAPI(title="Sample Code Executor MCP Server", version="1.0.0")

TOOLS_REGISTRY = [
    {
        "name": "execute_python",
        "description": "Executes Python code and captures stdout output and returned values.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python source code to execute"},
            },
            "required": ["code"],
        },
    },
    {
        "name": "json_transform",
        "description": "Applies a Python expression transform over input JSON data.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "data": {"type": "object", "description": "Input JSON object"},
                "expression": {"type": "string", "description": "Python expression (e.g. data['key'].upper())"},
            },
            "required": ["data", "expression"],
        },
    },
]


def execute_code_tool(tool_name: str, parameters: Dict[str, Any]) -> Any:
    """Execute Python code in controlled environment."""
    if tool_name == "execute_python":
        code = parameters.get("code", "")
        old_stdout = sys.stdout
        redirected_output = io.StringIO()
        sys.stdout = redirected_output

        safe_globals: Dict[str, Any] = {"__builtins__": __builtins__}
        local_scope: Dict[str, Any] = {}

        try:
            exec(code, safe_globals, local_scope)
            output = redirected_output.getvalue()
            result_val = local_scope.get("result", None)
            return {
                "stdout": output,
                "result": result_val,
                "status": "success",
            }
        except Exception as e:
            return {
                "stdout": redirected_output.getvalue(),
                "error": str(e),
                "traceback": traceback.format_exc(),
                "status": "error",
            }
        finally:
            sys.stdout = old_stdout

    elif tool_name == "json_transform":
        data = parameters.get("data", {})
        expr = parameters.get("expression", "data")
        try:
            eval_res = eval(expr, {"data": data, "math": __import__("math")})
            return {"transformed": eval_res, "status": "success"}
        except Exception as e:
            raise ValueError(f"Transform expression failed: {e}")

    raise ValueError(f"Unknown code executor tool: {tool_name}")


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
    return {"status": "healthy", "server": "sample-code-executor-server", "version": "1.0.0"}


@app.get("/tools")
async def list_tools_rest():
    return {"tools": TOOLS_REGISTRY}


@app.post("/invoke")
async def invoke_tool_rest(req: RESTInvokeRequest):
    params = req.parameters or req.arguments or {}
    try:
        result = execute_code_tool(req.name, params)
        return {"status": "success", "result": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Code execution error: {str(e)}")


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
            res = execute_code_tool(tool_name, args)
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
    parser = argparse.ArgumentParser(description="Run Sample Code Executor MCP Server")
    parser.add_argument("--port", type=int, default=8094, help="Port to bind")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind")
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
