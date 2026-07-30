import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  GitFork,
  ArrowLeft,
  Save,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Play,
  Layers,
  Plus,
  Trash2,
  Loader2,
  Sparkles,
  Bot,
  Database,
  FileCode,
} from "lucide-react";
import { useHubPermissions } from "../../../hooks/useHubPermissions";
import { api } from "../../../services/api";
import { routes } from "../../../routes";

export function WorkflowEditor() {
  const { hubId, workflowId } = useParams<{ hubId: string; workflowId: string }>();
  const navigate = useNavigate();
  const { can, isArchived } = useHubPermissions();

  const [workflow, setWorkflow] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [nodes, setNodes] = useState<any[]>([]);
  const [edges, setEdges] = useState<any[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const [isDirty, setIsDirty] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"saved" | "dirty" | "saving">("saved");

  const fetchWorkflow = async () => {
    if (!hubId || !workflowId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.workflows.get(hubId, workflowId);
      setWorkflow(data);
      const graph = (data as any).graph_json || { nodes: [], edges: [] };
      setNodes(graph.nodes || []);
      setEdges(graph.edges || []);
      setIsDirty(false);
      setSaveStatus("saved");
    } catch (err: any) {
      setError(err?.message || "Failed to load workflow details");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkflow();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hubId, workflowId]);

  const handleAddNode = (type: string) => {
    const newNode = {
      id: `node_${Date.now()}`,
      type,
      label: `${type.toUpperCase()} Node`,
      data: {},
    };
    setNodes([...nodes, newNode]);
    setIsDirty(true);
    setSaveStatus("dirty");
  };

  const handleDeleteNode = (nodeId: string) => {
    setNodes(nodes.filter((n) => n.id !== nodeId));
    setEdges(edges.filter((e) => e.source !== nodeId && e.target !== nodeId));
    if (selectedNodeId === nodeId) setSelectedNodeId(null);
    setIsDirty(true);
    setSaveStatus("dirty");
  };

  const handleSaveDraft = async () => {
    if (!hubId || !workflowId) return;
    setIsSaving(true);
    setSaveStatus("saving");
    try {
      await api.workflows.update(hubId, workflowId, {
        name: workflow.name,
        graph_json: { nodes, edges },
      } as any);
      setIsDirty(false);
      setSaveStatus("saved");
    } catch (err: any) {
      console.error("Failed to save draft workflow:", err);
      setSaveStatus("dirty");
    } finally {
      setIsSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 text-center space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mx-auto" />
        <p className="text-sm text-slate-400">Loading Workflow canvas...</p>
      </div>
    );
  }

  if (error || !workflow) {
    return (
      <div className="p-8 text-center space-y-4">
        <AlertTriangle className="w-10 h-10 text-red-500 mx-auto" />
        <h3 className="text-base font-bold text-slate-200">Workflow Not Found</h3>
        <p className="text-xs text-slate-400">{error || "Could not load target workflow graph"}</p>
        <button
          onClick={() => navigate(routes.workflowHub.workflows(hubId || ""))}
          className="px-4 py-2 bg-slate-800 text-slate-200 text-xs font-medium rounded-lg hover:bg-slate-700"
        >
          Back to Workflow Library
        </button>
      </div>
    );
  }

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);

  return (
    <div className="space-y-6 pb-12">
      {/* Editor Top Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-4">
        <div className="flex items-center space-x-3">
          <button
            onClick={() => navigate(routes.workflowHub.workflows(hubId || ""))}
            className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
            title="Back to Workflow Library"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-bold font-display text-slate-100">{workflow.name}</h1>
              <span className={`px-2 py-0.5 text-xs font-mono font-semibold uppercase rounded border ${
                saveStatus === "saved"
                  ? "bg-emerald-950/60 text-emerald-400 border-emerald-800/40"
                  : saveStatus === "saving"
                  ? "bg-indigo-950/60 text-indigo-400 border-indigo-800/40"
                  : "bg-amber-950/60 text-amber-400 border-amber-800/40"
              }`}>
                {saveStatus === "saved" ? "Saved • v1 Draft" : saveStatus === "saving" ? "Saving..." : "Unsaved Changes"}
              </span>
            </div>
            <p className="text-xs font-mono text-slate-500 mt-0.5">
              {nodes.length} nodes, {edges.length} connections
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {isDirty && can("edit_resource") && !isArchived && (
            <button
              onClick={handleSaveDraft}
              disabled={isSaving}
              className="flex items-center space-x-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs rounded-xl shadow transition-colors"
            >
              {isSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
              <span>Save Draft</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Canvas Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 h-[600px]">
        {/* Node Palette (Left Column) */}
        <div className="bg-slate-900/50 border border-slate-800/80 rounded-xl p-4 space-y-4 flex flex-col justify-between">
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase font-mono text-slate-400">Add Graph Nodes</h3>
            <div className="space-y-2">
              <button
                onClick={() => handleAddNode("agent")}
                disabled={!can("edit_resource") || isArchived}
                className="w-full p-2.5 bg-slate-950/80 hover:bg-slate-800 border border-slate-800 rounded-xl text-left text-xs font-medium text-slate-200 flex items-center space-x-2 transition-colors disabled:opacity-50"
              >
                <Bot className="w-4 h-4 text-indigo-400" />
                <span>Agent Invocation</span>
              </button>

              <button
                onClick={() => handleAddNode("retrieval")}
                disabled={!can("edit_resource") || isArchived}
                className="w-full p-2.5 bg-slate-950/80 hover:bg-slate-800 border border-slate-800 rounded-xl text-left text-xs font-medium text-slate-200 flex items-center space-x-2 transition-colors disabled:opacity-50"
              >
                <Database className="w-4 h-4 text-emerald-400" />
                <span>Vector Retrieval</span>
              </button>

              <button
                onClick={() => handleAddNode("code")}
                disabled={!can("edit_resource") || isArchived}
                className="w-full p-2.5 bg-slate-950/80 hover:bg-slate-800 border border-slate-800 rounded-xl text-left text-xs font-medium text-slate-200 flex items-center space-x-2 transition-colors disabled:opacity-50"
              >
                <FileCode className="w-4 h-4 text-amber-400" />
                <span>Code Script</span>
              </button>
            </div>
          </div>
        </div>

        {/* Graph Nodes Canvas Surface (Middle 2 Columns) */}
        <div className="lg:col-span-2 bg-slate-950/80 border border-slate-800 rounded-xl p-6 relative overflow-auto custom-scrollbar flex flex-col justify-between">
          <div className="space-y-4">
            <h3 className="text-xs font-bold uppercase font-mono text-slate-400">Execution Graph Nodes ({nodes.length})</h3>

            {nodes.length === 0 ? (
              <div className="p-12 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-xl">
                Canvas empty. Click nodes on the left to build execution graph.
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {nodes.map((node) => {
                  const isSelected = selectedNodeId === node.id;
                  return (
                    <div
                      key={node.id}
                      onClick={() => setSelectedNodeId(node.id)}
                      className={`p-4 rounded-xl border cursor-pointer transition-all space-y-2 ${
                        isSelected
                          ? "bg-indigo-950/40 border-indigo-500 shadow-lg shadow-indigo-500/10"
                          : "bg-slate-900/60 hover:bg-slate-900 border-slate-800"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-100 text-xs font-mono">{node.label}</span>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteNode(node.id);
                          }}
                          className="p-1 rounded text-slate-500 hover:text-red-400 hover:bg-red-950/40"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                      <p className="text-[11px] font-mono text-slate-500">id: {node.id}</p>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Node Properties Drawer (Right Column) */}
        <div className="bg-slate-900/50 border border-slate-800/80 rounded-xl p-4 space-y-4">
          <h3 className="text-xs font-bold uppercase font-mono text-slate-400">Node Properties</h3>

          {selectedNode ? (
            <div className="space-y-4 text-xs">
              <div>
                <label className="block text-[11px] font-semibold text-slate-400 mb-1">Node Label</label>
                <input
                  type="text"
                  value={selectedNode.label}
                  onChange={(e) => {
                    const newLabel = e.target.value;
                    setNodes(nodes.map((n) => (n.id === selectedNode.id ? { ...n, label: newLabel } : n)));
                    setIsDirty(true);
                    setSaveStatus("dirty");
                  }}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-400 mb-1">Node Type</label>
                <span className="px-2 py-1 rounded bg-slate-950 border border-slate-800 text-indigo-400 font-mono font-bold inline-block">
                  {selectedNode.type}
                </span>
              </div>
            </div>
          ) : (
            <p className="text-xs text-slate-500 italic">Select a node on the canvas to edit properties.</p>
          )}
        </div>
      </div>
    </div>
  );
}
