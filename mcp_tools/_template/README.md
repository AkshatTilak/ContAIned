# Starter MCP Server Template

This directory provides a reference skeleton implementing all ContAIned MCP protocol endpoints (REST and JSON-RPC 2.0).

## How to use
1. Copy this folder to `mcp_tools/your_tool_name`.
2. Add your custom tools in `server.py` within `TOOLS_REGISTRY` and `execute_tool()`.
3. Start the server:
   ```bash
   python server.py --port 8091
   ```
4. Register the URL `http://localhost:8091` in ContAIned MCP Registry.
