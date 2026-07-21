import React, { useState, useEffect } from "react";
import { X, Sliders, Check } from "lucide-react";
import { useStore } from "../store/useStore";

interface PropertyDrawerProps {
  onClose: () => void;
  availableModels: string[];
  onUpdateNodeData: (nodeId: string, newData: any) => void;
}

export const PropertyDrawer: React.FC<PropertyDrawerProps> = ({
  onClose,
  availableModels,
  onUpdateNodeData,
}) => {
  const activeWorkflow = useStore((state) => state.activeWorkflow);
  const selectedNodeId = useStore((state) => state.selectedNodeId);

  const node = activeWorkflow?.graph_json?.nodes?.find((n) => n.id === selectedNodeId);

  const [label, setLabel] = useState("");
  const [modelId, setModelId] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [threshold, setThreshold] = useState(0.75);
  const [topK, setTopK] = useState(5);
  const [selectedTools, setSelectedTools] = useState<string[]>(["retrieval"]);

  const availableTools = [
    { id: "retrieval", label: "SyntraFlow Hybrid Retrieval" },
    { id: "web_search", label: "Web Search Tool" },
    { id: "code_sandbox", label: "Code Execution Sandbox" },
  ];

  useEffect(() => {
    if (node) {
      const data = node.data || {};
      setLabel(data.label || node.id);
      setModelId(data.model_id || availableModels[0] || "Arch-Router-1.5B");
      setSystemPrompt(data.system_prompt || "");
      setThreshold(data.threshold ?? 0.75);
      setTopK(data.top_k ?? 5);
      setSelectedTools(data.tools || ["retrieval"]);
    }
  }, [node, availableModels]);

  if (!node) return null;

  const nodeType = node.type || "AgentNode";

  const handleSave = () => {
    const newData: any = {
      label,
      model_id: modelId,
      system_prompt: systemPrompt,
      threshold,
      top_k: topK,
      tools: selectedTools,
    };
    onUpdateNodeData(node.id, newData);
    onClose();
  };

  const toggleTool = (toolId: string) => {
    const updated = selectedTools.includes(toolId)
      ? selectedTools.filter((t) => t !== toolId)
      : [...selectedTools, toolId];
    setSelectedTools(updated);
    onUpdateNodeData(node.id, {
      ...node.data,
      label,
      model_id: modelId,
      system_prompt: systemPrompt,
      threshold,
      top_k: topK,
      tools: updated,
    });
  };

  return (
    <div className="w-80 bg-[#15171e] border-l border-[#26282d] p-5 flex flex-col justify-between shadow-2xl overflow-y-auto select-none">
      <div className="space-y-6">
        {/* Drawer Header */}
        <div className="flex items-center justify-between pb-4 border-b border-[#26282d]">
          <div className="flex items-center gap-2 overflow-hidden">
            <Sliders className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            <h3 className="text-sm font-semibold text-white truncate capitalize">{nodeType} Settings</h3>
          </div>
          <button onClick={onClose} className="p-1 rounded text-zinc-400 hover:text-white hover:bg-[#22252c] transition-colors flex-shrink-0">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Node Properties Form */}
        <div className="space-y-4 text-xs">
          <div>
            <label className="text-zinc-400 font-medium block mb-1">Node Identifier</label>
            <input
              type="text"
              readOnly
              value={node.id}
              className="w-full px-3 py-2 rounded bg-[#121316] border border-[#26282d] text-zinc-300 font-mono truncate"
            />
          </div>

          <div>
            <label className="text-zinc-400 font-medium block mb-1">Label / Title</label>
            <input
              type="text"
              value={label}
              onChange={(e) => {
                setLabel(e.target.value);
                onUpdateNodeData(node.id, { ...node.data, label: e.target.value });
              }}
              className="w-full px-3 py-2 rounded bg-[#121316] border border-[#26282d] text-white focus:outline-none focus:border-emerald-500"
            />
          </div>

          {nodeType === "AgentNode" && (
            <>
              <div>
                <label className="text-zinc-400 font-medium block mb-1">LLM Model</label>
                <select
                  value={modelId}
                  onChange={(e) => {
                    setModelId(e.target.value);
                    onUpdateNodeData(node.id, { ...node.data, model_id: e.target.value });
                  }}
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
                  value={systemPrompt}
                  onChange={(e) => {
                    setSystemPrompt(e.target.value);
                    onUpdateNodeData(node.id, { ...node.data, system_prompt: e.target.value });
                  }}
                  placeholder="Override default prompt for this node..."
                  className="w-full px-3 py-2 rounded bg-[#121316] border border-[#26282d] text-white focus:outline-none focus:border-emerald-500 resize-none font-mono text-xs leading-relaxed"
                />
              </div>

              <div>
                <label className="text-zinc-400 font-medium block mb-1">Tool Authorizations</label>
                <div className="space-y-1.5">
                  {availableTools.map((t) => (
                    <button
                      type="button"
                      key={t.id}
                      onClick={() => toggleTool(t.id)}
                      className={`w-full flex items-center justify-between px-3 py-2 rounded border text-left text-[11px] transition-colors ${
                        selectedTools.includes(t.id)
                          ? "bg-amber-500/10 border-amber-500/30 text-amber-400"
                          : "bg-[#121316] border-[#26282d] text-zinc-400"
                      }`}
                    >
                      <span className="truncate">{t.label}</span>
                      {selectedTools.includes(t.id) && <Check className="w-3.5 h-3.5 flex-shrink-0" />}
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}

          {nodeType === "ClassifierNode" && (
            <div>
              <div className="flex items-center justify-between text-zinc-400 font-medium mb-1">
                <span>Confidence Threshold</span>
                <span className="font-mono text-emerald-400">{(threshold * 100).toFixed(0)}%</span>
              </div>
              <input
                type="range"
                min="0.1"
                max="1.0"
                step="0.05"
                value={threshold}
                onChange={(e) => {
                  const val = Number(e.target.value);
                  setThreshold(val);
                  onUpdateNodeData(node.id, { ...node.data, threshold: val });
                }}
                className="w-full accent-emerald-500"
              />
            </div>
          )}

          {nodeType === "RetrievalNode" && (
            <div>
              <div className="flex items-center justify-between text-zinc-400 font-medium mb-1">
                <span>Hybrid Top-K Limit</span>
                <span className="font-mono text-indigo-400">{topK}</span>
              </div>
              <input
                type="range"
                min="1"
                max="20"
                step="1"
                value={topK}
                onChange={(e) => {
                  const val = Number(e.target.value);
                  setTopK(val);
                  onUpdateNodeData(node.id, { ...node.data, top_k: val });
                }}
                className="w-full accent-indigo-500"
              />
            </div>
          )}
        </div>
      </div>

      <button
        onClick={handleSave}
        className="w-full py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 font-medium text-xs text-white shadow-lg shadow-emerald-500/20 transition-colors mt-6"
      >
        Save & Close Drawer
      </button>
    </div>
  );
};
