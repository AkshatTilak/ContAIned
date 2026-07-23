import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import { Network, Lock } from "lucide-react";

export const APICallNode = memo(({ data }: any) => {
  const label = data?.label || "REST API Call";
  const url = data?.url || "https://api.example.com/data";
  const method = (data?.method || "GET").toUpperCase();
  const authType = data?.auth_type || "none";
  const status = data?.status || "idle";

  const getMethodBadgeColor = () => {
    switch (method) {
      case "GET":
        return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
      case "POST":
        return "bg-blue-500/20 text-blue-400 border-blue-500/30";
      case "PUT":
        return "bg-amber-500/20 text-amber-400 border-amber-500/30";
      case "DELETE":
        return "bg-rose-500/20 text-rose-400 border-rose-500/30";
      default:
        return "bg-cyan-500/20 text-cyan-400 border-cyan-500/30";
    }
  };

  return (
    <div className="px-4 py-3 rounded-xl bg-[var(--bg-surface-alt)] border border-blue-500/40 shadow-xl min-w-[240px] max-w-[280px] select-none space-y-2 relative overflow-hidden">
      {/* Top Gradient Border */}
      <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-blue-500 to-teal-400" />

      {/* Input Handle */}
      <Handle type="target" position={Position.Left} className="!bg-blue-400 !w-3 !h-3" />

      {/* Header */}
      <div className="flex items-center justify-between gap-2 pt-1">
        <div className="flex items-center gap-2 overflow-hidden">
          <div className="p-1.5 rounded-lg bg-blue-500/10 text-blue-400 flex-shrink-0">
            <Network className="w-4 h-4" />
          </div>
          <span className="text-xs font-bold text-white truncate">{label}</span>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <span className={`px-1.5 py-0.5 rounded text-[9px] font-mono font-bold border ${getMethodBadgeColor()}`}>
            {method}
          </span>
          <span
            className={`w-2 h-2 rounded-full ${
              status === "running"
                ? "bg-blue-400 animate-pulse"
                : status === "error"
                ? "bg-rose-500"
                : "bg-zinc-500"
            }`}
          />
        </div>
      </div>

      {/* URL & Auth Info */}
      <div className="p-1.5 rounded bg-[var(--bg-input)] border border-blue-500/20 space-y-1">
        <div className="text-[10px] text-zinc-300 font-mono truncate">{url}</div>
        {authType !== "none" && (
          <div className="flex items-center gap-1 text-[9px] text-blue-300 font-mono">
            <Lock className="w-2.5 h-2.5" /> Auth: {authType}
          </div>
        )}
      </div>

      {/* Output Handle */}
      <Handle type="source" position={Position.Right} className="!bg-blue-400 !w-3 !h-3" />
    </div>
  );
});

APICallNode.displayName = "APICallNode";
