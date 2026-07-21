import React, { useState } from "react";
import {
  ReactFlow,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Save, Plus } from "lucide-react";

import { useStore } from "../store/useStore";
import { PropertyDrawer } from "./PropertyDrawer";
import { api } from "../services/api";

const initialNodes = [
  {
    id: "classify",
    type: "default",
    data: { label: "Task Classifier (Router)" },
    position: { x: 250, y: 50 },
    style: { background: "#181a21", border: "1px solid #10b981", color: "#fff", borderRadius: "8px", padding: "10px" }
  },
  {
    id: "retrieval",
    type: "default",
    data: { label: "SyntraFlow Hybrid Retrieval" },
    position: { x: 100, y: 180 },
    style: { background: "#181a21", border: "1px solid #6366f1", color: "#fff", borderRadius: "8px", padding: "10px" }
  },
  {
    id: "coding",
    type: "default",
    data: { label: "Coding Subagent Node" },
    position: { x: 400, y: 180 },
    style: { background: "#181a21", border: "1px solid #f59e0b", color: "#fff", borderRadius: "8px", padding: "10px" }
  },
  {
    id: "synthesis",
    type: "default",
    data: { label: "Gather & Synthesis Node" },
    position: { x: 250, y: 310 },
    style: { background: "#181a21", border: "1px solid #06b6d4", color: "#fff", borderRadius: "8px", padding: "10px" }
  },
];

const initialEdges = [
  { id: "e1", source: "classify", target: "retrieval", animated: true, style: { stroke: "#10b981" } },
  { id: "e2", source: "classify", target: "coding", animated: true, style: { stroke: "#10b981" } },
  { id: "e3", source: "retrieval", target: "synthesis", style: { stroke: "#6366f1" } },
  { id: "e4", source: "coding", target: "synthesis", style: { stroke: "#f59e0b" } },
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

  const onConnect = (params: any) => setEdges((eds) => addEdge(params, eds));

  const formatGraphJson = () => ({
    nodes: nodes.map((n) => ({
      id: n.id,
      type: n.type || "default",
      data: n.data || {},
      position: n.position || { x: 0, y: 0 },
    })),
    edges: edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      label: typeof e.label === "string" ? e.label : undefined,
    })),
  });

  const handleNodeClick = (_: any, node: any) => {
    setSelectedNodeId(node.id);
    setActiveWorkflow({
      id: "wf_current",
      name: workflowName,
      graph_json: formatGraphJson(),
      is_active: true
    });
  };

  const handleSaveWorkflow = async () => {
    try {
      setStatusMsg("Validating & saving workflow to Postgres...");
      const graph_json = formatGraphJson();
      const saved = await api.createWorkflow({
        name: workflowName,
        graph_json,
        is_active: true
      });
      await api.activateWorkflow(saved.id);
      setStatusMsg(`Workflow '${saved.name}' activated successfully!`);
      setTimeout(() => setStatusMsg(null), 4000);
    } catch (err: any) {
      setStatusMsg(`Failed to save: ${err.message}`);
    }
  };

  const addNode = (_typeStr: string, label: string, border: string) => {
    const newId = `node_${Date.now()}`;
    const newNode = {
      id: newId,
      type: "default",
      data: { label },
      position: { x: 200 + Math.random() * 100, y: 150 + Math.random() * 100 },
      style: { background: "#181a21", border: `1px solid ${border}`, color: "#fff", borderRadius: "8px", padding: "10px" }
    };
    setNodes((nds) => [...nds, newNode]);
  };

  return (
    <div className="flex h-[calc(100vh-6rem)] rounded-xl border border-[#26282d] bg-[#121316] overflow-hidden">
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
              onClick={() => addNode("ClassifierNode", "New Classifier", "#10b981")}
              className="px-2.5 py-1.5 rounded bg-[#1f2128] hover:bg-[#282b34] text-xs font-medium text-zinc-300 flex items-center gap-1"
            >
              <Plus className="w-3.5 h-3.5 text-emerald-400" /> + Classifier
            </button>
            <button
              onClick={() => addNode("AgentNode", "New Agent Node", "#f59e0b")}
              className="px-2.5 py-1.5 rounded bg-[#1f2128] hover:bg-[#282b34] text-xs font-medium text-zinc-300 flex items-center gap-1"
            >
              <Plus className="w-3.5 h-3.5 text-amber-400" /> + Agent
            </button>

            <button
              onClick={handleSaveWorkflow}
              className="px-4 py-1.5 rounded bg-emerald-500 hover:bg-emerald-600 font-medium text-xs text-white flex items-center gap-1.5 shadow-lg shadow-emerald-500/20"
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
        />
      )}
    </div>
  );
};
