import React, { useState, useMemo } from "react";
import {
  ReactFlow,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  type NodeTypes,
  type Node,
  type Connection,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Save, Plus } from "lucide-react";

import { useStore } from "../store/useStore";
import { PropertyDrawer } from "./PropertyDrawer";
import { ClassifierNode } from "./nodes/ClassifierNode";
import { AgentNode } from "./nodes/AgentNode";
import { RetrievalNode } from "./nodes/RetrievalNode";
import { SynthesisNode } from "./nodes/SynthesisNode";
import { api } from "../services/api";

const initialNodes = [
  {
    id: "classify",
    type: "ClassifierNode",
    data: { label: "Task Classifier (Arch-Router)", threshold: 0.75 },
    position: { x: 250, y: 50 },
  },
  {
    id: "retrieval",
    type: "RetrievalNode",
    data: { label: "SyntraFlow Hybrid Retrieval", top_k: 5 },
    position: { x: 100, y: 180 },
  },
  {
    id: "coding",
    type: "AgentNode",
    data: { label: "Coding Subagent Node", model_id: "Arch-Router-1.5B", tools: ["retrieval", "code_sandbox"] },
    position: { x: 400, y: 180 },
  },
  {
    id: "synthesis",
    type: "SynthesisNode",
    data: { label: "Gather & Synthesis Node" },
    position: { x: 250, y: 310 },
  },
];

const initialEdges = [
  { id: "e1", source: "classify", target: "retrieval", animated: true, style: { stroke: "#10b981", strokeWidth: 2 } },
  { id: "e2", source: "classify", target: "coding", animated: true, style: { stroke: "#10b981", strokeWidth: 2 } },
  { id: "e3", source: "retrieval", target: "synthesis", style: { stroke: "#6366f1", strokeWidth: 2 } },
  { id: "e4", source: "coding", target: "synthesis", style: { stroke: "#f59e0b", strokeWidth: 2 } },
];

export const WorkflowCanvas: React.FC = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes as any);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges as any);
  const [workflowName, setWorkflowName] = useState("Scatter-Gather Orchestrator");
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  const drawerOpen = useStore((state) => state.drawerOpen);
  const setSelectedNodeId = useStore((state) => state.setSelectedNodeId);
  const setDrawerOpen = useStore((state) => state.setDrawerOpen);
  const setActiveWorkflow = useStore((state) => state.setActiveWorkflow);

  const nodeTypes: NodeTypes = useMemo(() => ({
    ClassifierNode,
    AgentNode,
    RetrievalNode,
    SynthesisNode,
  }), []);

  const onConnect = (params: Connection) => setEdges((eds) => addEdge({ ...params, animated: true, style: { stroke: "#10b981", strokeWidth: 2 } }, eds));

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
      is_active: true
    });
  };

  const handleUpdateNodeData = (nodeId: string, newData: Record<string, any>) => {
    setNodes((nds) =>
      nds.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, ...newData } } : n))
    );
    setActiveWorkflow({
      id: "wf_current",
      name: workflowName,
      graph_json: formatGraphJson(),
      is_active: true
    });
  };

  const handleSaveWorkflow = async () => {
    try {
      setStatusMsg("Validating & saving workflow topology to Postgres...");
      const graph_json = formatGraphJson();
      const saved = await api.createWorkflow({
        name: workflowName,
        graph_json,
        is_active: true
      });
      await api.activateWorkflow(saved.id);
      setStatusMsg(`Workflow '${saved.name}' activated successfully!`);
      setTimeout(() => setStatusMsg(null), 4000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error occurred";
      setStatusMsg(`Failed to save: ${msg}`);
    }
  };

  const addNode = (type: string, label: string) => {
    const newId = `node_${Date.now()}`;
    const newNode = {
      id: newId,
      type,
      data: { label, threshold: 0.75, top_k: 5, model_id: "Arch-Router-1.5B", tools: ["retrieval"] },
      position: { x: 200 + Math.random() * 100, y: 150 + Math.random() * 100 },
    };
    setNodes((nds) => [...nds, newNode]);
  };

  return (
    <div className="flex h-[calc(100vh-6rem)] rounded-xl border border-[#26282d] bg-[#121316] overflow-hidden select-none">
      {/* Canvas Area */}
      <div className="flex-1 flex flex-col">
        {/* Top Control Bar */}
        <div className="flex items-center justify-between px-4 py-3 bg-[#15171e] border-b border-[#26282d]">
          <div className="flex items-center gap-3">
            <input
              type="text"
              value={workflowName}
              onChange={(e) => setWorkflowName(e.target.value)}
              className="bg-transparent text-sm font-semibold text-white focus:outline-none focus:border-b border-emerald-500"
            />
            {statusMsg && <span className="text-xs text-emerald-400 font-medium">{statusMsg}</span>}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => addNode("ClassifierNode", "Classifier Router")}
              className="px-2.5 py-1.5 rounded bg-[#1f2128] hover:bg-[#282b34] text-xs font-medium text-zinc-300 flex items-center gap-1 transition-colors"
            >
              <Plus className="w-3.5 h-3.5 text-emerald-400" /> + Classifier
            </button>

            <button
              onClick={() => addNode("AgentNode", "Subagent Node")}
              className="px-2.5 py-1.5 rounded bg-[#1f2128] hover:bg-[#282b34] text-xs font-medium text-zinc-300 flex items-center gap-1 transition-colors"
            >
              <Plus className="w-3.5 h-3.5 text-amber-400" /> + Agent
            </button>

            <button
              onClick={() => addNode("RetrievalNode", "Hybrid Search")}
              className="px-2.5 py-1.5 rounded bg-[#1f2128] hover:bg-[#282b34] text-xs font-medium text-zinc-300 flex items-center gap-1 transition-colors"
            >
              <Plus className="w-3.5 h-3.5 text-indigo-400" /> + Retrieval
            </button>

            <button
              onClick={handleSaveWorkflow}
              className="px-4 py-1.5 rounded bg-emerald-500 hover:bg-emerald-600 font-medium text-xs text-white flex items-center gap-1.5 shadow-lg shadow-emerald-500/20 transition-colors"
            >
              <Save className="w-3.5 h-3.5" /> Save & Activate
            </button>
          </div>
        </div>

        {/* ReactFlow Component */}
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
            <Background color="#26282d" gap={16} />
            <Controls className="!bg-[#181a21] !border-[#26282d] !fill-zinc-300" />
          </ReactFlow>
        </div>
      </div>

      {/* Property Drawer */}
      {drawerOpen && (
        <PropertyDrawer
          onClose={() => setDrawerOpen(false)}
          availableModels={["Arch-Router-1.5B", "FunAudioLLM/SenseVoiceSmall", "THUDM/GLM-OCR", "jinaai/jina-clip-v2"]}
          onUpdateNodeData={handleUpdateNodeData}
        />
      )}
    </div>
  );
};
