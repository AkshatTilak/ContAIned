import React from "react";
import { X, Sliders } from "lucide-react";
import { useStore } from "../store/useStore";

interface PropertyDrawerProps {
  onClose: () => void;
  availableModels: string[];
}

export const PropertyDrawer: React.FC<PropertyDrawerProps> = ({ onClose, availableModels }) => {
  const activeWorkflow = useStore((state) => state.activeWorkflow);
  const selectedNodeId = useStore((state) => state.selectedNodeId);

  const node = activeWorkflow?.graph_json?.nodes?.find((n) => n.id === selectedNodeId);

  if (!node) return null;

  const nodeType = node.type || "AgentNode";
  const data = node.data || {};

  return (
    <div className="w-80 bg-[#15171e] border-l border-[#26282d] p-5 flex flex-col justify-between shadow-2xl">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-[#26282d]">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-emerald-400" />
            <h3 className="text-sm font-semibold text-white capitalize">{nodeType} Settings</h3>
          </div>
          <button onClick={onClose} className="p-1 rounded text-zinc-400 hover:text-white hover:bg-[#22252c]">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Node Properties */}
        <div className="space-y-4 text-xs">
          <div>
            <label className="text-zinc-400 font-medium block mb-1">Node Identifier</label>
            <input
              type="text"
              readOnly
              value={node.id}
              className="w-full px-3 py-2 rounded bg-[#121316] border border-[#26282d] text-zinc-300 font-mono"
            />
          </div>

          <div>
            <label className="text-zinc-400 font-medium block mb-1">Label / Title</label>
            <input
              type="text"
              defaultValue={data.label || node.id}
              className="w-full px-3 py-2 rounded bg-[#121316] border border-[#26282d] text-white focus:outline-none focus:border-emerald-500"
            />
          </div>

          {nodeType === "AgentNode" && (
            <>
              <div>
                <label className="text-zinc-400 font-medium block mb-1">LLM Model</label>
                <select
                  defaultValue={data.model_id || availableModels[0] || "Arch-Router-1.5B"}
                  className="w-full px-3 py-2 rounded bg-[#121316] border border-[#26282d] text-white focus:outline-none focus:border-emerald-500"
                >
                  {availableModels.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-zinc-400 font-medium block mb-1">Local System Prompt</label>
                <textarea
                  rows={4}
                  defaultValue={data.system_prompt || "You are a specialized agent node."}
                  className="w-full px-3 py-2 rounded bg-[#121316] border border-[#26282d] text-white focus:outline-none focus:border-emerald-500 resize-none font-mono"
                />
              </div>
            </>
          )}

          {nodeType === "ClassifierNode" && (
            <div>
              <label className="text-zinc-400 font-medium block mb-1">Confidence Threshold</label>
              <input
                type="number"
                step="0.05"
                min="0.1"
                max="1.0"
                defaultValue={data.threshold || 0.75}
                className="w-full px-3 py-2 rounded bg-[#121316] border border-[#26282d] text-white"
              />
            </div>
          )}

          {nodeType === "RetrievalNode" && (
            <div>
              <label className="text-zinc-400 font-medium block mb-1">Hybrid Top-K Results</label>
              <input
                type="number"
                defaultValue={data.top_k || 5}
                className="w-full px-3 py-2 rounded bg-[#121316] border border-[#26282d] text-white"
              />
            </div>
          )}
        </div>
      </div>

      <button
        onClick={onClose}
        className="w-full py-2 rounded bg-emerald-500 hover:bg-emerald-600 font-medium text-xs text-white transition-colors"
      >
        Save Node Properties
      </button>
    </div>
  );
};
