import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import { Cpu } from "lucide-react";

export const ClassifierNode = memo(({ data }: any) => {
  const threshold = data?.threshold ?? 0.75;
  const label = data?.label || "Task Classifier (Arch-Router)";

  return (
    <div className="px-4 py-3 rounded-xl bg-[#181a21] border border-emerald-500/40 shadow-xl min-w-[220px] select-none space-y-2">
      <Handle type="target" position={Position.Top} className="!bg-emerald-400 !w-3 !h-3" />
      
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400">
            <Cpu className="w-4 h-4" />
          </div>
          <span className="text-xs font-bold text-white truncate max-w-[130px]">{label}</span>
        </div>
        <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[10px] font-mono border border-emerald-500/20">
          {(threshold * 100).toFixed(0)}% Conf
        </span>
      </div>

      <p className="text-[11px] text-zinc-400 line-clamp-1">
        Complexity Classifier & Router
      </p>

      <Handle type="source" position={Position.Bottom} className="!bg-emerald-400 !w-3 !h-3" />
    </div>
  );
});

ClassifierNode.displayName = "ClassifierNode";
