import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import { Layers } from "lucide-react";

export const SynthesisNode = memo(({ data }: any) => {
  const label = data?.label || "Gather & Synthesis";

  return (
    <div className="px-4 py-3 rounded-xl bg-[#181a21] border border-cyan-500/40 shadow-xl min-w-[220px] select-none space-y-2">
      <Handle type="target" position={Position.Top} className="!bg-cyan-400 !w-3 !h-3" />
      
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-cyan-500/10 text-cyan-400">
            <Layers className="w-4 h-4" />
          </div>
          <span className="text-xs font-bold text-white truncate max-w-[130px]">{label}</span>
        </div>
        <span className="px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 text-[10px] font-mono border border-cyan-500/20">
          Aggregator
        </span>
      </div>

      <p className="text-[11px] text-zinc-400 line-clamp-1">
        Post-flight PII & Toxicity Guard
      </p>

      <Handle type="source" position={Position.Bottom} className="!bg-cyan-400 !w-3 !h-3" />
    </div>
  );
});

SynthesisNode.displayName = "SynthesisNode";
