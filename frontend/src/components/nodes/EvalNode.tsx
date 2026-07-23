import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import { TestTube, Check, X } from "lucide-react";

export const EvalNode = memo(({ data }: any) => {
  const label = data?.label || "Inline Evaluation";
  const suiteName = data?.suite_name || "Accuracy Suite";
  const framework = (data?.framework || "RAGAS").toUpperCase();
  const threshold = data?.threshold || 0.7;
  const status = data?.status || "idle";

  return (
    <div className="px-4 py-3 rounded-xl bg-[var(--bg-surface-alt)] border border-emerald-500/40 shadow-xl min-w-[240px] max-w-[280px] select-none space-y-2 relative overflow-hidden">
      {/* Top Gradient Border */}
      <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-emerald-500 to-teal-300" />

      {/* Input Handle */}
      <Handle type="target" position={Position.Top} className="!bg-emerald-400 !w-3 !h-3" />

      {/* Header */}
      <div className="flex items-center justify-between gap-2 pt-1">
        <div className="flex items-center gap-2 overflow-hidden">
          <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 flex-shrink-0">
            <TestTube className="w-4 h-4" />
          </div>
          <span className="text-xs font-bold text-white truncate">{label}</span>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[9px] font-mono border border-emerald-500/30">
            {framework}
          </span>
          <span
            className={`w-2 h-2 rounded-full ${
              status === "running"
                ? "bg-emerald-400 animate-pulse"
                : status === "error"
                ? "bg-rose-500"
                : "bg-zinc-500"
            }`}
          />
        </div>
      </div>

      {/* Info Box */}
      <div className="p-1.5 rounded bg-[var(--bg-input)] border border-emerald-500/20 text-[10px] font-mono space-y-0.5">
        <div className="text-white font-semibold truncate">{suiteName}</div>
        <div className="text-emerald-400">Min Score: {threshold}</div>
      </div>

      {/* Dual Branch Output Handles */}
      <div className="flex justify-between items-center text-[10px] font-mono pt-1 text-zinc-400">
        <div className="flex items-center gap-1 text-emerald-400 font-bold">
          <Check className="w-3 h-3" /> Pass
        </div>
        <div className="flex items-center gap-1 text-rose-400 font-bold">
          Fail <X className="w-3 h-3" />
        </div>
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        id="pass"
        style={{ left: "30%" }}
        className="!bg-emerald-400 !w-3 !h-3"
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="fail"
        style={{ left: "70%" }}
        className="!bg-rose-500 !w-3 !h-3"
      />
    </div>
  );
});

EvalNode.displayName = "EvalNode";
