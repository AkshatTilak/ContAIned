import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import { Bot, Terminal } from "lucide-react";

export const AgentNode = memo(({ data }: any) => {
  const label = data?.label || "Subagent Node";
  const modelId = data?.model_id || "Arch-Router-1.5B";
  const tools: string[] = data?.tools || ["retrieval"];
  const hasPromptOverride = Boolean(data?.system_prompt);
  const status = data?.status || "idle"; // idle, running, error

  return (
    <div className="px-4 py-3 rounded-xl bg-[var(--bg-surface-alt)] border border-amber-500/40 shadow-xl min-w-[240px] max-w-[280px] select-none space-y-2 relative overflow-hidden">
      {/* Top Gradient Border */}
      <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-amber-500 to-amber-300" />
      
      <Handle type="target" position={Position.Top} className="!bg-amber-400 !w-3 !h-3" />
      
      <div className="flex items-center justify-between gap-2 pt-1">
        <div className="flex items-center gap-2 overflow-hidden">
          <div className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400 flex-shrink-0">
            <Bot className="w-4 h-4" />
          </div>
          <span className="text-xs font-bold text-white truncate">{label}</span>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <span
            className={`w-2 h-2 rounded-full ${
              status === "running"
                ? "bg-emerald-400 animate-pulse shadow-[0_0_6px_rgba(52,211,153,0.8)]"
                : status === "error"
                ? "bg-rose-500"
                : "bg-zinc-500"
            }`}
            title={`Status: ${status}`}
          />
          {hasPromptOverride && (
            <span className="px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-400 text-[9px] font-mono border border-indigo-500/20">
              Override
            </span>
          )}
        </div>
      </div>

      <div className="flex items-center gap-1.5 text-[10px] text-zinc-400 font-mono truncate">
        <Terminal className="w-3 h-3 text-amber-400 flex-shrink-0" />
        <span className="truncate">{modelId}</span>
      </div>

      <div className="flex flex-wrap gap-1 pt-1">
        {tools.map((tool) => (
          <span key={tool} className="px-1.5 py-0.5 rounded bg-[var(--bg-input)] text-[9px] text-amber-400 border border-amber-500/20 font-mono truncate max-w-[120px]">
            {tool}
          </span>
        ))}
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-amber-400 !w-3 !h-3" />
    </div>
  );
});

AgentNode.displayName = "AgentNode";

