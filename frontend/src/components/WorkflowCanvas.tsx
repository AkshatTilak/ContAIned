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
  type Node,
  type Connection,
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
} from "lucide-react";

import { useStore } from "../store/useStore";
import { PropertyDrawer } from "./PropertyDrawer";
import { ClassifierNode } from "./nodes/ClassifierNode";
import { AgentNode } from "./nodes/AgentNode";
import { RetrievalNode } from "./nodes/RetrievalNode";
import { SynthesisNode } from "./nodes/SynthesisNode";
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
    id: "retrieval",
    type: "RetrievalNode",
    data: { label: "SyntraFlow Hybrid Retrieval", top_k: 5, status: "idle" },
    position: { x: 120, y: 190 },
  },
  {
    id: "coding",
    type: "AgentNode",
    data: { label: "Coding Subagent Node", model_id: "Arch-Router-1.5B", tools: ["retrieval", "code_sandbox"], status: "idle" },
    position: { x: 420, y: 190 },
  },
  {
    id: "synthesis",
    type: "SynthesisNode",
    data: { label: "Gather & Synthesis Node", status: "idle" },
    position: { x: 280, y: 340 },
  },
];

const initialEdges = [
  {
    id: "e1",
    source: "classify",
    target: "retrieval",
    animated: true,
    label: "confidence >= 0.75",
    labelStyle: { fill: "#10b981", fontSize: 10, fontFamily: "monospace" },
    labelBgStyle: { fill: "#14151a", fillOpacity: 0.8 },
    style: { stroke: "#10b981", strokeWidth: 2 },
  },
  {
    id: "e2",
    source: "classify",
    target: "coding",
    animated: true,
    label: "code task",
    labelStyle: { fill: "#f59e0b", fontSize: 10, fontFamily: "monospace" },
    labelBgStyle: { fill: "#14151a", fillOpacity: 0.8 },
    style: { stroke: "#f59e0b", strokeWidth: 2 },
  },
  {
    id: "e3",
    source: "retrieval",
    target: "synthesis",
    label: "context vector",
    labelStyle: { fill: "#6366f1", fontSize: 10, fontFamily: "monospace" },
    labelBgStyle: { fill: "#14151a", fillOpacity: 0.8 },
    style: { stroke: "#6366f1", strokeWidth: 2 },
  },
  {
    id: "e4",
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
  const [workflowName, setWorkflowName] = useState("Scatter-Gather Orchestrator");
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
      // ignore fetch error if backend not ready
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
          // Redo
          handleRedo();
        } else {
          // Undo
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

  const formatGraphJson = (currentNodes = nodes, currentEdges = edges) => ({
    nodes: currentNodes.map((n) => ({
      id: n.id,
      type: n.type || "AgentNode",
      data: n.data || {},
      position: n.position || { x: 0, y: 0 },
    })),
    edges: currentEdges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      label: typeof e.label === "string" ? e.label : undefined,
    })),
  });

  const handleNodeClick = (_: React.MouseEvent, node: Node) => {
    setSelectedNodeId(node.id);
    setActiveWorkflow({
      id: "wf_current",
      name: workflowName,
      graph_json: formatGraphJson(),
      is_active: true,
    });
  };

  const handleUpdateNodeData = (nodeId: string, newData: Record<string, any>) => {
    pushStateToHistory();
    setNodes((nds) =>
      nds.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, ...newData } } : n))
    );
    setActiveWorkflow({
      id: "wf_current",
      name: workflowName,
      graph_json: formatGraphJson(),
      is_active: true,
    });
  };

  const handleSaveWorkflow = async () => {
    try {
      const graph_json = formatGraphJson();
      const saved = await api.createWorkflow({
        name: workflowName,
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

  const addNodeFromPalette = (type: string, label: string) => {
    pushStateToHistory();
    const newId = `node_${Date.now()}`;
    const newNode = {
      id: newId,
      type,
      data: { label, threshold: 0.75, top_k: 5, model_id: "Arch-Router-1.5B", tools: ["retrieval"], status: "idle" },
      position: { x: 220 + Math.random() * 80, y: 150 + Math.random() * 80 },
    };
    setNodes((nds) => [...nds, newNode]);
    toast.info("Node Added", `Created ${label}.`);
  };

  return (
    <div className="flex h-[calc(100vh-6rem)] rounded-xl border border-[var(--border-default)] bg-[var(--bg-input)] overflow-hidden select-none">
      {/* Node Palette Sidebar (Left side) */}
      <div className="w-56 bg-[var(--bg-surface)] border-r border-[var(--border-default)] p-3 flex flex-col justify-between shrink-0">
        <div>
          <div className="flex items-center gap-2 mb-3 pb-2 border-b border-[var(--border-subtle)] text-xs font-bold text-white uppercase tracking-wider font-display">
            <Sparkles className="w-4 h-4 text-emerald-400" />
            <span>Node Palette</span>
          </div>

          <div className="space-y-2">
            <button
              onClick={() => addNodeFromPalette("ClassifierNode", "Task Classifier Router")}
              className="w-full flex items-center gap-2.5 p-2.5 rounded-lg bg-[var(--bg-surface-alt)] hover:bg-[var(--bg-elevated)] border border-emerald-500/30 text-left transition-colors group"
            >
              <div className="p-1.5 rounded-md bg-emerald-500/10 text-emerald-400">
                <Cpu className="w-4 h-4" />
              </div>
              <div>
                <div className="text-xs font-semibold text-white group-hover:text-emerald-300">Classifier</div>
                <div className="text-[10px] text-zinc-400">Intent Routing Router</div>
              </div>
            </button>

            <button
              onClick={() => addNodeFromPalette("AgentNode", "Custom Subagent Node")}
              className="w-full flex items-center gap-2.5 p-2.5 rounded-lg bg-[var(--bg-surface-alt)] hover:bg-[var(--bg-elevated)] border border-amber-500/30 text-left transition-colors group"
            >
              <div className="p-1.5 rounded-md bg-amber-500/10 text-amber-400">
                <Bot className="w-4 h-4" />
              </div>
              <div>
                <div className="text-xs font-semibold text-white group-hover:text-amber-300">Subagent</div>
                <div className="text-[10px] text-zinc-400">LLM Reasoning Node</div>
              </div>
            </button>

            <button
              onClick={() => addNodeFromPalette("RetrievalNode", "SyntraFlow Hybrid Retrieval")}
              className="w-full flex items-center gap-2.5 p-2.5 rounded-lg bg-[var(--bg-surface-alt)] hover:bg-[var(--bg-elevated)] border border-indigo-500/30 text-left transition-colors group"
            >
              <div className="p-1.5 rounded-md bg-indigo-500/10 text-indigo-400">
                <Database className="w-4 h-4" />
              </div>
              <div>
                <div className="text-xs font-semibold text-white group-hover:text-indigo-300">Retrieval</div>
                <div className="text-[10px] text-zinc-400">Qdrant Vector RAG</div>
              </div>
            </button>

            <button
              onClick={() => addNodeFromPalette("SynthesisNode", "Gather & Synthesis Node")}
              className="w-full flex items-center gap-2.5 p-2.5 rounded-lg bg-[var(--bg-surface-alt)] hover:bg-[var(--bg-elevated)] border border-cyan-500/30 text-left transition-colors group"
            >
              <div className="p-1.5 rounded-md bg-cyan-500/10 text-cyan-400">
                <Layers className="w-4 h-4" />
              </div>
              <div>
                <div className="text-xs font-semibold text-white group-hover:text-cyan-300">Synthesis</div>
                <div className="text-[10px] text-zinc-400">Aggregator & Guard</div>
              </div>
            </button>
          </div>
        </div>

        {/* Shortcuts Hints */}
        <div className="p-2.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border-subtle)] space-y-1 text-[10px] font-mono text-zinc-400">
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
                if (n.type === "ClassifierNode") return "#10b981";
                if (n.type === "AgentNode") return "#f59e0b";
                if (n.type === "RetrievalNode") return "#6366f1";
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

