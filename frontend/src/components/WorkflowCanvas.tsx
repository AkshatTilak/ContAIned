import React, { useState, useMemo, useEffect, useCallback } from "react";
import {
  ReactFlow,
  Controls,
  Background,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  type NodeTypes,
  type Connection,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Save,
  Download,
  RotateCcw,
  RotateCw,
  Cpu,
  Bot,
  Database,
  Layers,
  FolderOpen,
  Sparkles,
  GitFork,
  Send,
  Network,
  TestTube,
  Wrench,
  Route,
  Sliders,
} from "lucide-react";

import { useStore } from "../store/useStore";
import { PropertyDrawer } from "./PropertyDrawer";
import { ClassifierNode } from "./nodes/ClassifierNode";
import { AgentNode } from "./nodes/AgentNode";
import { RetrievalNode } from "./nodes/RetrievalNode";
import { SynthesisNode } from "./nodes/SynthesisNode";
import { IfElseNode } from "./nodes/IfElseNode";
import { WebhookNode } from "./nodes/WebhookNode";
import { APICallNode } from "./nodes/APICallNode";
import { EvalNode } from "./nodes/EvalNode";
import { MCPToolNode } from "./nodes/MCPToolNode";
import { RouterNode } from "./nodes/RouterNode";
import { TransformNode } from "./nodes/TransformNode";

import { api } from "../services/api";
import { useToast } from "./shared";
import type { WorkflowResponse } from "../types/api";

const initialNodes = [
  {
    id: "classify",
    type: "ClassifierNode",
    data: { label: "Task Classifier (Arch-Router)", threshold: 0.75, status: "running" },
    position: { x: 280, y: 50 },
  },
  {
    id: "if_else_branch",
    type: "IfElseNode",
    data: { label: "If / Else Complexity Gate", condition: { type: "complexity_equals", value: "HIGH" }, status: "idle" },
    position: { x: 280, y: 180 },
  },
  {
    id: "retrieval",
    type: "RetrievalNode",
    data: { label: "SyntraFlow Hybrid Retrieval", top_k: 5, status: "idle" },
    position: { x: 120, y: 310 },
  },
  {
    id: "coding",
    type: "AgentNode",
    data: { label: "Coding Subagent Node", model_id: "Arch-Router-1.5B", tools: ["retrieval", "code_sandbox"], status: "idle" },
    position: { x: 440, y: 310 },
  },
  {
    id: "synthesis",
    type: "SynthesisNode",
    data: { label: "Gather & Synthesis Node", status: "idle" },
    position: { x: 280, y: 460 },
  },
];

const initialEdges = [
  {
    id: "e1",
    source: "classify",
    target: "if_else_branch",
    animated: true,
    label: "evaluate intent",
    labelStyle: { fill: "#10b981", fontSize: 10, fontFamily: "monospace" },
    labelBgStyle: { fill: "#14151a", fillOpacity: 0.8 },
    style: { stroke: "#10b981", strokeWidth: 2 },
  },
  {
    id: "e2",
    source: "if_else_branch",
    sourceHandle: "false",
    target: "retrieval",
    animated: true,
    label: "standard task",
    labelStyle: { fill: "#a855f7", fontSize: 10, fontFamily: "monospace" },
    labelBgStyle: { fill: "#14151a", fillOpacity: 0.8 },
    style: { stroke: "#a855f7", strokeWidth: 2 },
  },
  {
    id: "e3",
    source: "if_else_branch",
    sourceHandle: "true",
    target: "coding",
    animated: true,
    label: "high complexity",
    labelStyle: { fill: "#f59e0b", fontSize: 10, fontFamily: "monospace" },
    labelBgStyle: { fill: "#14151a", fillOpacity: 0.8 },
    style: { stroke: "#f59e0b", strokeWidth: 2 },
  },
  {
    id: "e4",
    source: "retrieval",
    target: "synthesis",
    label: "context vector",
    labelStyle: { fill: "#6366f1", fontSize: 10, fontFamily: "monospace" },
    labelBgStyle: { fill: "#14151a", fillOpacity: 0.8 },
    style: { stroke: "#6366f1", strokeWidth: 2 },
  },
  {
    id: "e5",
    source: "coding",
    target: "synthesis",
    label: "code artifact",
    labelStyle: { fill: "#f59e0b", fontSize: 10, fontFamily: "monospace" },
    labelBgStyle: { fill: "#14151a", fillOpacity: 0.8 },
    style: { stroke: "#f59e0b", strokeWidth: 2 },
  },
];

