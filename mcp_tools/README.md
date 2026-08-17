# ContAIned MCP Tools Ecosystem & Developer Guide

Welcome to the Model Context Protocol (MCP) tool ecosystem in ContAIned.

This directory serves as the canonical registry and starting point for building, testing, and registering custom MCP tool servers into ContAIned workflows and autonomous agents.

---

## 1. What is Model Context Protocol (MCP)?

The Model Context Protocol (MCP) is an open standard that allows LLMs and autonomous agents to securely discover and invoke tools, query external datastores, and interact with external APIs.

ContAIned supports:
- **REST Protocol**: `GET /tools` for discovery, `POST /invoke` for execution.
- **JSON-RPC Protocol**: `tools/list` method for discovery, `tools/call` method for execution.
- **Authentication**: `none`, `bearer` token, or `api_key` header (encrypted at rest using AES-256 Fernet).
- **Transport Types**: `streamable_http`, `sse`, and `stdio`.

---

## 2. Directory Structure

```
mcp_tools/
├── README.md                    # This developer guide
├── _template/                   # Starter template with full REST + JSON-RPC boilerplate
│   ├── server.py
│   ├── requirements.txt
│   └── README.md
├── sample_calculator/           # Arithmetic tool server (add, subtract, multiply, divide, power)
│   ├── server.py
│   ├── requirements.txt
│   └── README.md
├── sample_web_search/           # Web search tool server
│   ├── server.py
│   ├── requirements.txt
│   └── README.md
└── sample_code_executor/        # Sandboxed Python code execution server
    ├── server.py
    ├── requirements.txt
    └── README.md
```

---

## 3. Protocol Specification

Your tool server must implement either REST or JSON-RPC (or both, recommended):

### REST Endpoints
1. **Health Check**: `GET /`
   - Returns HTTP 200: `{"status": "healthy"}`
2. **Tool Discovery**: `GET /tools`
   - Returns list of tool definitions:
     ```json
     {
       "tools": [
         {
           "name": "tool_name",
           "description": "Tool functionality description",
           "inputSchema": {
             "type": "object",
             "properties": {
               "param1": {"type": "string", "description": "Description"}
             },
             "required": ["param1"]
           }
         }
       ]
     }
     ```
3. **Tool Invocation**: `POST /invoke`
   - Request Body: `{"name": "tool_name", "parameters": {"param1": "value"}}`
   - Response Body: `{"status": "success", "result": ...}`

### JSON-RPC 2.0 Endpoint
- Single endpoint `POST /`
- **Method `tools/list`**:
  ```json
  {"jsonrpc": "2.0", "id": 1, "result": {"tools": [...]}}
  ```
- **Method `tools/call`**:
  ```json
  {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "result"}]}}
  ```

---

## 4. Quickstart: Building and Registering a Tool

1. **Copy the starter template**:
   ```bash
   cp -r mcp_tools/_template mcp_tools/my_custom_tool
   cd mcp_tools/my_custom_tool
   pip install -r requirements.txt
   ```
2. **Implement your tools** in `server.py`.
3. **Run your server locally**:
   ```bash
   python server.py --port 8090
   ```
4. **Register in ContAIned**:
   ```bash
   curl -X POST http://localhost:8000/api/mcp/servers \
     -H "Authorization: Bearer <YOUR_TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "My Custom Tool",
       "url": "http://localhost:8090",
       "transport": "streamable_http",
       "auth_type": "none"
     }'
   ```
5. **Use in Workflows**:
   In GuardRoute workflow canvas, add an `mcp_tool` node, select your server and tool, and connect it downstream to any agent or evaluation pipeline.
