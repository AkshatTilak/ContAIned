import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import { Users, Bot } from "lucide-react";

export const MultiAgentNode = memo(({ data }: any) => {
  const label = data?.label || "Multi-Agent Node";
  const agentId = data?.agent_id || "sub_agent";
  const modelId = data?.model_id || "gemini/gemini-3.5-flash";
  const status = data?.status || "idle";

  return (
    <div className="px-4 py-3 rounded-xl bg-[var(--bg-surface-alt)] border border-violet-500/40 shadow-xl min-w-[240px] max-w-[280px] select-none space-y-2 relative overflow-hidden">
      {/* Top Gradient Border */}
      <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-violet-500 to-indigo-400" />

      <Handle type="target" position={Position.Top} className="!bg-violet-400 !w-3 !h-3" />

      <div className="flex items-center justify-between gap-2 pt-1">
        <div className="flex items-center gap-2 overflow-hidden">
          <div className="p-1.5 rounded-lg bg-violet-500/10 text-violet-400 flex-shrink-0">
            <Users className="w-4 h-4" />
          </div>
          <span className="text-xs font-bold text-white truncate">{label}</span>
        </div>
        <span
          className={`w-2 h-2 rounded-full shrink-0 ${
            status === "running"
              ? "bg-emerald-400 animate-pulse shadow-[0_0_6px_rgba(52,211,153,0.8)]"
              : status === "error"
              ? "bg-rose-500"
              : "bg-zinc-500"
          }`}
          title={`Status: ${status}`}
        />
      </div>

      <div className="flex items-center justify-between text-[10px] text-zinc-400 font-mono pt-0.5">
        <div className="flex items-center gap-1.5 truncate">
          <Bot className="w-3 h-3 text-violet-400 flex-shrink-0" />
          <span className="truncate text-violet-300 font-semibold">{agentId}</span>
        </div>
        <span className="px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-400 text-[9px] border border-violet-500/20 font-mono">
          SubAgent
        </span>
      </div>

      <div className="text-[9px] text-zinc-400 font-mono truncate bg-[var(--bg-input)] px-2 py-1 rounded border border-[var(--border-subtle)]">
        Model: {modelId}
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-violet-400 !w-3 !h-3" />
    </div>
  );
});

MultiAgentNode.displayName = "MultiAgentNode";
