import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import { Zap, Send, Database } from "lucide-react";

export const ActionNode = memo(({ data }: any) => {
  const label = data?.label || "Terminal Action Node";
  const actionType = data?.action_type || "http_post";
  const url = data?.url || "";

  return (
    <div className="px-4 py-3 rounded-xl bg-[var(--bg-surface-alt)] border border-rose-500/40 shadow-xl min-w-[240px] max-w-[280px] select-none space-y-2 relative overflow-hidden">
      {/* Top Red Gradient Border */}
      <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-rose-500 to-amber-500" />

      <Handle type="target" position={Position.Top} className="!bg-rose-400 !w-3 !h-3" />

      <div className="flex items-center justify-between gap-2 pt-1">
        <div className="flex items-center gap-2 overflow-hidden">
          <div className="p-1.5 rounded-lg bg-rose-500/10 text-rose-400 flex-shrink-0">
            {actionType === "http_post" ? <Send className="w-4 h-4" /> : <Zap className="w-4 h-4" />}
          </div>
          <span className="text-xs font-bold text-white truncate">{label}</span>
        </div>
        <span className="px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 text-[10px] font-mono border border-rose-500/20 shrink-0">
          Terminal
        </span>
      </div>

      <div className="flex items-center gap-1.5 text-[10px] text-zinc-400 font-mono">
        <Database className="w-3 h-3 text-rose-400 flex-shrink-0" />
        <span className="uppercase text-rose-300 font-semibold">{actionType}</span>
      </div>

      {url && (
        <div className="text-[9px] text-rose-300 font-mono truncate bg-[var(--bg-input)] px-2 py-1 rounded border border-rose-500/20">
          {url}
        </div>
      )}
    </div>
  );
});

ActionNode.displayName = "ActionNode";
