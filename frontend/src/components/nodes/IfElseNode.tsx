import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import { GitFork, Check, X } from "lucide-react";

export const IfElseNode = memo(({ data }: any) => {
  const label = data?.label || "If / Else Condition";
  const condType = data?.condition?.type || "complexity_equals";
  const targetVal = data?.condition?.value || "HIGH";
  const expr = data?.condition?.expression || "";
  const status = data?.status || "idle";

  const getSummary = () => {
    if (condType === "custom_expression" && expr) {
      return expr;
    }
    if (condType === "complexity_equals") {
      return `Complexity == "${targetVal}"`;
    }
    if (condType === "output_contains") {
      return `Contains "${targetVal}"`;
    }
    if (condType === "metadata_field") {
      return `${data?.condition?.field || "field"} ${data?.condition?.operator || "=="} ${targetVal}`;
    }
    if (condType === "regex_match") {
      return `Matches /${targetVal}/`;
    }
    return `Condition: ${condType}`;
  };

  return (
    <div className="px-4 py-3 rounded-xl bg-[var(--bg-surface-alt)] border border-purple-500/40 shadow-xl min-w-[240px] max-w-[280px] select-none space-y-2 relative overflow-hidden">
      {/* Top Gradient Border */}
      <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-purple-500 to-indigo-400" />

      {/* Single Input Handle */}
      <Handle type="target" position={Position.Top} className="!bg-purple-400 !w-3 !h-3" />

      {/* Header */}
      <div className="flex items-center justify-between gap-2 pt-1">
        <div className="flex items-center gap-2 overflow-hidden">
          <div className="p-1.5 rounded-lg bg-purple-500/10 text-purple-400 flex-shrink-0">
            <GitFork className="w-4 h-4" />
          </div>
          <span className="text-xs font-bold text-white truncate">{label}</span>
        </div>
        <span
          className={`w-2 h-2 rounded-full shrink-0 ${
            status === "running"
              ? "bg-purple-400 animate-pulse"
              : status === "error"
              ? "bg-rose-500"
              : "bg-zinc-500"
          }`}
        />
      </div>

      {/* Condition Summary */}
      <div className="p-2 rounded bg-[var(--bg-input)] border border-purple-500/20 text-[10px] font-mono text-purple-300 truncate">
        {getSummary()}
      </div>

      {/* Output Handles Info & Indicators */}
      <div className="flex justify-between items-center text-[10px] font-mono pt-1 text-zinc-400">
        <div className="flex items-center gap-1 text-emerald-400 font-bold">
          <Check className="w-3 h-3" /> True
        </div>
        <div className="flex items-center gap-1 text-rose-400 font-bold">
          False <X className="w-3 h-3" />
        </div>
      </div>

      {/* Dual Output Handles */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="true"
        style={{ left: "30%" }}
        className="!bg-emerald-400 !w-3 !h-3"
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="false"
        style={{ left: "70%" }}
        className="!bg-rose-500 !w-3 !h-3"
      />
    </div>
  );
});

IfElseNode.displayName = "IfElseNode";
