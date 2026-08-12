import React from "react";
import {
  Bot,
  Database,
  Award,
  Wrench,
  GitBranch,
  Split,
  FileCode,
  Globe,
  Sparkles,
  Layers,
  Flag,
  Trash2,
  AlertCircle,
  CheckCircle2,
  Play,
  Zap,
} from "lucide-react";

export interface NodePort {
  id: string;
  label: string;
  type: "input" | "output";
  kind?: "data" | "true" | "false" | "error" | "route";
}

export interface WorkflowNodeData {
  id: string;
  type: string;
  label: string;
  category?: string;
  data: Record<string, any>;
  position: { x: number; y: number };
  ports?: {
    inputs: NodePort[];
    outputs: NodePort[];
  };
}

interface WorkflowNodeCardProps {
  node: WorkflowNodeData;
  isSelected: boolean;
  onSelect: (nodeId: string) => void;
  onDelete: (nodeId: string) => void;
  onStartConnection: (nodeId: string, portId: string, portType: "output", e: React.MouseEvent) => void;
  onEndConnection: (nodeId: string, portId: string, portType: "input") => void;
  isConnecting?: boolean;
}

export const NODE_CONFIGS: Record<string, { label: string; icon: any; category: string; color: string; border: string; bg: string; description: string }> = {
  // Triggers
  start: { label: "Workflow Input", icon: Play, category: "trigger", color: "text-emerald-400", border: "border-emerald-500/40", bg: "bg-emerald-950/20", description: "Entry point receiving input payload" },
  webhook: { label: "HTTP Webhook", icon: Globe, category: "trigger", color: "text-emerald-400", border: "border-emerald-500/40", bg: "bg-emerald-950/20", description: "External API webhook trigger" },
  WebhookNode: { label: "HTTP Webhook", icon: Globe, category: "trigger", color: "text-emerald-400", border: "border-emerald-500/40", bg: "bg-emerald-950/20", description: "External API webhook trigger" },

  // Hub Integrations
  agent: { label: "Agent Invocation", icon: Bot, category: "hub", color: "text-indigo-400", border: "border-indigo-500/40", bg: "bg-indigo-950/20", description: "Invoke an Agent Hub agent" },
  AgentNode: { label: "Agent Invocation", icon: Bot, category: "hub", color: "text-indigo-400", border: "border-indigo-500/40", bg: "bg-indigo-950/20", description: "Invoke an Agent Hub agent" },
  multi_agent: { label: "Multi-Agent Consensus", icon: Zap, category: "hub", color: "text-indigo-400", border: "border-indigo-500/40", bg: "bg-indigo-950/20", description: "Team consensus across multiple agents" },
  MultiAgentNode: { label: "Multi-Agent Consensus", icon: Zap, category: "hub", color: "text-indigo-400", border: "border-indigo-500/40", bg: "bg-indigo-950/20", description: "Team consensus across multiple agents" },
  retrieval: { label: "Vector Retrieval", icon: Database, category: "hub", color: "text-cyan-400", border: "border-cyan-500/40", bg: "bg-cyan-950/20", description: "Search Ingestion Hub collection" },
  RetrievalNode: { label: "Vector Retrieval", icon: Database, category: "hub", color: "text-cyan-400", border: "border-cyan-500/40", bg: "bg-cyan-950/20", description: "Search Ingestion Hub collection" },
  eval: { label: "Eval Suite", icon: Award, category: "hub", color: "text-purple-400", border: "border-purple-500/40", bg: "bg-purple-950/20", description: "Run evaluation suite in Eval Hub" },
  EvalNode: { label: "Eval Suite", icon: Award, category: "hub", color: "text-purple-400", border: "border-purple-500/40", bg: "bg-purple-950/20", description: "Run evaluation suite in Eval Hub" },
  mcp_tool: { label: "MCP Tool", icon: Wrench, category: "hub", color: "text-amber-400", border: "border-amber-500/40", bg: "bg-amber-950/20", description: "Execute registered MCP server tool" },
  MCPToolNode: { label: "MCP Tool", icon: Wrench, category: "hub", color: "text-amber-400", border: "border-amber-500/40", bg: "bg-amber-950/20", description: "Execute registered MCP server tool" },
  api_call: { label: "API Call", icon: Globe, category: "hub", color: "text-teal-400", border: "border-teal-500/40", bg: "bg-teal-950/20", description: "Make an external HTTP API request" },
  APICallNode: { label: "API Call", icon: Globe, category: "hub", color: "text-teal-400", border: "border-teal-500/40", bg: "bg-teal-950/20", description: "Make an external HTTP API request" },
  database_query: { label: "Database Query", icon: Database, category: "hub", color: "text-emerald-400", border: "border-emerald-500/40", bg: "bg-emerald-950/20", description: "Run a parametrized read-only query against an external database" },
  DatabaseQueryNode: { label: "Database Query", icon: Database, category: "hub", color: "text-emerald-400", border: "border-emerald-500/40", bg: "bg-emerald-950/20", description: "Run a parametrized read-only query against an external database" },
  db_store: { label: "DB Store", icon: Database, category: "hub", color: "text-emerald-400", border: "border-emerald-500/40", bg: "bg-emerald-950/20", description: "Persist a record into an external database" },
  DBStoreNode: { label: "DB Store", icon: Database, category: "hub", color: "text-emerald-400", border: "border-emerald-500/40", bg: "bg-emerald-950/20", description: "Persist a record into an external database" },

  // Classifier
  classifier: { label: "Classifier", icon: GitBranch, category: "logic", color: "text-violet-400", border: "border-violet-500/40", bg: "bg-violet-950/20", description: "Classify input into categories" },
  ClassifierNode: { label: "Classifier", icon: GitBranch, category: "logic", color: "text-violet-400", border: "border-violet-500/40", bg: "bg-violet-950/20", description: "Classify input into categories" },

  // Logic & Control
  if_else: { label: "If / Else Condition", icon: Split, category: "logic", color: "text-amber-400", border: "border-amber-500/40", bg: "bg-amber-950/20", description: "Branch flow based on condition" },
  IfElseNode: { label: "If / Else Condition", icon: Split, category: "logic", color: "text-amber-400", border: "border-amber-500/40", bg: "bg-amber-950/20", description: "Branch flow based on condition" },
  router: { label: "Intent Router", icon: GitBranch, category: "logic", color: "text-amber-400", border: "border-amber-500/40", bg: "bg-amber-950/20", description: "Classify & route to specific sub-flows" },
  RouterNode: { label: "Intent Router", icon: GitBranch, category: "logic", color: "text-amber-400", border: "border-amber-500/40", bg: "bg-amber-950/20", description: "Classify & route to specific sub-flows" },
  gather: { label: "Gather / Merge", icon: Layers, category: "logic", color: "text-amber-400", border: "border-amber-500/40", bg: "bg-amber-950/20", description: "Combine parallel upstream inputs" },
  GatherNode: { label: "Gather / Merge", icon: Layers, category: "logic", color: "text-amber-400", border: "border-amber-500/40", bg: "bg-amber-950/20", description: "Combine parallel upstream inputs" },

  // Transform & Compute
  transform: { label: "Transform JSON", icon: Sparkles, category: "compute", color: "text-sky-400", border: "border-sky-500/40", bg: "bg-sky-950/20", description: "Map & format data payload" },
  TransformNode: { label: "Transform JSON", icon: Sparkles, category: "compute", color: "text-sky-400", border: "border-sky-500/40", bg: "bg-sky-950/20", description: "Map & format data payload" },
  coding: { label: "Code Script", icon: FileCode, category: "compute", color: "text-sky-400", border: "border-sky-500/40", bg: "bg-sky-950/20", description: "Run custom Python script snippet" },
  CodingNode: { label: "Code Script", icon: FileCode, category: "compute", color: "text-sky-400", border: "border-sky-500/40", bg: "bg-sky-950/20", description: "Run custom Python script snippet" },
  synthesis: { label: "LLM Synthesizer", icon: Sparkles, category: "compute", color: "text-sky-400", border: "border-sky-500/40", bg: "bg-sky-950/20", description: "Synthesize answer summary" },
  SynthesisNode: { label: "LLM Synthesizer", icon: Sparkles, category: "compute", color: "text-sky-400", border: "border-sky-500/40", bg: "bg-sky-950/20", description: "Synthesize answer summary" },
  web_search: { label: "Web Search", icon: Globe, category: "compute", color: "text-sky-400", border: "border-sky-500/40", bg: "bg-sky-950/20", description: "Search the web for current information" },
  WebSearchNode: { label: "Web Search", icon: Globe, category: "compute", color: "text-sky-400", border: "border-sky-500/40", bg: "bg-sky-950/20", description: "Search the web for current information" },

  // Output
  action: { label: "Action", icon: Flag, category: "output", color: "text-rose-400", border: "border-rose-500/40", bg: "bg-rose-950/20", description: "Terminal action execution" },
  ActionNode: { label: "Action", icon: Flag, category: "output", color: "text-rose-400", border: "border-rose-500/40", bg: "bg-rose-950/20", description: "Terminal action execution" },
  final_message: { label: "Final Output", icon: Flag, category: "output", color: "text-rose-400", border: "border-rose-500/40", bg: "bg-rose-950/20", description: "Terminal response formatting" },
  FinalMessageNode: { label: "Final Output", icon: Flag, category: "output", color: "text-rose-400", border: "border-rose-500/40", bg: "bg-rose-950/20", description: "Terminal response formatting" },
};

