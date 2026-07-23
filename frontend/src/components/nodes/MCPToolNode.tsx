import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import { Wrench, Server } from "lucide-react";

export const MCPToolNode = memo(({ data }: any) => {
  const label = data?.label || "MCP Tool";
  const serverId = data?.server_id || "mcp-server";
  const toolName = data?.tool_name || "execute_action";
  const status = data?.status || "idle";

  return (
    <div className="px-4 py-3 rounded-xl bg-[var(--bg-surface-alt)] border border-orange-500/40 shadow-xl min-w-[240px] max-w-[280px] select-none space-y-2 relative overflow-hidden">
      {/* Top Gradient Border */}
      <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-orange-500 to-amber-400" />

      {/* Input Handle */}
      <Handle type="target" position={Position.Left} className="!bg-orange-400 !w-3 !h-3" />

      {/* Header */}
      <div className="flex items-center justify-between gap-2 pt-1">
        <div className="flex items-center gap-2 overflow-hidden">
          <div className="p-1.5 rounded-lg bg-orange-500/10 text-orange-400 flex-shrink-0">
            <Wrench className="w-4 h-4" />
          </div>
          <span className="text-xs font-bold text-white truncate">{label}</span>
        </div>
        <span
          className={`w-2 h-2 rounded-full shrink-0 ${
            status === "running"
              ? "bg-orange-400 animate-pulse"
              : status === "error"
              ? "bg-rose-500"
              : "bg-zinc-500"
          }`}
        />
      </div>

      {/* Details Box */}
      <div className="p-1.5 rounded bg-[var(--bg-input)] border border-orange-500/20 text-[10px] font-mono space-y-1">
        <div className="flex items-center gap-1 text-zinc-400 truncate">
          <Server className="w-3 h-3 text-orange-400 shrink-0" />
          <span className="truncate">{serverId}</span>
        </div>
        <div className="text-orange-300 font-semibold truncate">Tool: {toolName}</div>
      </div>

      {/* Output Handle */}
      <Handle type="source" position={Position.Right} className="!bg-orange-400 !w-3 !h-3" />
    </div>
  );
});

MCPToolNode.displayName = "MCPToolNode";
