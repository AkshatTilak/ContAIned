import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import { Database } from "lucide-react";

export const RetrievalNode = memo(({ data }: any) => {
  const label = data?.label || "SyntraFlow Retrieval";
  const topK = data?.top_k ?? 5;

  return (
    <div className="px-4 py-3 rounded-xl bg-[var(--bg-surface-alt)] border border-indigo-500/40 shadow-xl min-w-[220px] select-none space-y-2">
      <Handle type="target" position={Position.Top} className="!bg-indigo-400 !w-3 !h-3" />
      
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-400">
            <Database className="w-4 h-4" />
          </div>
          <span className="text-xs font-bold text-white truncate max-w-[130px]">{label}</span>
        </div>
        <span className="px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 text-[10px] font-mono border border-indigo-500/20">
          K={topK}
        </span>
      </div>

      <p className="text-[11px] text-zinc-400 line-clamp-1">
        Hybrid Qdrant + Fulltext Search
      </p>

      <Handle type="source" position={Position.Bottom} className="!bg-indigo-400 !w-3 !h-3" />
    </div>
  );
});

RetrievalNode.displayName = "RetrievalNode";
