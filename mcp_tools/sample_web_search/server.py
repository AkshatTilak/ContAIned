"""Sample Web Search MCP Server.

Implements REST (/tools, /invoke) and JSON-RPC 2.0 endpoints for search tools.
"""

import argparse
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

app = FastAPI(title="Sample Web Search MCP Server", version="1.0.0")

TOOLS_REGISTRY = [
    {
        "name": "web_search",
        "description": "Performs a web search for the given query and returns top matching snippets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query text"},
                "max_results": {"type": "integer", "description": "Maximum number of results to return", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch_page",
        "description": "Fetches page content from a specified URL.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Web URL to fetch"},
            },
            "required": ["url"],
        },
    },
]


def execute_search_tool(tool_name: str, parameters: Dict[str, Any]) -> Any:
    """Execute search or fetch tool."""
    if tool_name == "web_search":
        query = parameters.get("query", "")
        max_results = int(parameters.get("max_results", 5))
        return {
            "query": query,
            "results": [
                {
                    "title": f"Result for {query} - ContAIned Knowledge Base",
                    "snippet": f"Detailed documentation and references about {query} in modern AI systems.",
                    "url": f"https://contained.ai/docs?q={query}",
                }
                for _ in range(min(max_results, 3))
            ],
        }
    elif tool_name == "fetch_page":
        url = parameters.get("url", "")
        return {
            "url": url,
            "status": 200,
            "content": f"Sample simulated web page body content for {url}.",
        }
    raise ValueError(f"Unknown search tool: {tool_name}")


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
    return {"status": "healthy", "server": "sample-web-search-server", "version": "1.0.0"}


@app.get("/tools")
async def list_tools_rest():
    return {"tools": TOOLS_REGISTRY}


@app.post("/invoke")
async def invoke_tool_rest(req: RESTInvokeRequest):
    params = req.parameters or req.arguments or {}
    try:
        result = execute_search_tool(req.name, params)
        return {"status": "success", "result": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Web search execution error: {str(e)}")


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
            res = execute_search_tool(tool_name, args)
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
    parser = argparse.ArgumentParser(description="Run Sample Web Search MCP Server")
    parser.add_argument("--port", type=int, default=8093, help="Port to bind")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind")
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
