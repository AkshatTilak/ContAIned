import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import { Send, Globe } from "lucide-react";

export const WebhookNode = memo(({ data }: any) => {
  const label = data?.label || "Outbound Webhook";
  const url = data?.url || "https://api.example.com/webhook";
  const method = (data?.method || "POST").toUpperCase();
  const status = data?.status || "idle";

  return (
    <div className="px-4 py-3 rounded-xl bg-[var(--bg-surface-alt)] border border-cyan-500/40 shadow-xl min-w-[240px] max-w-[280px] select-none space-y-2 relative overflow-hidden">
      {/* Top Gradient Border */}
      <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-cyan-500 to-blue-400" />

      {/* Input Handle */}
      <Handle type="target" position={Position.Left} className="!bg-cyan-400 !w-3 !h-3" />

      {/* Header */}
      <div className="flex items-center justify-between gap-2 pt-1">
        <div className="flex items-center gap-2 overflow-hidden">
          <div className="p-1.5 rounded-lg bg-cyan-500/10 text-cyan-400 flex-shrink-0">
            <Send className="w-4 h-4" />
          </div>
          <span className="text-xs font-bold text-white truncate">{label}</span>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <span className="px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 text-[9px] font-mono font-bold border border-cyan-500/30">
            {method}
          </span>
          <span
            className={`w-2 h-2 rounded-full ${
              status === "running"
                ? "bg-cyan-400 animate-pulse"
                : status === "error"
                ? "bg-rose-500"
                : "bg-zinc-500"
            }`}
          />
        </div>
      </div>

      {/* URL Display */}
      <div className="flex items-center gap-1.5 text-[10px] text-zinc-400 font-mono bg-[var(--bg-input)] p-1.5 rounded border border-cyan-500/20 truncate">
        <Globe className="w-3 h-3 text-cyan-400 shrink-0" />
        <span className="truncate">{url}</span>
      </div>

      {/* Output Handle */}
      <Handle type="source" position={Position.Right} className="!bg-cyan-400 !w-3 !h-3" />
    </div>
  );
});

WebhookNode.displayName = "WebhookNode";
