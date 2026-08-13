import { useState } from "react";
import { GitFork, Check, Loader2, X, Sparkles } from "lucide-react";
import { api } from "../../../services/api";

export interface CreateWorkflowDialogProps {
  hubId: string;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (workflowId: string, starterGraph?: { nodes: any[]; edges: any[] }) => void;
}

// Starter node templates seeded onto the canvas when a template is chosen.
// These mirror the backend SUPPORTED_NODE_TYPES and the frontend NODE_CONFIGS.
function buildStarterGraph(template: string): { nodes: any[]; edges: any[] } {
  const nodes: any[] = [];
  const edges: any[] = [];
  let seq = 0;
  const nid = (prefix: string) => `${prefix}_${Date.now()}_${seq++}`;

  const addNode = (type: string, label: string, x: number, y: number, data: any = {}, ports?: any) => {
    nodes.push({
      id: nid(type),
      type,
      label,
      data,
      position: { x, y },
      ports: ports || {
        inputs: [{ id: "in", label: "Input Data", type: "input", kind: "data" }],
        outputs: [
          { id: "out", label: "Output Data", type: "output", kind: "data" },
          { id: "error", label: "On Error", type: "output", kind: "error" },
        ],
      },
    });
    return nodes[nodes.length - 1];
  };

  const link = (from: any, fromHandle: string, to: any, toHandle: string) => {
    edges.push({
      id: `edge_${Date.now()}_${seq++}`,
      source: from.id,
      sourceHandle: fromHandle,
      target: to.id,
      targetHandle: toHandle,
    });
  };

  if (template === "rag") {
    const start = addNode("start", "Workflow Input", 60, 120, {}, { inputs: [], outputs: [{ id: "out", label: "Payload Out", type: "output", kind: "data" }] });
    // Vector retrieval is a tool bound to the agent node, not a standalone node.
    const agent = addNode("agent", "Agent Invocation", 380, 120, {
      tools: [{ type: "retrieval", enabled: true, label: "Vector Retrieval" }],
    });
    const finalMsg = addNode("final_message", "Final Output", 700, 120, {}, { inputs: [{ id: "in", label: "Result In", type: "input", kind: "data" }], outputs: [] });
    link(start, "out", agent, "in");
    link(agent, "out", finalMsg, "in");
  } else if (template === "classifier") {
    const start = addNode("start", "Workflow Input", 60, 120, {}, { inputs: [], outputs: [{ id: "out", label: "Payload Out", type: "output", kind: "data" }] });
    const router = addNode("router", "Intent Router", 380, 120, { routes: ["support", "billing", "fallback"] }, {
      inputs: [{ id: "in", label: "Input Query", type: "input", kind: "data" }],
      outputs: [
        { id: "route_support", label: "Route: support", type: "output", kind: "route" },
        { id: "route_billing", label: "Route: billing", type: "output", kind: "route" },
        { id: "route_fallback", label: "Route: fallback", type: "output", kind: "route" },
      ],
    });
    const agent = addNode("agent", "Agent Invocation", 700, 60, {});
    const finalMsg = addNode("final_message", "Final Output", 1020, 120, {}, { inputs: [{ id: "in", label: "Result In", type: "input", kind: "data" }], outputs: [] });
    link(start, "out", router, "in");
    link(router, "route_support", agent, "in");
    link(router, "route_billing", agent, "in");
    link(router, "route_fallback", agent, "in");
    link(agent, "out", finalMsg, "in");
  } else if (template === "multi-agent") {
    const start = addNode("start", "Workflow Input", 60, 160, {}, { inputs: [], outputs: [{ id: "out", label: "Payload Out", type: "output", kind: "data" }] });
    const agent1 = addNode("agent", "Agent Invocation 1", 380, 40, {});
    const agent2 = addNode("agent", "Agent Invocation 2", 380, 200, {});
    const gather = addNode("gather", "Gather / Merge", 700, 120, {}, {
      inputs: [
        { id: "in_multi", label: "Branch 1", type: "input", kind: "data" },
        { id: "in_multi_2", label: "Branch 2", type: "input", kind: "data" },
      ],
      outputs: [{ id: "out", label: "Merged Array", type: "output", kind: "data" }],
    });
    const finalMsg = addNode("final_message", "Final Output", 1020, 120, {}, { inputs: [{ id: "in", label: "Result In", type: "input", kind: "data" }], outputs: [] });
    link(start, "out", agent1, "in");
    link(start, "out", agent2, "in");
    link(agent1, "out", gather, "in_multi");
    link(agent2, "out", gather, "in_multi_2");
    link(gather, "out", finalMsg, "in");
  }

  return { nodes, edges };
}

export function CreateWorkflowDialog({
  hubId,
  isOpen,
  onClose,
  onSuccess,
}: CreateWorkflowDialogProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [template, setTemplate] = useState("blank");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const newWf = await api.workflows.create(hubId, {
        name: name.trim(),
        description,
      });
      const starterGraph = template === "blank" ? undefined : buildStarterGraph(template);
      onSuccess(newWf.id, starterGraph);
    } catch (err: any) {
      setError(err?.message || "Failed to create workflow");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md bg-[#0f1117] border border-slate-800 rounded-2xl p-6 space-y-4 shadow-2xl"
      >
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <h3 className="font-bold text-slate-100 text-base font-display flex items-center space-x-2">
            <GitFork className="w-4 h-4 text-indigo-400" />
            <span>Create New Workflow</span>
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {error && <p className="text-xs text-red-400">{error}</p>}

        <div className="space-y-3">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Workflow Name *</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Customer Support RAG Pipeline"
              required
              className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              placeholder="Describe graph execution flow..."
              className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Starter Template</label>
            <select
              value={template}
              onChange={(e) => setTemplate(e.target.value)}
              className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
            >
              <option value="blank">Blank Canvas (Custom)</option>
              <option value="rag">RAG Q&A Pipeline (Vector + LLM)</option>
              <option value="classifier">Classifier → Agent Router</option>
              <option value="multi-agent">Multi-Agent Fan-Out Orchestration</option>
            </select>
          </div>
        </div>

        <div className="flex justify-end space-x-2 pt-4 border-t border-slate-800">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 bg-slate-800 text-slate-300 text-xs font-medium rounded-xl hover:bg-slate-700"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting || !name.trim()}
            className="px-4 py-2 bg-indigo-600 text-white text-xs font-medium rounded-xl hover:bg-indigo-500 flex items-center space-x-1"
          >
            {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
            <span>Initialize Graph</span>
          </button>
        </div>
      </form>
    </div>
  );
}