export const WorkflowCanvas: React.FC = () => {
  const toast = useToast();
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes as any);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges as any);
  const [workflowName, setWorkflowName] = useState("Scatter-Gather V5 Workflow");
  const [savedWorkflows, setSavedWorkflows] = useState<WorkflowResponse[]>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string>("");

  // Undo/Redo stack
  const [history, setHistory] = useState<{ nodes: any[]; edges: any[] }[]>([]);
  const [redoStack, setRedoStack] = useState<{ nodes: any[]; edges: any[] }[]>([]);

  const drawerOpen = useStore((state) => state.drawerOpen);
  const setSelectedNodeId = useStore((state) => state.setSelectedNodeId);
  const setDrawerOpen = useStore((state) => state.setDrawerOpen);
  const setActiveWorkflow = useStore((state) => state.setActiveWorkflow);

  const nodeTypes: NodeTypes = useMemo(
    () => ({
      ClassifierNode,
      AgentNode,
      RetrievalNode,
      SynthesisNode,
      IfElseNode,
      WebhookNode,
      APICallNode,
      EvalNode,
      MCPToolNode,
      RouterNode,
      TransformNode,
      // Alias mapping
      classifier: ClassifierNode,
      agent: AgentNode,
      retrieval: RetrievalNode,
      synthesis: SynthesisNode,
      if_else: IfElseNode,
      webhook: WebhookNode,
      api_call: APICallNode,
      eval: EvalNode,
      mcp_tool: MCPToolNode,
      router: RouterNode,
      transform: TransformNode,
    }),
    []
  );

  // Load saved workflows on mount
  useEffect(() => {
    loadWorkflows();
  }, []);

  const loadWorkflows = async () => {
    try {
      const list = await api.getWorkflows();
      setSavedWorkflows(list);
    } catch {
      // ignore fetch error if backend offline
    }
  };

  const pushStateToHistory = useCallback(() => {
    setHistory((prev) => [...prev.slice(-19), { nodes, edges }]);
    setRedoStack([]);
  }, [nodes, edges]);

  // Undo/Redo keyboard handlers
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "z") {
        if (e.shiftKey) {
          handleRedo();
        } else {
          handleUndo();
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [history, redoStack, nodes, edges]);

  const handleUndo = () => {
    if (history.length === 0) return;
    const last = history[history.length - 1];
    setRedoStack((prev) => [{ nodes, edges }, ...prev]);
    setNodes(last.nodes);
    setEdges(last.edges);
    setHistory((prev) => prev.slice(0, -1));
    toast.info("Undo Action", "Restored previous canvas state.");
  };

  const handleRedo = () => {
    if (redoStack.length === 0) return;
    const next = redoStack[0];
    setHistory((prev) => [...prev, { nodes, edges }]);
    setNodes(next.nodes);
    setEdges(next.edges);
    setRedoStack((prev) => prev.slice(1));
    toast.info("Redo Action", "Re-applied canvas state.");
  };

  const onConnect = (params: Connection) => {
    pushStateToHistory();
    setEdges((eds) =>
      addEdge(
        {
          ...params,
          animated: true,
          label: "data flow",
          labelStyle: { fill: "#10b981", fontSize: 10, fontFamily: "monospace" },
          labelBgStyle: { fill: "#14151a", fillOpacity: 0.8 },
          style: { stroke: "#10b981", strokeWidth: 2 },
        },
        eds
      )
    );
  };

  const handleNodeClick = (_: React.MouseEvent, node: Node) => {
    setSelectedNodeId(node.id);
    setActiveWorkflow({
      id: "current",
      name: workflowName,
      description: "Visual topology",
      graph_json: formatGraphJson(),
      created_at: new Date().toISOString(),
    });
    setDrawerOpen(true);
  };

  const handleUpdateNodeData = (nodeId: string, newData: any) => {
    pushStateToHistory();
    setNodes((nds) =>
      nds.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, ...newData } } : n))
    );
  };

  const formatGraphJson = (): { nodes: any[]; edges: any[] } => {
    return {
      nodes: nodes.map((n) => ({
        id: n.id,
        type: n.type || "custom",
        data: n.data,
        position: n.position,
      })),
      edges: edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: e.sourceHandle,
        targetHandle: e.targetHandle,
        label: e.label,
      })),
    };
  };

  const handleSaveWorkflow = async () => {
    try {
      const graph_json = formatGraphJson();
      const saved = await api.createWorkflow({
        name: workflowName,
        description: "Configured via V5 Workflow Builder Canvas",
        graph_json,
        is_active: true,
      });
      await api.activateWorkflow(saved.id);
      toast.success("Workflow Saved & Activated", `Topology '${saved.name}' is now live.`);
      loadWorkflows();
    } catch (err: any) {
      toast.error("Save Failed", err.message || "Failed to save workflow.");
    }
  };

  const handleExportJson = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(formatGraphJson(), null, 2));
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `${workflowName.toLowerCase().replace(/\s+/g, "_")}_workflow.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
    toast.success("Export Complete", "Downloaded workflow JSON file.");
  };

  const handleSelectSavedWorkflow = (wfId: string) => {
    setSelectedWorkflowId(wfId);
    const found = savedWorkflows.find((w) => w.id === wfId);
    if (found && found.graph_json?.nodes) {
      pushStateToHistory();
      setWorkflowName(found.name);
      setNodes(found.graph_json.nodes);
      if (found.graph_json.edges) setEdges(found.graph_json.edges);
      toast.info("Workflow Loaded", `Loaded '${found.name}' topology.`);
    }
  };

  const addNodeFromPalette = (type: string, label: string, extraData: any = {}) => {
    pushStateToHistory();
    const newId = `node_${Date.now()}`;
    const newNode = {
      id: newId,
      type,
      data: { label, status: "idle", ...extraData },
      position: { x: 220 + Math.random() * 80, y: 150 + Math.random() * 80 },
    };
    setNodes((nds) => [...nds, newNode]);
    toast.info("Node Added", `Created ${label}.`);
  };

  return (
    <div className="flex h-[calc(100vh-6rem)] rounded-xl border border-[var(--border-default)] bg-[var(--bg-input)] overflow-hidden select-none">
      {/* Node Palette Sidebar (Left side) */}
      <div className="w-64 bg-[var(--bg-surface)] border-r border-[var(--border-default)] p-3 flex flex-col justify-between shrink-0 overflow-y-auto">
        <div className="space-y-4">
          <div className="flex items-center gap-2 pb-2 border-b border-[var(--border-subtle)] text-xs font-bold text-white uppercase tracking-wider font-display">
            <Sparkles className="w-4 h-4 text-emerald-400" />
            <span>V5 Node Palette</span>
          </div>

          {/* Core Category */}
          <div>
            <div className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider mb-2">Core Blocks</div>
            <div className="space-y-1.5">
              <button
                onClick={() => addNodeFromPalette("ClassifierNode", "Task Classifier Router", { threshold: 0.75 })}
                className="w-full flex items-center gap-2.5 p-2 rounded-lg bg-[var(--bg-surface-alt)] hover:bg-[var(--bg-elevated)] border border-emerald-500/30 text-left transition-colors group"
              >
                <div className="p-1.5 rounded bg-emerald-500/10 text-emerald-400"><Cpu className="w-3.5 h-3.5" /></div>
                <div><div className="text-xs font-semibold text-white group-hover:text-emerald-300">Classifier</div><div className="text-[9px] text-zinc-400">Intent Routing</div></div>
              </button>

              <button
                onClick={() => addNodeFromPalette("AgentNode", "Subagent Execution", { model_id: "Arch-Router-1.5B", tools: ["retrieval"] })}
                className="w-full flex items-center gap-2.5 p-2 rounded-lg bg-[var(--bg-surface-alt)] hover:bg-[var(--bg-elevated)] border border-amber-500/30 text-left transition-colors group"
              >
                <div className="p-1.5 rounded bg-amber-500/10 text-amber-400"><Bot className="w-3.5 h-3.5" /></div>
                <div><div className="text-xs font-semibold text-white group-hover:text-amber-300">Subagent</div><div className="text-[9px] text-zinc-400">LLM Reasoning</div></div>
              </button>

              <button
                onClick={() => addNodeFromPalette("RetrievalNode", "SyntraFlow Retrieval", { top_k: 5 })}
                className="w-full flex items-center gap-2.5 p-2 rounded-lg bg-[var(--bg-surface-alt)] hover:bg-[var(--bg-elevated)] border border-indigo-500/30 text-left transition-colors group"
              >
                <div className="p-1.5 rounded bg-indigo-500/10 text-indigo-400"><Database className="w-3.5 h-3.5" /></div>
                <div><div className="text-xs font-semibold text-white group-hover:text-indigo-300">Retrieval</div><div className="text-[9px] text-zinc-400">Qdrant Vector Search</div></div>
              </button>

              <button
                onClick={() => addNodeFromPalette("SynthesisNode", "Gather & Synthesis")}
                className="w-full flex items-center gap-2.5 p-2 rounded-lg bg-[var(--bg-surface-alt)] hover:bg-[var(--bg-elevated)] border border-cyan-500/30 text-left transition-colors group"
              >
                <div className="p-1.5 rounded bg-cyan-500/10 text-cyan-400"><Layers className="w-3.5 h-3.5" /></div>
                <div><div className="text-xs font-semibold text-white group-hover:text-cyan-300">Synthesis</div><div className="text-[9px] text-zinc-400">Terminal Aggregator</div></div>
              </button>
            </div>
          </div>

          {/* Logic Category */}
          <div>
            <div className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider mb-2">Logic & Routing</div>
            <div className="space-y-1.5">
              <button
                onClick={() => addNodeFromPalette("IfElseNode", "If / Else Condition", { condition: { type: "complexity_equals", value: "HIGH" } })}
                className="w-full flex items-center gap-2.5 p-2 rounded-lg bg-[var(--bg-surface-alt)] hover:bg-[var(--bg-elevated)] border border-purple-500/30 text-left transition-colors group"
              >
                <div className="p-1.5 rounded bg-purple-500/10 text-purple-400"><GitFork className="w-3.5 h-3.5" /></div>
                <div><div className="text-xs font-semibold text-white group-hover:text-purple-300">IfElse Node</div><div className="text-[9px] text-zinc-400">Conditional Branch</div></div>
              </button>

              <button
                onClick={() => addNodeFromPalette("RouterNode", "Multi-Branch Router", { routes: [{ label: "Route A" }, { label: "Route B" }], default_route: "Default" })}
                className="w-full flex items-center gap-2.5 p-2 rounded-lg bg-[var(--bg-surface-alt)] hover:bg-[var(--bg-elevated)] border border-pink-500/30 text-left transition-colors group"
              >
                <div className="p-1.5 rounded bg-pink-500/10 text-pink-400"><Route className="w-3.5 h-3.5" /></div>
                <div><div className="text-xs font-semibold text-white group-hover:text-pink-300">Router Node</div><div className="text-[9px] text-zinc-400">Multi-way Branching</div></div>
              </button>

              <button
                onClick={() => addNodeFromPalette("TransformNode", "Data Transform", { mode: "template", template: "{{prompt}}" })}
                className="w-full flex items-center gap-2.5 p-2 rounded-lg bg-[var(--bg-surface-alt)] hover:bg-[var(--bg-elevated)] border border-yellow-500/30 text-left transition-colors group"
              >
                <div className="p-1.5 rounded bg-yellow-500/10 text-yellow-400"><Sliders className="w-3.5 h-3.5" /></div>
                <div><div className="text-xs font-semibold text-white group-hover:text-yellow-300">Transform</div><div className="text-[9px] text-zinc-400">Jinja2 & Formatting</div></div>
              </button>
            </div>
          </div>

          {/* Integrations Category */}
          <div>
            <div className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider mb-2">Integrations</div>
            <div className="space-y-1.5">
              <button
                onClick={() => addNodeFromPalette("WebhookNode", "Outbound Webhook", { url: "https://api.example.com/webhook", method: "POST" })}
                className="w-full flex items-center gap-2.5 p-2 rounded-lg bg-[var(--bg-surface-alt)] hover:bg-[var(--bg-elevated)] border border-cyan-500/30 text-left transition-colors group"
              >
                <div className="p-1.5 rounded bg-cyan-500/10 text-cyan-400"><Send className="w-3.5 h-3.5" /></div>
                <div><div className="text-xs font-semibold text-white group-hover:text-cyan-300">Webhook</div><div className="text-[9px] text-zinc-400">HTTP Trigger</div></div>
              </button>

              <button
                onClick={() => addNodeFromPalette("APICallNode", "REST API Call", { url: "https://api.example.com/v1", method: "GET", auth_type: "none" })}
                className="w-full flex items-center gap-2.5 p-2 rounded-lg bg-[var(--bg-surface-alt)] hover:bg-[var(--bg-elevated)] border border-blue-500/30 text-left transition-colors group"
              >
                <div className="p-1.5 rounded bg-blue-500/10 text-blue-400"><Network className="w-3.5 h-3.5" /></div>
                <div><div className="text-xs font-semibold text-white group-hover:text-blue-300">API Call</div><div className="text-[9px] text-zinc-400">REST Client</div></div>
              </button>
            </div>
          </div>

          {/* Evaluation & Tools */}
          <div>
            <div className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider mb-2">Evaluation & Tools</div>
            <div className="space-y-1.5">
              <button
                onClick={() => addNodeFromPalette("EvalNode", "Inline Evaluation", { suite_name: "Accuracy Suite", framework: "RAGAS", threshold: 0.7 })}
                className="w-full flex items-center gap-2.5 p-2 rounded-lg bg-[var(--bg-surface-alt)] hover:bg-[var(--bg-elevated)] border border-emerald-500/30 text-left transition-colors group"
              >
                <div className="p-1.5 rounded bg-emerald-500/10 text-emerald-400"><TestTube className="w-3.5 h-3.5" /></div>
                <div><div className="text-xs font-semibold text-white group-hover:text-emerald-300">Inline Eval</div><div className="text-[9px] text-zinc-400">RAGAS / DeepEval</div></div>
              </button>

              <button
                onClick={() => addNodeFromPalette("MCPToolNode", "MCP Tool", { server_id: "mcp-server-1", tool_name: "query_db" })}
                className="w-full flex items-center gap-2.5 p-2 rounded-lg bg-[var(--bg-surface-alt)] hover:bg-[var(--bg-elevated)] border border-orange-500/30 text-left transition-colors group"
              >
                <div className="p-1.5 rounded bg-orange-500/10 text-orange-400"><Wrench className="w-3.5 h-3.5" /></div>
                <div><div className="text-xs font-semibold text-white group-hover:text-orange-300">MCP Tool</div><div className="text-[9px] text-zinc-400">Server Tool Call</div></div>
              </button>
            </div>
          </div>
        </div>

        {/* Shortcuts Hints */}
        <div className="p-2.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border-subtle)] space-y-1 text-[10px] font-mono text-zinc-400 mt-4">
          <div className="text-zinc-300 font-semibold mb-1 font-sans">Shortcuts</div>
          <div className="flex justify-between"><span>Undo</span><span className="text-emerald-400">Ctrl+Z</span></div>
          <div className="flex justify-between"><span>Redo</span><span className="text-emerald-400">Ctrl+Shift+Z</span></div>
        </div>
      </div>

      {/* Canvas Main Section */}
      <div className="flex-1 flex flex-col">
        {/* Top Control Toolbar */}
        <div className="flex items-center justify-between px-4 py-3 bg-[var(--bg-surface)] border-b border-[var(--border-default)] gap-3">
          <div className="flex items-center gap-3">
            <input
              type="text"
              value={workflowName}
              onChange={(e) => setWorkflowName(e.target.value)}
              className="bg-transparent text-sm font-semibold text-white focus:outline-none focus:border-b border-emerald-500 font-display"
            />

            {/* Saved Workflows Selector */}
            {savedWorkflows.length > 0 && (
              <div className="flex items-center gap-1 bg-[var(--bg-input)] px-2 py-1 rounded-lg border border-[var(--border-subtle)] text-xs">
                <FolderOpen className="w-3.5 h-3.5 text-zinc-400" />
                <select
                  value={selectedWorkflowId}
                  onChange={(e) => handleSelectSavedWorkflow(e.target.value)}
                  className="bg-transparent text-zinc-300 focus:outline-none"
                >
                  <option value="">Load Saved Workflow...</option>
                  {savedWorkflows.map((w) => (
                    <option key={w.id} value={w.id}>{w.name}</option>
                  ))}
                </select>
              </div>
            )}
          </div>

          <div className="flex items-center gap-2">
            {/* Undo / Redo buttons */}
            <button
              onClick={handleUndo}
              disabled={history.length === 0}
              className="p-1.5 rounded bg-[var(--bg-elevated)] hover:bg-[var(--bg-surface-alt)] text-zinc-300 disabled:opacity-40 transition-colors"
              title="Undo (Ctrl+Z)"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
            <button
              onClick={handleRedo}
              disabled={redoStack.length === 0}
              className="p-1.5 rounded bg-[var(--bg-elevated)] hover:bg-[var(--bg-surface-alt)] text-zinc-300 disabled:opacity-40 transition-colors"
              title="Redo (Ctrl+Shift+Z)"
            >
              <RotateCw className="w-4 h-4" />
            </button>

            {/* Export JSON */}
            <button
              onClick={handleExportJson}
              className="px-3 py-1.5 rounded bg-[var(--bg-elevated)] hover:bg-[var(--bg-surface-alt)] text-xs font-medium text-zinc-300 flex items-center gap-1.5 transition-colors border border-[var(--border-subtle)]"
              title="Export Workflow JSON"
            >
              <Download className="w-3.5 h-3.5" /> Export JSON
            </button>

            {/* Save & Activate */}
            <button
              onClick={handleSaveWorkflow}
              className="px-4 py-1.5 rounded bg-emerald-500 hover:bg-emerald-600 font-medium text-xs text-white flex items-center gap-1.5 shadow-lg shadow-emerald-500/20 transition-colors"
            >
              <Save className="w-3.5 h-3.5" /> Save & Activate
            </button>
          </div>
        </div>

        {/* ReactFlow Canvas Area with MiniMap */}
        <div className="flex-1">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={handleNodeClick}
            fitView
          >
            <Background color="var(--border-default)" gap={16} />
            <Controls className="!bg-[var(--bg-surface-alt)] !border-[var(--border-default)] !fill-zinc-300" />
            <MiniMap
              className="!bg-[var(--bg-surface-alt)] !border-[var(--border-default)] rounded-lg overflow-hidden"
              nodeColor={(n) => {
                if (n.type === "ClassifierNode" || n.type === "classifier") return "#10b981";
                if (n.type === "AgentNode" || n.type === "agent") return "#f59e0b";
                if (n.type === "RetrievalNode" || n.type === "retrieval") return "#6366f1";
                if (n.type === "IfElseNode" || n.type === "if_else") return "#a855f7";
                if (n.type === "WebhookNode" || n.type === "webhook") return "#06b6d4";
                if (n.type === "APICallNode" || n.type === "api_call") return "#3b82f6";
                if (n.type === "EvalNode" || n.type === "eval") return "#10b981";
                if (n.type === "MCPToolNode" || n.type === "mcp_tool") return "#f97316";
                if (n.type === "RouterNode" || n.type === "router") return "#ec4899";
                if (n.type === "TransformNode" || n.type === "transform") return "#eab308";
                return "#06b6d4";
              }}
              maskColor="rgba(0, 0, 0, 0.6)"
            />
          </ReactFlow>
        </div>
      </div>

      {/* Property Drawer */}
      {drawerOpen && (
        <PropertyDrawer
          onClose={() => setDrawerOpen(false)}
          availableModels={[
            "Arch-Router-1.5B",
            "FunAudioLLM/SenseVoiceSmall",
            "THUDM/GLM-OCR",
            "jinaai/jina-clip-v2",
          ]}
          onUpdateNodeData={handleUpdateNodeData}
        />
      )}
    </div>
  );
};

export default WorkflowCanvas;
