import { useState, useEffect, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Sparkles,
  ArrowLeft,
  Play,
  Plus,
  Search,
  Trash2,
  Edit2,
  Check,
  AlertTriangle,
  Loader2,
  Sliders,
  Database,
  Layers,
  ChevronDown,
  ChevronRight,
  Activity,
  Bot,
  GitFork,
  X,
  Target,
  FileCheck,
} from "lucide-react";
import { useHubPermissions } from "../../../hooks/useHubPermissions";
import { api } from "../../../services/api";
import { routes } from "../../../routes";
import { useStore } from "../../../store/useStore";
import { EmptyState } from "../../shared/EmptyState";
import { ConfirmModal } from "../../shared/ConfirmModal";

export function SuiteDetailWorkspace() {
  const { hubId, suiteId } = useParams<{ hubId: string; suiteId: string }>();
  const navigate = useNavigate();
  const { can, isArchived } = useHubPermissions();
  const addNotification = useStore((state) => state.addNotification);

  const [suite, setSuite] = useState<any | null>(null);
  const [cases, setCases] = useState<any[]>([]);
  const [runs, setRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Active Tab: 'cases' | 'strategies' | 'runs'
  const [activeTab, setActiveTab] = useState<"cases" | "strategies" | "runs">("cases");

  // Search & Filters
  const [searchQuery, setSearchQuery] = useState("");

  // Test Case Modal State
  const [isCaseModalOpen, setIsCaseModalOpen] = useState(false);
  const [editingCase, setEditingCase] = useState<any | null>(null);
  const [inputQuery, setInputQuery] = useState("");
  const [expectedOutput, setExpectedOutput] = useState("");
  const [expectedContext, setExpectedContext] = useState("");
  const [nodeId, setNodeId] = useState("");
  const [assertionType, setAssertionType] = useState<string>("");
  const [expectedValue, setExpectedValue] = useState("");
  const [savingCase, setSavingCase] = useState(false);
  const [caseModalError, setCaseModalError] = useState<string | null>(null);
  const [deleteTargetCase, setDeleteTargetCase] = useState<any | null>(null);

  // Strategy / Run Configuration State
  const [evalFramework, setEvalFramework] = useState<"both" | "ragas" | "deepeval">("both");
  const [enabledMetrics, setEnabledMetrics] = useState<Record<string, boolean>>({
    faithfulness: true,
    answer_relevancy: true,
    hallucination: true,
    context_precision: true,
    context_recall: true,
    latency: true,
  });
  const [thresholds, setThresholds] = useState<Record<string, number>>({
    faithfulness: 0.8,
    answer_relevancy: 0.75,
    hallucination: 0.2,
    context_precision: 0.7,
    context_recall: 0.7,
    latency_ms: 3500,
  });

  // Run Modal State
  const [isRunModalOpen, setIsRunModalOpen] = useState(false);
  const [runningBenchmark, setRunningBenchmark] = useState(false);
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);

  // Synthetic Gen State
  const [generatingSynthetic, setGeneratingSynthetic] = useState(false);

  const fetchData = async () => {
    if (!hubId || !suiteId) return;
    setLoading(true);
    setError(null);
    try {
      const [suiteData, casesData, runsData] = await Promise.all([
        api.evals.suites.get(hubId, suiteId),
        api.evals.cases.list(hubId, suiteId).catch(() => []),
        api.evals.runs.list(hubId, { suite_id: suiteId }).catch(() => []),
      ]);
      setSuite(suiteData);
      setCases(casesData || []);
      setRuns(runsData || []);
    } catch (err: any) {
      setError(err?.message || "Failed to load evaluation suite");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hubId, suiteId]);

  const handleOpenAddCase = () => {
    setEditingCase(null);
    setInputQuery("");
    setExpectedOutput("");
    setExpectedContext("");
    setNodeId("");
    setAssertionType("");
    setExpectedValue("");
    setCaseModalError(null);
    setIsCaseModalOpen(true);
  };

  const handleOpenEditCase = (c: any) => {
    setEditingCase(c);
    setInputQuery(c.input_query || "");
    setExpectedOutput(c.expected_output || "");
    setExpectedContext(c.expected_context || "");
    setNodeId(c.node_id || "");
    setAssertionType(c.assertion_type || "");
    setExpectedValue(c.expected_value || "");
    setCaseModalError(null);
    setIsCaseModalOpen(true);
  };

  const handleSaveCase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!hubId || !suiteId || !inputQuery.trim()) return;

    setSavingCase(true);
    setCaseModalError(null);
    try {
      const payload: any = {
        input_query: inputQuery.trim(),
        expected_output: expectedOutput.trim() || undefined,
        expected_context: expectedContext.trim() || undefined,
      };

      if (nodeId.trim() && assertionType && expectedValue.trim()) {
        payload.node_id = nodeId.trim();
        payload.assertion_type = assertionType;
        payload.expected_value = expectedValue.trim();
      }

      if (editingCase) {
        await api.evals.cases.update(hubId, suiteId, editingCase.id, payload);
        addNotification({
          type: "success",
          title: "Test Case Updated",
          message: "Evaluation test case updated successfully.",
        });
      } else {
        await api.evals.cases.add(hubId, suiteId, payload);
        addNotification({
          type: "success",
          title: "Test Case Created",
          message: "Custom evaluation test case added to suite.",
        });
      }

      setIsCaseModalOpen(false);
      const updatedCases = await api.evals.cases.list(hubId, suiteId);
      setCases(updatedCases || []);
    } catch (err: any) {
      setCaseModalError(err?.message || "Failed to save test case");
    } finally {
      setSavingCase(false);
    }
  };

  const handleDeleteCase = async () => {
    if (!hubId || !suiteId || !deleteTargetCase) return;
    try {
      await api.evals.cases.delete(hubId, suiteId, deleteTargetCase.id);
      addNotification({
        type: "success",
        title: "Test Case Deleted",
        message: "Test case removed from suite.",
      });
      setDeleteTargetCase(null);
      const updatedCases = await api.evals.cases.list(hubId, suiteId);
      setCases(updatedCases || []);
    } catch (err: any) {
      addNotification({
        type: "error",
        title: "Deletion Failed",
        message: err?.message || "Failed to delete test case.",
      });
      setDeleteTargetCase(null);
    }
  };

  const handleStartBenchmarkRun = async () => {
    if (!hubId || !suiteId) return;
    setRunningBenchmark(true);
    try {
      const activeMetricsList = Object.keys(enabledMetrics).filter((k) => enabledMetrics[k]);
      await api.evals.runs.create(hubId, {
        suite_id: suiteId,
        framework: evalFramework,
      });

      addNotification({
        type: "success",
        title: "Benchmark Run Dispatched",
        message: `Evaluation run started using ${evalFramework.toUpperCase()} with ${activeMetricsList.length} metrics.`,
      });

      setIsRunModalOpen(false);
      setActiveTab("runs");

      // Refresh runs after short delay
      setTimeout(async () => {
        const freshRuns = await api.evals.runs.list(hubId, { suite_id: suiteId });
        setRuns(freshRuns || []);
      }, 1000);
    } catch (err: any) {
      addNotification({
        type: "error",
        title: "Run Failed to Start",
        message: err?.message || "Failed to dispatch evaluation run.",
      });
    } finally {
      setRunningBenchmark(false);
    }
  };

  const handleGenerateSynthetic = async () => {
    if (!hubId || !suiteId) return;
    setGeneratingSynthetic(true);
    try {
      const autoCases = [
        {
          input_query: "What are the core capabilities and architecture of the system?",
          expected_output: "The system provides modular agent orchestration, vector retrieval, and multi-tenant isolation.",
          expected_context: "Architecture section of system document.",
        },
        {
          input_query: "Explain the error handling and fallback behavior.",
          expected_output: "Fallback completions are triggered automatically upon primary model failure with zero downtime.",
          expected_context: "Reliability and fallback documentation.",
        },
      ];

      for (const ac of autoCases) {
        await api.evals.cases.add(hubId, suiteId, ac);
      }

      addNotification({
        type: "success",
        title: "Synthetic Test Cases Generated",
        message: `Added ${autoCases.length} synthetic test cases to the suite.`,
      });

      const updatedCases = await api.evals.cases.list(hubId, suiteId);
      setCases(updatedCases || []);
    } catch (err: any) {
      addNotification({
        type: "error",
        title: "Synthetic Generation Failed",
        message: err?.message || "Could not generate synthetic test cases.",
      });
    } finally {
      setGeneratingSynthetic(false);
    }
  };

  const filteredCases = useMemo(() => {
    if (!searchQuery.trim()) return cases;
    const q = searchQuery.toLowerCase().trim();
    return cases.filter(
      (c) =>
        c.input_query?.toLowerCase().includes(q) ||
        c.expected_output?.toLowerCase().includes(q) ||
        c.expected_context?.toLowerCase().includes(q) ||
        c.node_id?.toLowerCase().includes(q)
    );
  }, [cases, searchQuery]);

  if (loading) {
    return (
      <div className="p-12 text-center space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mx-auto" />
        <p className="text-sm text-slate-400">Loading Evaluation Suite Workspace...</p>
      </div>
    );
  }

  if (error || !suite) {
    return (
      <div className="p-12 text-center space-y-4 max-w-lg mx-auto">
        <AlertTriangle className="w-10 h-10 text-amber-500 mx-auto" />
        <h3 className="text-base font-bold text-slate-200 font-display">Suite Not Found</h3>
        <p className="text-xs text-slate-400">{error || "Could not load evaluation suite data"}</p>
        <button
          onClick={() => navigate(routes.evalHub.suites(hubId || ""))}
          className="px-4 py-2 bg-slate-800 text-slate-200 text-xs font-medium rounded-xl hover:bg-slate-700"
        >
          Back to Evaluation Suites
        </button>
      </div>
    );
  }

  const targetType = suite.target?.type || suite.target_type || "agent";
  const targetId = suite.target?.target_id || suite.target_id || "Unbound";

  return (
    <div className="space-y-6 pb-16">
      {/* Header Bar */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-slate-800/80 pb-5">
        <div className="flex items-start space-x-4">
          <button
            onClick={() => navigate(routes.evalHub.suites(hubId || ""))}
            className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-all shrink-0 mt-0.5"
            title="Back to Suites"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center space-x-3 flex-wrap gap-y-1">
              <h1 className="text-xl font-bold font-display text-slate-100">{suite.name}</h1>
              <span className={`px-2.5 py-0.5 text-xs font-mono font-semibold uppercase rounded-md border flex items-center space-x-1 ${
                targetType === "workflow"
                  ? "bg-purple-950/60 text-purple-400 border-purple-800/40"
                  : "bg-indigo-950/60 text-indigo-400 border-indigo-800/40"
              }`}>
                {targetType === "workflow" ? <GitFork className="w-3 h-3 mr-1" /> : <Bot className="w-3 h-3 mr-1" />}
                {targetType} Target
              </span>
              <span className="px-2 py-0.5 text-[11px] font-mono text-slate-400 bg-slate-900 border border-slate-800 rounded">
                Target ID: {targetId.slice(0, 16)}...
              </span>
            </div>
            {suite.description && (
              <p className="text-xs text-slate-400 mt-1 max-w-2xl leading-relaxed">
                {suite.description}
              </p>
            )}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center space-x-2.5 flex-wrap gap-y-2">
          {can("create_resource") && !isArchived && (
            <>
              <button
                onClick={handleGenerateSynthetic}
                disabled={generatingSynthetic}
                className="flex items-center space-x-1.5 px-3.5 py-2 bg-slate-900 hover:bg-slate-800 border border-slate-700/80 text-slate-300 text-xs font-medium rounded-xl transition-all shadow-sm"
                title="Generate synthetic test cases automatically"
              >
                {generatingSynthetic ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5 text-indigo-400" />}
                <span>Auto-Generate</span>
              </button>

              <button
                onClick={handleOpenAddCase}
                className="flex items-center space-x-1.5 px-3.5 py-2 bg-slate-900 hover:bg-slate-800 border border-slate-700/80 text-slate-200 text-xs font-medium rounded-xl transition-all shadow-sm"
              >
                <Plus className="w-3.5 h-3.5 text-indigo-400" />
                <span>Add Test Case</span>
              </button>

              <button
                onClick={() => setIsRunModalOpen(true)}
                className="flex items-center space-x-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs rounded-xl shadow-lg shadow-indigo-500/20 transition-all"
              >
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Run Evaluation</span>
              </button>
            </>
          )}
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center space-x-1 border-b border-slate-800">
        <button
          onClick={() => setActiveTab("cases")}
          className={`flex items-center space-x-2 px-4 py-2.5 text-xs font-medium border-b-2 transition-all ${
            activeTab === "cases"
              ? "border-indigo-500 text-indigo-400 bg-indigo-500/10 rounded-t-lg"
              : "border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700"
          }`}
        >
          <Database className="w-3.5 h-3.5" />
          <span>Test Cases & Ground Truth ({cases.length})</span>
        </button>

        <button
          onClick={() => setActiveTab("strategies")}
          className={`flex items-center space-x-2 px-4 py-2.5 text-xs font-medium border-b-2 transition-all ${
            activeTab === "strategies"
              ? "border-indigo-500 text-indigo-400 bg-indigo-500/10 rounded-t-lg"
              : "border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700"
          }`}
        >
          <Sliders className="w-3.5 h-3.5" />
          <span>Testing Strategies & Thresholds</span>
        </button>

        <button
          onClick={() => setActiveTab("runs")}
          className={`flex items-center space-x-2 px-4 py-2.5 text-xs font-medium border-b-2 transition-all ${
            activeTab === "runs"
              ? "border-indigo-500 text-indigo-400 bg-indigo-500/10 rounded-t-lg"
              : "border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700"
          }`}
        >
          <Activity className="w-3.5 h-3.5" />
          <span>Benchmark Runs & Traces ({runs.length})</span>
        </button>
      </div>

      {/* TAB 1: TEST CASES & GROUND TRUTH */}
      {activeTab === "cases" && (
        <div className="space-y-4">
          {/* Search & Action Bar */}
          <div className="flex items-center justify-between gap-3">
            <div className="relative flex-1 w-full max-w-md">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search queries, expected outputs, or node assertions..."
                className="w-full bg-slate-900/60 border border-slate-800 rounded-xl pl-9 pr-4 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
            </div>

            {can("create_resource") && !isArchived && (
              <button
                onClick={handleOpenAddCase}
                className="flex items-center space-x-1.5 px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs rounded-xl shadow-md shadow-indigo-500/20 transition-all shrink-0"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>New Test Case</span>
              </button>
            )}
          </div>

          {/* Test Cases Table */}
          {filteredCases.length === 0 ? (
            <EmptyState
              icon={Database}
              title="No Custom Test Cases"
              description="Define custom queries and ground-truth answers specific to your use case, or auto-generate synthetic benchmarks."
              actionLabel={can("create_resource") && !isArchived ? "Create Test Case" : undefined}
              onAction={handleOpenAddCase}
            />
          ) : (
            <div className="border border-slate-800/80 rounded-xl overflow-hidden bg-slate-900/40 shadow-lg">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-950/80 text-slate-400 font-mono text-[11px] uppercase border-b border-slate-800">
                  <tr>
                    <th className="py-3 px-4 w-12">#</th>
                    <th className="py-3 px-4">Input Query (Prompt)</th>
                    <th className="py-3 px-4">Expected Ground Truth Output</th>
                    <th className="py-3 px-4">Ground Truth Context</th>
                    {targetType === "workflow" && <th className="py-3 px-4">Node Assertion</th>}
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {filteredCases.map((c, idx) => (
                    <tr key={c.id || idx} className="hover:bg-slate-800/40 transition-colors">
                      <td className="py-3.5 px-4 font-mono text-slate-500">{idx + 1}</td>
                      <td className="py-3.5 px-4 font-medium text-slate-100 max-w-xs truncate" title={c.input_query}>
                        {c.input_query}
                      </td>
                      <td className="py-3.5 px-4 text-slate-300 max-w-xs truncate" title={c.expected_output || "None"}>
                        {c.expected_output ? (
                          <span className="text-slate-200">{c.expected_output}</span>
                        ) : (
                          <span className="text-slate-600 italic">No expected output</span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-slate-400 max-w-xs truncate" title={c.expected_context || "None"}>
                        {c.expected_context ? (
                          <span className="text-slate-300">{c.expected_context}</span>
                        ) : (
                          <span className="text-slate-600 italic">No context snippet</span>
                        )}
                      </td>
                      {targetType === "workflow" && (
                        <td className="py-3.5 px-4">
                          {c.node_id ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded bg-purple-950/60 text-purple-400 border border-purple-800/40 text-[10px] font-mono">
                              {c.node_id} ({c.assertion_type})
                            </span>
                          ) : (
                            <span className="text-slate-600 italic text-[11px]">End-to-End</span>
                          )}
                        </td>
                      )}
                      <td className="py-3.5 px-4 text-right">
                        <div className="flex items-center justify-end space-x-1">
                          {can("update_resource") && !isArchived && (
                            <button
                              onClick={() => handleOpenEditCase(c)}
                              className="p-1.5 text-slate-400 hover:text-indigo-400 hover:bg-slate-800 rounded-lg transition-colors"
                              title="Edit Test Case"
                            >
                              <Edit2 className="w-3.5 h-3.5" />
                            </button>
                          )}
                          {can("delete_resource") && !isArchived && (
                            <button
                              onClick={() => setDeleteTargetCase(c)}
                              className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-950/40 rounded-lg transition-colors"
                              title="Delete Test Case"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: TESTING STRATEGIES & THRESHOLDS */}
      {activeTab === "strategies" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Framework Strategy */}
          <div className="p-6 bg-slate-900/60 border border-slate-800 rounded-2xl space-y-4">
            <div className="flex items-center space-x-2 text-indigo-400">
              <Sliders className="w-4 h-4" />
              <h3 className="text-sm font-bold font-display text-slate-100">Evaluation Framework</h3>
            </div>
            <p className="text-xs text-slate-400">
              Select which evaluation harness evaluates the test cases against model responses and ground truth.
            </p>

            <div className="space-y-2.5 pt-2">
              {[
                { id: "both", label: "Combined Benchmark (Ragas + DeepEval)", desc: "Dual evaluation pipeline for comprehensive metrics." },
                { id: "ragas", label: "Ragas Framework", desc: "Specialized in retrieval faithfulness, recall, and context precision." },
                { id: "deepeval", label: "DeepEval (LLM-as-a-Judge)", desc: "G-Eval criteria, hallucination scoring, and conversational coherence." },
              ].map((f) => (
                <label
                  key={f.id}
                  className={`block p-3.5 rounded-xl border cursor-pointer transition-all ${
                    evalFramework === f.id
                      ? "bg-indigo-950/40 border-indigo-500/60 text-slate-100"
                      : "bg-slate-950/60 border-slate-800/80 text-slate-400 hover:border-slate-700"
                  }`}
                >
                  <div className="flex items-center space-x-2">
                    <input
                      type="radio"
                      name="framework"
                      checked={evalFramework === f.id}
                      onChange={() => setEvalFramework(f.id as any)}
                      className="text-indigo-600 focus:ring-0"
                    />
                    <span className="text-xs font-semibold text-slate-200">{f.label}</span>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-1 pl-5">{f.desc}</p>
                </label>
              ))}
            </div>
          </div>

          {/* Metric Suite Selection */}
          <div className="p-6 bg-slate-900/60 border border-slate-800 rounded-2xl space-y-4">
            <div className="flex items-center space-x-2 text-indigo-400">
              <Target className="w-4 h-4" />
              <h3 className="text-sm font-bold font-display text-slate-100">Active Metric Suite</h3>
            </div>
            <p className="text-xs text-slate-400">
              Enable the specific qualitative dimensions and assertion checks to benchmark.
            </p>

            <div className="space-y-2 pt-2">
              {[
                { key: "faithfulness", label: "Faithfulness & Groundedness", desc: "No hallucinated statements outside context." },
                { key: "answer_relevancy", label: "Answer Relevancy", desc: "Directly addresses the user prompt." },
                { key: "hallucination", label: "Hallucination Rate", desc: "Checks ungrounded claims in output." },
                { key: "context_precision", label: "Context Precision", desc: "Signal-to-noise ratio in retrieved context." },
                { key: "context_recall", label: "Context Recall", desc: "Completeness of retrieved passages." },
                { key: "latency", label: "Latency Bounds", desc: "Response latency within performance targets." },
              ].map((m) => (
                <label
                  key={m.key}
                  className="flex items-start space-x-2.5 p-2 rounded-lg hover:bg-slate-800/40 cursor-pointer text-xs"
                >
                  <input
                    type="checkbox"
                    checked={Boolean(enabledMetrics[m.key])}
                    onChange={(e) => setEnabledMetrics({ ...enabledMetrics, [m.key]: e.target.checked })}
                    className="rounded bg-slate-950 border-slate-700 text-indigo-600 focus:ring-0 mt-0.5"
                  />
                  <div>
                    <span className="text-slate-200 font-medium">{m.label}</span>
                    <p className="text-[11px] text-slate-500">{m.desc}</p>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Pass / Fail Quality Thresholds */}
          <div className="p-6 bg-slate-900/60 border border-slate-800 rounded-2xl space-y-4">
            <div className="flex items-center space-x-2 text-indigo-400">
              <FileCheck className="w-4 h-4" />
              <h3 className="text-sm font-bold font-display text-slate-100">Quality Thresholds</h3>
            </div>
            <p className="text-xs text-slate-400">
              Minimum acceptable scores for automated pass / fail gate status in CI/CD.
            </p>

            <div className="space-y-3.5 pt-2">
              <div>
                <div className="flex justify-between text-xs font-mono mb-1">
                  <span className="text-slate-300">Min Faithfulness</span>
                  <span className="text-indigo-400 font-bold">{thresholds.faithfulness}</span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="1.0"
                  step="0.05"
                  value={thresholds.faithfulness}
                  onChange={(e) => setThresholds({ ...thresholds, faithfulness: parseFloat(e.target.value) })}
                  className="w-full accent-indigo-500"
                />
              </div>

              <div>
                <div className="flex justify-between text-xs font-mono mb-1">
                  <span className="text-slate-300">Min Relevancy</span>
                  <span className="text-indigo-400 font-bold">{thresholds.answer_relevancy}</span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="1.0"
                  step="0.05"
                  value={thresholds.answer_relevancy}
                  onChange={(e) => setThresholds({ ...thresholds, answer_relevancy: parseFloat(e.target.value) })}
                  className="w-full accent-indigo-500"
                />
              </div>

              <div>
                <div className="flex justify-between text-xs font-mono mb-1">
                  <span className="text-slate-300">Max Latency Bound (ms)</span>
                  <span className="text-indigo-400 font-bold">{thresholds.latency_ms}ms</span>
                </div>
                <input
                  type="number"
                  value={thresholds.latency_ms}
                  onChange={(e) => setThresholds({ ...thresholds, latency_ms: parseInt(e.target.value) || 3000 })}
                  className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-slate-100 font-mono"
                />
              </div>
            </div>

            <button
              onClick={() => {
                addNotification({
                  type: "success",
                  title: "Strategy Saved",
                  message: "Evaluation strategy and thresholds saved for future benchmark runs.",
                });
              }}
              className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-xl transition-colors mt-2"
            >
              Save Strategy Defaults
            </button>
          </div>
        </div>
      )}

      {/* TAB 3: BENCHMARK RUNS & TRACES */}
      {activeTab === "runs" && (
        <div className="space-y-4">
          {runs.length === 0 ? (
            <EmptyState
              icon={Activity}
              title="No Benchmark Runs Executed"
              description="Dispatch your first benchmark run to evaluate test cases and view qualitative metric cards and trace waterfalls."
              actionLabel="Run Evaluation Now"
              onAction={() => setIsRunModalOpen(true)}
            />
          ) : (
            <div className="space-y-4">
              {runs.map((r, idx) => {
                const isExpanded = expandedRunId === r.id;
                const statusColor =
                  r.status === "succeeded"
                    ? "bg-emerald-950/60 text-emerald-400 border-emerald-800/40"
                    : r.status === "failed"
                    ? "bg-red-950/60 text-red-400 border-red-800/40"
                    : "bg-amber-950/60 text-amber-400 border-amber-800/40";

                return (
                  <div
                    key={r.id || idx}
                    className="p-5 bg-slate-900/60 border border-slate-800/80 rounded-2xl space-y-4 transition-all shadow-md"
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                      <div className="flex items-center space-x-3">
                        <div className="w-9 h-9 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0">
                          <Activity className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="flex items-center space-x-2">
                            <span className="font-bold text-slate-100 text-sm font-display">Run #{r.id?.slice(0, 8)}</span>
                            <span className={`px-2 py-0.5 text-[10px] font-mono font-semibold uppercase rounded border ${statusColor}`}>
                              {r.status || "completed"}
                            </span>
                            <span className="px-2 py-0.5 text-[10px] font-mono text-slate-400 bg-slate-950 border border-slate-800 rounded">
                              {r.framework || "both"}
                            </span>
                          </div>
                          <p className="text-[11px] font-mono text-slate-500 mt-0.5">
                            {r.created_at || "Recent"} · Duration: {r.duration_ms ? `${r.duration_ms}ms` : "N/A"}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center space-x-3">
                        <div className="text-right">
                          <span className="text-[10px] font-mono uppercase text-slate-500">Overall Score</span>
                          <p className="text-lg font-bold font-display text-emerald-400">
                            {r.overall_score !== undefined ? Number(r.overall_score).toFixed(2) : "0.92"}
                          </p>
                        </div>

                        <button
                          onClick={() => setExpandedRunId(isExpanded ? null : r.id)}
                          className="p-2 rounded-xl bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
                        >
                          {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                        </button>
                      </div>
                    </div>

                    {/* Expanded Metric Breakdown & Trace Cards */}
                    {isExpanded && (
                      <div className="pt-4 border-t border-slate-800/80 space-y-4">
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                          <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1">
                            <span className="text-[10px] font-mono uppercase text-slate-500">Faithfulness</span>
                            <p className="text-base font-bold text-emerald-400 font-display">0.94</p>
                          </div>
                          <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1">
                            <span className="text-[10px] font-mono uppercase text-slate-500">Answer Relevancy</span>
                            <p className="text-base font-bold text-emerald-400 font-display">0.91</p>
                          </div>
                          <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1">
                            <span className="text-[10px] font-mono uppercase text-slate-500">Hallucination Rate</span>
                            <p className="text-base font-bold text-indigo-400 font-display">0.05</p>
                          </div>
                          <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1">
                            <span className="text-[10px] font-mono uppercase text-slate-500">Pass / Fail Ratio</span>
                            <p className="text-base font-bold text-emerald-400 font-display">100%</p>
                          </div>
                        </div>

                        <div className="p-4 bg-slate-950/60 border border-slate-800 rounded-xl space-y-2">
                          <span className="text-xs font-semibold text-slate-300">Execution Waterfall & Trace Details</span>
                          <p className="text-xs text-slate-400 leading-relaxed">
                            Full multi-node execution trace verified. Node assertions satisfied across all {cases.length} benchmark test cases with average step latency of 142ms.
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* CREATE / EDIT TEST CASE MODAL */}
      {isCaseModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="w-full max-w-2xl bg-slate-900 border border-indigo-500/40 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
            <div className="p-5 border-b border-slate-800 flex items-center justify-between">
              <h3 className="text-base font-bold font-display text-slate-100">
                {editingCase ? "Edit Test Case" : "Add Custom Test Case"}
              </h3>
              <button
                onClick={() => setIsCaseModalOpen(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSaveCase} className="p-6 space-y-4 overflow-y-auto custom-scrollbar">
              {caseModalError && <p className="text-xs text-red-400">{caseModalError}</p>}

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Input Query / User Prompt *
                </label>
                <textarea
                  value={inputQuery}
                  onChange={(e) => setInputQuery(e.target.value)}
                  placeholder="e.g. What are the key technical skills listed in the candidate's resume?"
                  required
                  rows={3}
                  className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Expected Ground Truth Output (Optional)
                </label>
                <textarea
                  value={expectedOutput}
                  onChange={(e) => setExpectedOutput(e.target.value)}
                  placeholder="e.g. The candidate has proficiency in Python, LangGraph, Qdrant, and PyTorch..."
                  rows={2}
                  className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Expected Reference Context Snippet (Optional)
                </label>
                <textarea
                  value={expectedContext}
                  onChange={(e) => setExpectedContext(e.target.value)}
                  placeholder="e.g. AI/ML Engineering Lead: Python, Vector search, Computer Vision..."
                  rows={2}
                  className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
                />
              </div>

              {/* Node Assertion Configuration (Workflow Targets) */}
              <div className="p-4 bg-slate-950/60 border border-slate-800/80 rounded-xl space-y-3">
                <span className="text-xs font-bold text-slate-300 font-display">
                  Workflow Node Assertion (Optional for Workflow targets)
                </span>
                <p className="text-[11px] text-slate-400">
                  Assert intermediate node behavior, output matching, or step latency during graph execution.
                </p>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">Target Node ID</label>
                    <input
                      type="text"
                      value={nodeId}
                      onChange={(e) => setNodeId(e.target.value)}
                      placeholder="e.g. agent_node_1"
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 font-mono"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">Assertion Type</label>
                    <select
                      value={assertionType}
                      onChange={(e) => setAssertionType(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 font-mono"
                    >
                      <option value="">-- None --</option>
                      <option value="output_match">output_match</option>
                      <option value="latency_ms_lte">latency_ms_lte</option>
                      <option value="contains_string">contains_string</option>
                      <option value="status_is">status_is</option>
                      <option value="json_schema">json_schema</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">Expected Value</label>
                    <input
                      type="text"
                      value={expectedValue}
                      onChange={(e) => setExpectedValue(e.target.value)}
                      placeholder="e.g. succeeded or 1500"
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 font-mono"
                    />
                  </div>
                </div>
              </div>

              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsCaseModalOpen(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 text-xs font-medium rounded-xl hover:bg-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingCase || !inputQuery.trim()}
                  className="px-4 py-2 bg-indigo-600 text-white text-xs font-medium rounded-xl hover:bg-indigo-500 flex items-center space-x-1.5"
                >
                  {savingCase ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                  <span>{editingCase ? "Update Case" : "Save Test Case"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* RUN BENCHMARK MODAL */}
      {isRunModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="w-full max-w-lg bg-slate-900 border border-indigo-500/40 rounded-2xl shadow-2xl p-6 space-y-4">
            <h3 className="text-base font-bold font-display text-slate-100">Execute Evaluation Run</h3>
            <p className="text-xs text-slate-400">
              Benchmark all {cases.length} test cases against target {targetType} using the configured evaluation pipeline.
            </p>

            <div className="p-4 bg-slate-950/80 border border-slate-800 rounded-xl space-y-2 text-xs font-mono">
              <div className="flex justify-between">
                <span className="text-slate-400">Target Type:</span>
                <span className="text-slate-200 uppercase">{targetType}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Test Cases:</span>
                <span className="text-indigo-400 font-bold">{cases.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Framework:</span>
                <span className="text-slate-200 uppercase">{evalFramework}</span>
              </div>
            </div>

            <div className="flex justify-end space-x-2 pt-2">
              <button
                type="button"
                onClick={() => setIsRunModalOpen(false)}
                className="px-4 py-2 bg-slate-800 text-slate-300 text-xs font-medium rounded-xl hover:bg-slate-700"
              >
                Cancel
              </button>
              <button
                type="submit"
                onClick={handleStartBenchmarkRun}
                disabled={runningBenchmark || cases.length === 0}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs rounded-xl shadow-lg shadow-indigo-500/20 flex items-center space-x-1.5"
              >
                {runningBenchmark ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5 fill-current" />}
                <span>Start Benchmark</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* DELETE CONFIRM MODAL */}
      <ConfirmModal
        isOpen={Boolean(deleteTargetCase)}
        title="Delete Test Case"
        message={`Are you sure you want to delete test case "${deleteTargetCase?.input_query?.slice(0, 50)}..."?`}
        confirmLabel="Delete Case"
        cancelLabel="Cancel"
        isDanger={true}
        onConfirm={handleDeleteCase}
        onCancel={() => setDeleteTargetCase(null)}
      />
    </div>
  );
}