export function getDefaultPortsForType(nodeType: string, dataConfig: Record<string, any> = {}): { inputs: NodePort[]; outputs: NodePort[] } {
  if (nodeType === "start") {
    return { inputs: [], outputs: [{ id: "out", label: "Payload Out", type: "output", kind: "data" }] };
  }
  if (nodeType === "if_else") {
    return {
      inputs: [{ id: "in", label: "Input Data", type: "input", kind: "data" }],
      outputs: [
        { id: "true", label: "True Branch", type: "output", kind: "true" },
        { id: "false", label: "False Branch", type: "output", kind: "false" },
      ],
    };
  }
  if (nodeType === "router") {
    const routes = dataConfig.routes || ["support", "billing", "fallback"];
    return {
      inputs: [{ id: "in", label: "Input Query", type: "input", kind: "data" }],
      outputs: routes.map((r: string) => ({ id: `route_${r}`, label: `Route: ${r}`, type: "output", kind: "route" })),
    };
  }
  if (nodeType === "final_message") {
    return { inputs: [{ id: "in", label: "Result In", type: "input", kind: "data" }], outputs: [] };
  }
  if (nodeType === "gather" || nodeType === "GatherNode") {
    return {
      inputs: [
        { id: "in_multi", label: "Branch 1", type: "input", kind: "data" },
        { id: "in_multi_2", label: "Branch 2", type: "input", kind: "data" },
      ],
      outputs: [{ id: "out", label: "Merged Array", type: "output", kind: "data" }],
    };
  }
  if (nodeType === "database_query" || nodeType === "DatabaseQueryNode") {
    return {
      inputs: [{ id: "in", label: "Params In", type: "input", kind: "data" }],
      outputs: [
        { id: "out", label: "Result Rows", type: "output", kind: "data" },
        { id: "row_count", label: "Row Count", type: "output", kind: "data" },
        { id: "error", label: "On Error", type: "output", kind: "error" },
      ],
    };
  }
  if (nodeType === "db_store" || nodeType === "DBStoreNode") {
    return {
      inputs: [{ id: "in", label: "Record In", type: "input", kind: "data" }],
      outputs: [
        { id: "out", label: "Affected", type: "output", kind: "data" },
        { id: "error", label: "On Error", type: "output", kind: "error" },
      ],
    };
  }

  // Standard nodes (agent, retrieval, eval, transform, coding, web_search, etc.)
  return {
    inputs: [{ id: "in", label: "Input Data", type: "input", kind: "data" }],
    outputs: [
      { id: "out", label: "Output Data", type: "output", kind: "data" },
      { id: "error", label: "On Error", type: "output", kind: "error" },
    ],
  };
}

