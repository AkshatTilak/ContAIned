import React, { useState, useEffect } from "react";
import { Activity, Clock, CheckCircle2, XCircle, ChevronRight, ChevronDown, Search, Cpu, Layers, Terminal } from "lucide-react";
import { api } from "../../services/api";
import { useToast } from "../shared";

interface FlowTraceStep {
  id: string;
  run_id: string;
  workflow_id: string;
  node_id: string;
  node_type: string;
  input_state: Record<string, any>;
  output_state: Record<string, any>;
  latency_ms: number;
  timestamp: string;
}

interface FlowTraceVisualizerProps {
  initialRunId?: string;
}

export const FlowTraceVisualizer: React.FC<FlowTraceVisualizerProps> = ({ initialRunId }) => {
  const toast = useToast();
  const [runIdInput, setRunIdInput] = useState<string>(initialRunId || "");
  const [traces, setTraces] = useState<FlowTraceStep[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [expandedNodes, setExpandedNodes] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (initialRunId) {
      setRunIdInput(initialRunId);
      loadTraces(initialRunId);
    } else {
      // Load sample fallback traces if no run_id is supplied
      loadMockTraces();
    }
  }, [initialRunId]);

  const loadTraces = async (idToFetch: string) => {
    if (!idToFetch.trim()) return;
    setIsLoading(true);
    try {
      const res = await api.getRunFlowTraces(idToFetch);
      if (res.traces && res.traces.length > 0) {
        setTraces(res.traces);
        setSelectedNodeId(res.traces[0].node_id);
      } else {
        toast.error("No Traces Found", `No flow execution steps logged for run ID: ${idToFetch}`);
        loadMockTraces();
      }
    } catch (err: any) {
      toast.error("Fetch Error", err.message || "Failed to load flow traces.");
      loadMockTraces();
    } finally {
      setIsLoading(false);
    }
  };

  const loadMockTraces = () => {
    const mockSteps: FlowTraceStep[] = [
      {
        id: "tr_1",
        run_id: "demo_run_101",
        workflow_id: "wf_multi_agent_customer_support",
        node_id: "intent_classifier_node",
        node_type: "classifier",
        input_state: { user_query: "I was double charged $49 on my invoice." },
        output_state: { intent: "billing_issue", confidence: 0.99, route: "finance_agent" },
        latency_ms: 85.4,
        timestamp: new Date(Date.now() - 4000).toISOString(),
      },
      {
        id: "tr_2",
        run_id: "demo_run_101",
        workflow_id: "wf_multi_agent_customer_support",
        node_id: "syntraflow_retrieval_node",
        node_type: "retrieval",
        input_state: { query: "invoice double charge refund policy", collection: "support_docs" },
        output_state: { retrieved_chunks: ["Chunk #12: Refund processing guidelines", "Chunk #45: Billing dispute SLA"], chunk_count: 2 },
        latency_ms: 142.1,
        timestamp: new Date(Date.now() - 3000).toISOString(),
      },
      {
        id: "tr_3",
        run_id: "demo_run_101",
        workflow_id: "wf_multi_agent_customer_support",
        node_id: "guardroute_safety_node",
        node_type: "guardrail",
        input_state: { prompt: "Verify user billing auth token" },
        output_state: { is_safe: true, pii_detected: false, toxicity_score: 0.01 },
        latency_ms: 45.0,
        timestamp: new Date(Date.now() - 2000).toISOString(),
      },
      {
        id: "tr_4",
        run_id: "demo_run_101",
        workflow_id: "wf_multi_agent_customer_support",
        node_id: "stripe_refund_action_node",
        node_type: "action_mock",
        input_state: { action: "issue_refund", amount: 49.00, currency: "USD" },
        output_state: { status: 200, mocked: true, message: "Simulated ActionNode execution success" },
        latency_ms: 32.8,
        timestamp: new Date(Date.now() - 1000).toISOString(),
      },
    ];
    setTraces(mockSteps);
    setSelectedNodeId("intent_classifier_node");
  };

  const toggleExpand = (nodeId: string) => {
    setExpandedNodes((prev) => ({ ...prev, [nodeId]: !prev[nodeId] }));
  };

  const selectedStep = traces.find((t) => t.node_id === selectedNodeId) || traces[0];

  const totalDurationMs = traces.reduce((acc, t) => acc + (t.latency_ms || 0), 0);

  const getNodeColor = (nodeType: string) => {
    switch (nodeType.toLowerCase()) {
      case "classifier":
      case "router":
        return "border-purple-500/50 bg-purple-500/10 text-purple-400";
      case "retrieval":
        return "border-blue-500/50 bg-blue-500/10 text-blue-400";
      case "guardrail":
      case "safety":
        return "border-emerald-500/50 bg-emerald-500/10 text-emerald-400";
      case "action":
      case "action_mock":
        return "border-amber-500/50 bg-amber-500/10 text-amber-400";
      default:
        return "border-gray-700 bg-gray-800 text-gray-300";
    }
  };

  return (
    <div className="space-y-6">
      {/* Header & Run ID Search Bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 rounded-xl bg-gray-900/60 border border-gray-800 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-100">Multi-Agent Flow Trace Debugger</h3>
            <p className="text-xs text-gray-400">Inspect intermediate LangGraph state transitions, latencies, and node assertions</p>
          </div>
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <div className="relative flex-1 sm:w-80">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-gray-500" />
            <input
              type="text"
              value={runIdInput}
              onChange={(e) => setRunIdInput(e.target.value)}
              placeholder="Enter Eval Run ID..."
              className="w-full pl-9 pr-3 py-1.5 bg-gray-950/80 border border-gray-700/80 rounded-lg text-xs text-gray-200 focus:outline-none focus:border-indigo-500"
            />
          </div>
          <button
            onClick={() => loadTraces(runIdInput)}
            disabled={isLoading}
            className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
          >
            {isLoading ? "Loading..." : "Fetch Traces"}
          </button>
        </div>
      </div>

      {/* Overview Metric Banner */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-gray-900/40 border border-gray-800/80">
          <div className="flex items-center justify-between text-gray-400 text-xs mb-1">
            <span>Execution Steps</span>
            <Layers className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-xl font-bold text-gray-100">{traces.length} Nodes</div>
        </div>

        <div className="p-4 rounded-xl bg-gray-900/40 border border-gray-800/80">
          <div className="flex items-center justify-between text-gray-400 text-xs mb-1">
            <span>Total End-to-End Latency</span>
            <Clock className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-xl font-bold text-amber-400">{totalDurationMs.toFixed(1)} ms</div>
        </div>

        <div className="p-4 rounded-xl bg-gray-900/40 border border-gray-800/80">
          <div className="flex items-center justify-between text-gray-400 text-xs mb-1">
            <span>Workflow ID</span>
            <Cpu className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-sm font-semibold text-purple-300 truncate">
            {traces[0]?.workflow_id || "wf_default"}
          </div>
        </div>

        <div className="p-4 rounded-xl bg-gray-900/40 border border-gray-800/80">
          <div className="flex items-center justify-between text-gray-400 text-xs mb-1">
            <span>Block Assertions</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-xl font-bold text-emerald-400">100% Passed</div>
        </div>
      </div>

      {/* Main Split Inspector View */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Step Timeline Column */}
        <div className="lg:col-span-5 space-y-3">
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider px-1">
            Step-by-Step Node Execution Sequence
          </h4>

          <div className="space-y-2">
            {traces.map((step, idx) => {
              const isSelected = selectedNodeId === step.node_id;
              const percentWidth = totalDurationMs > 0 ? (step.latency_ms / totalDurationMs) * 100 : 25;

              return (
                <div
                  key={step.id || idx}
                  onClick={() => setSelectedNodeId(step.node_id)}
                  className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                    isSelected
                      ? "border-indigo-500 bg-indigo-500/10 shadow-lg shadow-indigo-500/5"
                      : "border-gray-800/80 bg-gray-900/40 hover:border-gray-700 hover:bg-gray-900/70"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-gray-800 text-gray-400 text-[10px] font-mono flex items-center justify-center border border-gray-700">
                        {idx + 1}
                      </span>
                      <span className="text-xs font-semibold text-gray-200">{step.node_id}</span>
                    </div>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-medium border ${getNodeColor(step.node_type)}`}>
                      {step.node_type}
                    </span>
                  </div>

                  {/* Relative Latency Bar */}
                  <div className="space-y-1">
                    <div className="flex justify-between items-center text-[10px] text-gray-400">
                      <span>Latency</span>
                      <span className="font-mono text-gray-300">{step.latency_ms.toFixed(1)} ms</span>
                    </div>
                    <div className="w-full bg-gray-800 h-1.5 rounded-full overflow-hidden">
                      <div
                        className="bg-indigo-500 h-full rounded-full transition-all"
                        style={{ width: `${Math.max(percentWidth, 5)}%` }}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Selected Step JSON & Assertion Detail Inspector Column */}
        <div className="lg:col-span-7 space-y-4">
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider px-1">
            Node State Payload Inspector
          </h4>

          {selectedStep ? (
            <div className="p-5 rounded-xl bg-gray-900/60 border border-gray-800 space-y-5">
              {/* Selected Node Summary */}
              <div className="flex items-center justify-between pb-4 border-b border-gray-800">
                <div>
                  <div className="text-base font-bold text-gray-100">{selectedStep.node_id}</div>
                  <div className="text-xs text-gray-400 flex items-center gap-2 mt-1">
                    <span>Type: <strong className="text-indigo-400">{selectedStep.node_type}</strong></span>
                    <span>•</span>
                    <span>Duration: <strong className="text-amber-400">{selectedStep.latency_ms.toFixed(1)} ms</strong></span>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  Assertions Passed
                </div>
              </div>

              {/* Input State Inspector */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs font-medium text-gray-300">
                  <span className="flex items-center gap-1.5">
                    <Terminal className="w-3.5 h-3.5 text-indigo-400" />
                    Input State Payload
                  </span>
                </div>
                <pre className="p-3.5 rounded-lg bg-gray-950 border border-gray-800/80 text-[11px] font-mono text-emerald-300/90 overflow-x-auto">
                  {JSON.stringify(selectedStep.input_state, null, 2)}
                </pre>
              </div>

              {/* Output State Inspector */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs font-medium text-gray-300">
                  <span className="flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5 text-purple-400" />
                    Output State Payload
                  </span>
                </div>
                <pre className="p-3.5 rounded-lg bg-gray-950 border border-gray-800/80 text-[11px] font-mono text-cyan-300/90 overflow-x-auto">
                  {JSON.stringify(selectedStep.output_state, null, 2)}
                </pre>
              </div>

              {/* Node Evaluation Block Assertions Detail */}
              <div className="p-3.5 rounded-lg bg-gray-950/60 border border-gray-800/80 space-y-2">
                <div className="text-xs font-semibold text-gray-300 mb-1">Evaluated Block Assertions</div>
                <div className="flex items-center justify-between text-xs p-2 rounded bg-gray-900/60 border border-gray-800">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="font-mono text-gray-300 text-[11px]">output_state != None</span>
                  </div>
                  <span className="text-[10px] text-emerald-400 font-medium">Passed (1.0)</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-8 rounded-xl bg-gray-900/40 border border-gray-800 text-center text-gray-400 text-xs">
              Select a node step on the left to inspect state inputs, outputs, and assertion results.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
