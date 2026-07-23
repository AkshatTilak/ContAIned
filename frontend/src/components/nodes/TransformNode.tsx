import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import { Sliders, Code } from "lucide-react";

export const TransformNode = memo(({ data }: any) => {
  const label = data?.label || "Data Transform";
  const mode = (data?.mode || "template").toLowerCase();
  const status = data?.status || "idle";

  const getModeBadge = () => {
    switch (mode) {
      case "template":
        return "Jinja2 Template";
      case "extract_field":
        return "Extract Field";
      case "merge":
        return "Merge Dicts";
      case "format_json":
        return "JSON Format";
      default:
        return mode;
    }
  };

  return (
    <div className="px-4 py-3 rounded-xl bg-[var(--bg-surface-alt)] border border-yellow-500/40 shadow-xl min-w-[240px] max-w-[280px] select-none space-y-2 relative overflow-hidden">
      {/* Top Gradient Border */}
      <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-yellow-500 to-amber-300" />

      {/* Input Handle */}
      <Handle type="target" position={Position.Left} className="!bg-yellow-400 !w-3 !h-3" />

      {/* Header */}
      <div className="flex items-center justify-between gap-2 pt-1">
        <div className="flex items-center gap-2 overflow-hidden">
          <div className="p-1.5 rounded-lg bg-yellow-500/10 text-yellow-400 flex-shrink-0">
            <Sliders className="w-4 h-4" />
          </div>
          <span className="text-xs font-bold text-white truncate">{label}</span>
        </div>
        <span
          className={`w-2 h-2 rounded-full shrink-0 ${
            status === "running"
              ? "bg-yellow-400 animate-pulse"
              : status === "error"
              ? "bg-rose-500"
              : "bg-zinc-500"
          }`}
        />
      </div>

      {/* Mode Details */}
      <div className="p-1.5 rounded bg-[var(--bg-input)] border border-yellow-500/20 text-[10px] font-mono flex items-center gap-1 text-yellow-300 truncate">
        <Code className="w-3 h-3 text-yellow-400 shrink-0" />
        <span className="truncate">{getModeBadge()}</span>
      </div>

      {/* Output Handle */}
      <Handle type="source" position={Position.Right} className="!bg-yellow-400 !w-3 !h-3" />
    </div>
  );
});

TransformNode.displayName = "TransformNode";
