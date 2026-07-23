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

  // V5 Fields
  const [conditionType, setConditionType] = useState("complexity_equals");
  const [conditionValue, setConditionValue] = useState("HIGH");
  const [conditionExpression, setConditionExpression] = useState("");
  const [url, setUrl] = useState("https://api.example.com/webhook");
  const [httpMethod, setHttpMethod] = useState("POST");
  const [authType, setAuthType] = useState("none");
  const [authValue, setAuthValue] = useState("");
  const [bodyTemplate, setBodyTemplate] = useState("{\"prompt\": \"{{prompt}}\"}");
  const [suiteName, setSuiteName] = useState("Accuracy Suite");
  const [framework, setFramework] = useState("RAGAS");
  const [serverId, setServerId] = useState("mcp-server-1");
  const [toolName, setToolName] = useState("query_db");
  const [transformMode, setTransformMode] = useState("template");
  const [templateStr, setTemplateStr] = useState("{{prompt}}");

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

      // Load V5 node state
      if (data.condition) {
        setConditionType(data.condition.type || "complexity_equals");
        setConditionValue(data.condition.value || "HIGH");
        setConditionExpression(data.condition.expression || "");
      }
      if (data.url) setUrl(data.url);
      if (data.method) setHttpMethod(data.method);
      if (data.auth_type) setAuthType(data.auth_type);
      if (data.auth_value) setAuthValue(data.auth_value);
      if (data.body_template) setBodyTemplate(data.body_template);
      if (data.suite_name) setSuiteName(data.suite_name);
      if (data.framework) setFramework(data.framework);
      if (data.server_id) setServerId(data.server_id);
      if (data.tool_name) setToolName(data.tool_name);
      if (data.mode) setTransformMode(data.mode);
      if (data.template) setTemplateStr(data.template);
    }
  }, [node, availableModels]);

  if (!node) return null;

  const nodeType = node.type || "AgentNode";

  const handleSave = () => {
    const newData: any = {
      ...node.data,
      label,
      model_id: modelId,
      system_prompt: systemPrompt,
      threshold,
      top_k: topK,
      tools: selectedTools,
      condition: {
        type: conditionType,
        value: conditionValue,
        expression: conditionExpression,
      },
      url,
      method: httpMethod,
      auth_type: authType,
      auth_value: authValue,
      body_template: bodyTemplate,
      suite_name: suiteName,
      framework,
      server_id: serverId,
      tool_name: toolName,
      mode: transformMode,
      template: templateStr,
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
      tools: updated,
    });
  };

  return (
    <div className="w-80 bg-[var(--bg-surface)] border-l border-[var(--border-default)] p-5 flex flex-col justify-between shadow-2xl overflow-y-auto select-none">
      <div className="space-y-6">
        {/* Drawer Header */}
        <div className="flex items-center justify-between pb-4 border-b border-[var(--border-default)]">
          <div className="flex items-center gap-2 overflow-hidden">
            <Sliders className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            <h3 className="text-sm font-semibold text-white truncate capitalize">{nodeType} Settings</h3>
          </div>
          <button onClick={onClose} className="p-1 rounded text-zinc-400 hover:text-white hover:bg-[var(--bg-elevated)] transition-colors flex-shrink-0">
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
              className="w-full px-3 py-2 rounded bg-[var(--bg-input)] border border-[var(--border-default)] text-zinc-300 font-mono truncate"
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
              className="w-full px-3 py-2 rounded bg-[var(--bg-input)] border border-[var(--border-default)] text-white focus:outline-none focus:border-emerald-500"
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
                  className="w-full px-3 py-2 rounded bg-[var(--bg-input)] border border-[var(--border-default)] text-white focus:outline-none focus:border-emerald-500"
                >
                  {availableModels.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-zinc-400 font-medium block mb-1">Local System Prompt</label>
                <textarea
                  rows={3}
                  value={systemPrompt}
                  onChange={(e) => {
                    setSystemPrompt(e.target.value);
                    onUpdateNodeData(node.id, { ...node.data, system_prompt: e.target.value });
                  }}
                  placeholder="Override default prompt for this node..."
                  className="w-full px-3 py-2 rounded bg-[var(--bg-input)] border border-[var(--border-default)] text-white focus:outline-none focus:border-emerald-500 resize-none font-mono text-xs leading-relaxed"
                />
              </div>
            </>
          )}

          {(nodeType === "IfElseNode" || nodeType === "if_else") && (
            <>
              <div>
                <label className="text-zinc-400 font-medium block mb-1">Condition Type</label>
                <select
                  value={conditionType}
                  onChange={(e) => setConditionType(e.target.value)}
                  className="w-full px-3 py-2 rounded bg-[var(--bg-input)] border border-[var(--border-default)] text-white focus:outline-none focus:border-purple-500"
                >
                  <option value="complexity_equals">Complexity Equals</option>
                  <option value="output_contains">Output Contains</option>
                  <option value="metadata_field">State Field Lookup</option>
                  <option value="regex_match">Regex Match</option>
                  <option value="custom_expression">Custom Expression</option>
                </select>
              </div>

              {conditionType === "custom_expression" ? (
                <div>
                  <label className="text-zinc-400 font-medium block mb-1">Sandboxed Expression</label>
                  <input
                    type="text"
                    value={conditionExpression}
                    onChange={(e) => setConditionExpression(e.target.value)}
                    placeholder="complexity == 'HIGH' and token_count > 100"
                    className="w-full px-3 py-2 rounded bg-[var(--bg-input)] border border-[var(--border-default)] text-purple-300 font-mono focus:outline-none focus:border-purple-500"
                  />
                </div>
              ) : (
                <div>
                  <label className="text-zinc-400 font-medium block mb-1">Target Value</label>
                  <input
                    type="text"
                    value={conditionValue}
                    onChange={(e) => setConditionValue(e.target.value)}
                    className="w-full px-3 py-2 rounded bg-[var(--bg-input)] border border-[var(--border-default)] text-white focus:outline-none focus:border-purple-500"
                  />
                </div>
              )}
            </>
          )}

          {(nodeType === "WebhookNode" || nodeType === "webhook" || nodeType === "APICallNode" || nodeType === "api_call") && (
            <>
              <div>
                <label className="text-zinc-400 font-medium block mb-1">Target URL</label>
                <input
                  type="text"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  className="w-full px-3 py-2 rounded bg-[var(--bg-input)] border border-[var(--border-default)] text-cyan-300 font-mono focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="text-zinc-400 font-medium block mb-1">HTTP Method</label>
                <select
                  value={httpMethod}
                  onChange={(e) => setHttpMethod(e.target.value)}
                  className="w-full px-3 py-2 rounded bg-[var(--bg-input)] border border-[var(--border-default)] text-white focus:outline-none focus:border-cyan-500"
                >
                  <option value="GET">GET</option>
                  <option value="POST">POST</option>
                  <option value="PUT">PUT</option>
                  <option value="PATCH">PATCH</option>
                  <option value="DELETE">DELETE</option>
                </select>
              </div>

              <div>
                <label className="text-zinc-400 font-medium block mb-1">Authentication</label>
                <select
                  value={authType}
                  onChange={(e) => setAuthType(e.target.value)}
                  className="w-full px-3 py-2 rounded bg-[var(--bg-input)] border border-[var(--border-default)] text-white focus:outline-none focus:border-cyan-500"
                >
                  <option value="none">None</option>
                  <option value="bearer">Bearer Token</option>
                  <option value="api_key">API Key Header</option>
                </select>
              </div>

              {authType !== "none" && (
                <div>
                  <label className="text-zinc-400 font-medium block mb-1">Auth Secret / Token</label>
                  <input
                    type="password"
                    value={authValue}
                    onChange={(e) => setAuthValue(e.target.value)}
                    className="w-full px-3 py-2 rounded bg-[var(--bg-input)] border border-[var(--border-default)] text-white focus:outline-none focus:border-cyan-500"
                  />
                </div>
              )}
            </>
          )}

          {(nodeType === "EvalNode" || nodeType === "eval") && (
            <>
              <div>
                <label className="text-zinc-400 font-medium block mb-1">Evaluation Suite</label>
                <input
                  type="text"
                  value={suiteName}
                  onChange={(e) => setSuiteName(e.target.value)}
                  className="w-full px-3 py-2 rounded bg-[var(--bg-input)] border border-[var(--border-default)] text-emerald-300 focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="text-zinc-400 font-medium block mb-1">Framework</label>
                <select
                  value={framework}
                  onChange={(e) => setFramework(e.target.value)}
                  className="w-full px-3 py-2 rounded bg-[var(--bg-input)] border border-[var(--border-default)] text-white focus:outline-none focus:border-emerald-500"
                >
                  <option value="RAGAS">RAGAS</option>
                  <option value="DeepEval">DeepEval</option>
                  <option value="Heuristic">Heuristic Sandbox</option>
                </select>
              </div>

              <div>
                <div className="flex items-center justify-between text-zinc-400 font-medium mb-1">
                  <span>Pass Threshold</span>
                  <span className="font-mono text-emerald-400">{threshold}</span>
                </div>
                <input
                  type="range"
                  min="0.1"
                  max="1.0"
                  step="0.05"
                  value={threshold}
                  onChange={(e) => setThreshold(Number(e.target.value))}
                  className="w-full accent-emerald-500"
                />
              </div>
            </>
          )}

          {(nodeType === "MCPToolNode" || nodeType === "mcp_tool") && (
            <>
              <div>
                <label className="text-zinc-400 font-medium block mb-1">MCP Server ID</label>
                <input
                  type="text"
                  value={serverId}
                  onChange={(e) => setServerId(e.target.value)}
                  className="w-full px-3 py-2 rounded bg-[var(--bg-input)] border border-[var(--border-default)] text-orange-300 font-mono focus:outline-none focus:border-orange-500"
                />
              </div>

              <div>
                <label className="text-zinc-400 font-medium block mb-1">Tool Name</label>
                <input
                  type="text"
                  value={toolName}
                  onChange={(e) => setToolName(e.target.value)}
                  className="w-full px-3 py-2 rounded bg-[var(--bg-input)] border border-[var(--border-default)] text-white font-mono focus:outline-none focus:border-orange-500"
                />
              </div>
            </>
          )}

          {(nodeType === "TransformNode" || nodeType === "transform") && (
            <>
              <div>
                <label className="text-zinc-400 font-medium block mb-1">Transform Mode</label>
                <select
                  value={transformMode}
                  onChange={(e) => setTransformMode(e.target.value)}
                  className="w-full px-3 py-2 rounded bg-[var(--bg-input)] border border-[var(--border-default)] text-white focus:outline-none focus:border-yellow-500"
                >
                  <option value="template">Jinja2 Sandboxed Template</option>
                  <option value="extract_field">Extract Field</option>
                  <option value="merge">Merge Dicts</option>
                  <option value="format_json">Format JSON</option>
                </select>
              </div>

              {transformMode === "template" && (
                <div>
                  <label className="text-zinc-400 font-medium block mb-1">Jinja2 Template</label>
                  <textarea
                    rows={3}
                    value={templateStr}
                    onChange={(e) => setTemplateStr(e.target.value)}
                    className="w-full px-3 py-2 rounded bg-[var(--bg-input)] border border-[var(--border-default)] text-yellow-300 font-mono focus:outline-none focus:border-yellow-500 resize-none text-xs"
                  />
                </div>
              )}
            </>
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