export function WorkflowNodeCard({
  node,
  isSelected,
  onSelect,
  onDelete,
  onStartConnection,
  onEndConnection,
  isConnecting,
}: WorkflowNodeCardProps) {
  const config = NODE_CONFIGS[node.type] || {
    label: node.label || node.type,
    icon: Layers,
    category: "general",
    color: "text-slate-300",
    border: "border-slate-800",
    bg: "bg-slate-900/60",
    description: "Workflow node",
  };

  const IconComponent = config.icon;
  const ports = node.ports || getDefaultPortsForType(node.type, node.data);

  // Linked resource resolution check
  const isResourceLinked = () => {
    if (node.type === "agent" && !node.data?.agent_id) return false;
    if (node.type === "retrieval" && !node.data?.collection_id) return false;
    if (node.type === "eval" && !node.data?.suite_id) return false;
    return true;
  };

  const resourceOk = isResourceLinked();

  return (
    <div
      onClick={() => onSelect(node.id)}
      style={{ left: `${node.position.x}px`, top: `${node.position.y}px` }}
      className={`absolute w-64 rounded-xl border p-3.5 shadow-xl backdrop-blur-md transition-all group select-none cursor-pointer ${
        isSelected
          ? "bg-slate-900/90 border-indigo-500 ring-2 ring-indigo-500/20 shadow-indigo-500/10 z-30"
          : `${config.bg} ${config.border} hover:border-slate-700 z-10`
      }`}
    >
      {/* Header Bar */}
      <div className="flex items-center justify-between gap-2 border-b border-slate-800/80 pb-2.5 mb-3">
        <div className="flex items-center space-x-2.5 min-w-0">
          <div className={`p-1.5 rounded-lg bg-slate-950/80 border border-slate-800 ${config.color}`}>
            <IconComponent className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <h4 className="text-xs font-bold font-mono text-slate-100 truncate">{node.label}</h4>
            <p className="text-[10px] font-mono text-slate-500 truncate">id: {node.id}</p>
          </div>
        </div>

        <div className="flex items-center space-x-1">
          {!resourceOk && (
            <span title="Missing required Hub resource link!" className="text-amber-400">
              <AlertCircle className="w-3.5 h-3.5" />
            </span>
          )}
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete(node.id);
            }}
            className="p-1 rounded text-slate-500 hover:text-red-400 hover:bg-red-950/40 transition-colors"
            title="Delete node"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Description / Config summary */}
      <div className="text-[11px] text-slate-400 mb-3 space-y-1 bg-slate-950/50 p-2 rounded-lg border border-slate-800/50">
        {node.type === "agent" && (
          <p className="font-mono text-[10px] text-indigo-300 truncate">
            Agent: {node.data?.agent_name || node.data?.agent_id || "Unlinked"}
          </p>
        )}
        {node.type === "retrieval" && (
          <p className="font-mono text-[10px] text-cyan-300 truncate">
            Collection: {node.data?.collection_name || node.data?.collection_id || "Unlinked"}
          </p>
        )}
        {node.type === "eval" && (
          <p className="font-mono text-[10px] text-purple-300 truncate">
            Suite: {node.data?.suite_name || node.data?.suite_id || "Unlinked"}
          </p>
        )}
        {node.type === "if_else" && (
          <p className="font-mono text-[10px] text-amber-300 truncate">
            Cond: {node.data?.condition || "score >= 0.7"}
          </p>
        )}
        {(!["agent", "retrieval", "eval", "if_else"].includes(node.type)) && (
          <p className="text-[10px] text-slate-500 line-clamp-1">{config.description}</p>
        )}
      </div>

      {/* Ports Area */}
      <div className="space-y-2 relative">
        {/* Input Ports (Left) */}
        {ports.inputs.length > 0 && (
          <div className="space-y-1.5">
            {ports.inputs.map((port) => (
              <div key={port.id} className="flex items-center space-x-2 relative group/port">
                <div
                  onMouseUp={() => onEndConnection(node.id, port.id, "input")}
                  className={`w-3.5 h-3.5 rounded-full border border-slate-900 transition-all -ml-5 cursor-pointer hover:scale-125 ${
                    isConnecting ? "bg-indigo-400 ring-4 ring-indigo-500/30 animate-pulse" : "bg-slate-700 hover:bg-indigo-400"
                  }`}
                  title={`Input Port: ${port.label}`}
                />
                <span className="text-[10px] font-mono text-slate-400">{port.label}</span>
              </div>
            ))}
          </div>
        )}

        {/* Output Ports (Right) */}
        {ports.outputs.length > 0 && (
          <div className="space-y-1.5 text-right">
            {ports.outputs.map((port) => {
              const portColor =
                port.kind === "true"
                  ? "bg-emerald-500 hover:bg-emerald-400"
                  : port.kind === "false"
                  ? "bg-amber-500 hover:bg-amber-400"
                  : port.kind === "error"
                  ? "bg-rose-500 hover:bg-rose-400"
                  : "bg-indigo-500 hover:bg-indigo-400";

              return (
                <div key={port.id} className="flex items-center justify-end space-x-2 relative group/port">
                  <span className="text-[10px] font-mono text-slate-400">{port.label}</span>
                  <div
                    onMouseDown={(e) => {
                      e.stopPropagation();
                      onStartConnection(node.id, port.id, "output", e);
                    }}
                    className={`w-3.5 h-3.5 rounded-full border border-slate-900 transition-all -mr-5 cursor-crosshair hover:scale-125 ${portColor}`}
                    title={`Drag connection from ${port.label}`}
                  />
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
