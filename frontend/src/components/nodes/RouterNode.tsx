import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import { Route, CornerDownRight } from "lucide-react";

export const RouterNode = memo(({ data }: any) => {
  const label = data?.label || "Multi-Branch Router";
  const routes: any[] = data?.routes || [{ label: "Route A" }, { label: "Route B" }];
  const defaultRoute = data?.default_route || "Default";
  const status = data?.status || "idle";

  return (
    <div className="px-4 py-3 rounded-xl bg-[var(--bg-surface-alt)] border border-pink-500/40 shadow-xl min-w-[240px] max-w-[280px] select-none space-y-2 relative overflow-hidden">
      {/* Top Gradient Border */}
      <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-pink-500 to-rose-400" />

      {/* Input Handle */}
      <Handle type="target" position={Position.Top} className="!bg-pink-400 !w-3 !h-3" />

      {/* Header */}
      <div className="flex items-center justify-between gap-2 pt-1">
        <div className="flex items-center gap-2 overflow-hidden">
          <div className="p-1.5 rounded-lg bg-pink-500/10 text-pink-400 flex-shrink-0">
            <Route className="w-4 h-4" />
          </div>
          <span className="text-xs font-bold text-white truncate">{label}</span>
        </div>
        <span
          className={`w-2 h-2 rounded-full shrink-0 ${
            status === "running"
              ? "bg-pink-400 animate-pulse"
              : status === "error"
              ? "bg-rose-500"
              : "bg-zinc-500"
          }`}
        />
      </div>

      {/* Routes List Display */}
      <div className="p-1.5 rounded bg-[var(--bg-input)] border border-pink-500/20 text-[10px] font-mono space-y-1">
        {routes.slice(0, 3).map((r, idx) => (
          <div key={idx} className="flex items-center gap-1 text-pink-300 truncate">
            <CornerDownRight className="w-3 h-3 text-pink-400 shrink-0" />
            <span className="truncate">{r.label || `Branch ${idx + 1}`}</span>
          </div>
        ))}
        {routes.length > 3 && (
          <div className="text-[9px] text-zinc-400 italic">+ {routes.length - 3} more branches</div>
        )}
        <div className="text-[9px] text-zinc-400 border-t border-pink-500/20 pt-1">
          Fallback: {defaultRoute}
        </div>
      </div>

      {/* Multi-Output Handles */}
      <div className="flex justify-between items-center text-[9px] font-mono text-zinc-400 pt-1">
        {routes.slice(0, 3).map((r, idx) => (
          <span key={idx} className="truncate max-w-[60px] text-pink-400 font-semibold">
            {r.label || `B${idx + 1}`}
          </span>
        ))}
      </div>

      {routes.slice(0, 3).map((r, idx) => {
        const total = Math.min(routes.length, 3);
        const offsetPercent = ((idx + 1) / (total + 1)) * 100;
        return (
          <Handle
            key={idx}
            type="source"
            position={Position.Bottom}
            id={r.label || `branch_${idx}`}
            style={{ left: `${offsetPercent}%` }}
            className="!bg-pink-400 !w-3 !h-3"
          />
        );
      })}
    </div>
  );
});

RouterNode.displayName = "RouterNode";
