import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import { MessageSquareText, Sparkles } from "lucide-react";

export const FinalMessageNode = memo(({ data }: any) => {
  const label = data?.label || "Final Synthesis Message";
  const modelId = data?.model_id || "gemini/gemini-3.5-flash";

  return (
    <div className="px-4 py-3 rounded-xl bg-[var(--bg-surface-alt)] border border-emerald-500/40 shadow-xl min-w-[240px] max-w-[280px] select-none space-y-2 relative overflow-hidden">
      {/* Top Green Gradient Border */}
      <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-emerald-500 to-teal-400" />

      <Handle type="target" position={Position.Top} className="!bg-emerald-400 !w-3 !h-3" />

      <div className="flex items-center justify-between gap-2 pt-1">
        <div className="flex items-center gap-2 overflow-hidden">
          <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 flex-shrink-0">
            <MessageSquareText className="w-4 h-4" />
          </div>
          <span className="text-xs font-bold text-white truncate">{label}</span>
        </div>
        <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[10px] font-mono border border-emerald-500/20 shrink-0">
          Terminal
        </span>
      </div>

      <div className="flex items-center gap-1.5 text-[10px] text-emerald-400 font-mono">
        <Sparkles className="w-3 h-3 flex-shrink-0" />
        <span className="truncate">{modelId}</span>
      </div>

      <p className="text-[10px] text-zinc-400 line-clamp-1">
        Consolidates subagent state into final LLM synthesis response.
      </p>
    </div>
  );
});

FinalMessageNode.displayName = "FinalMessageNode";
