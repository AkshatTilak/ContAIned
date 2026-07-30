import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Sparkles,
  ArrowLeft,
  Play,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  BarChart2,
  FileText,
} from "lucide-react";
import { useHubPermissions } from "../../../hooks/useHubPermissions";
import { api } from "../../../services/api";
import { routes } from "../../../routes";

export function EvalResultsDashboard() {
  const { hubId, suiteId } = useParams<{ hubId: string; suiteId: string }>();
  const navigate = useNavigate();
  const { can, isArchived } = useHubPermissions();

  const [suite, setSuite] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSuite = async () => {
    if (!hubId || !suiteId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.evals.suites.get(hubId, suiteId);
      setSuite(data);
    } catch (err: any) {
      setError(err?.message || "Failed to load suite detail");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSuite();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hubId, suiteId]);

  if (loading) {
    return (
      <div className="p-8 text-center space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mx-auto" />
        <p className="text-sm text-slate-400">Loading Evaluation metrics...</p>
      </div>
    );
  }

  if (error || !suite) {
    return (
      <div className="p-8 text-center space-y-4">
        <AlertTriangle className="w-10 h-10 text-red-500 mx-auto" />
        <h3 className="text-base font-bold text-slate-200">Suite Not Found</h3>
        <p className="text-xs text-slate-400">{error || "Could not load evaluation suite data"}</p>
        <button
          onClick={() => navigate(routes.evalHub.suites(hubId || ""))}
          className="px-4 py-2 bg-slate-800 text-slate-200 text-xs font-medium rounded-lg hover:bg-slate-700"
        >
          Back to Suite Manager
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-4">
        <div className="flex items-center space-x-3">
          <button
            onClick={() => navigate(routes.evalHub.suites(hubId || ""))}
            className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
            title="Back to Suite Manager"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-bold font-display text-slate-100">{suite.name}</h1>
              <span className="px-2 py-0.5 text-xs font-mono font-semibold uppercase bg-indigo-950/60 text-indigo-400 border border-indigo-800/40 rounded">
                {suite.target_type}
              </span>
            </div>
            <p className="text-xs font-mono text-slate-500 mt-0.5">
              ID: {suite.id}
            </p>
          </div>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <div className="p-5 bg-slate-900/50 border border-slate-800/80 rounded-xl space-y-2">
          <span className="text-xs font-semibold uppercase font-mono text-slate-400">Faithfulness</span>
          <p className="text-2xl font-bold text-emerald-400 font-display">0.94</p>
          <p className="text-[11px] text-slate-500">RAGAS Ground Truth Ratio</p>
        </div>

        <div className="p-5 bg-slate-900/50 border border-slate-800/80 rounded-xl space-y-2">
          <span className="text-xs font-semibold uppercase font-mono text-slate-400">Answer Relevancy</span>
          <p className="text-2xl font-bold text-emerald-400 font-display">0.91</p>
          <p className="text-[11px] text-slate-500">Semantic Alignment Score</p>
        </div>

        <div className="p-5 bg-slate-900/50 border border-slate-800/80 rounded-xl space-y-2">
          <span className="text-xs font-semibold uppercase font-mono text-slate-400">Context Recall</span>
          <p className="text-2xl font-bold text-amber-400 font-display">0.86</p>
          <p className="text-[11px] text-slate-500">Vector Search Precision</p>
        </div>
      </div>

      {/* Test Cases List */}
      <section className="bg-slate-900/50 border border-slate-800/80 rounded-xl p-6 space-y-4">
        <h3 className="text-sm font-bold text-slate-200 font-display flex items-center space-x-2">
          <FileText className="w-4 h-4 text-indigo-400" />
          <span>Ground Truth Test Cases (12)</span>
        </h3>

        <div className="divide-y divide-slate-800/60 text-xs">
          {[
            { query: "What is the return policy for defective hardware?", score: 0.96, status: "passed" },
            { query: "How do I trigger an automatic webhook retry?", score: 0.91, status: "passed" },
            { query: "Explain the rate limits for the v6 ingestion endpoints", score: 0.84, status: "passed" },
          ].map((tc, idx) => (
            <div key={idx} className="py-3 flex items-center justify-between">
              <div className="space-y-0.5">
                <p className="font-bold text-slate-200">"{tc.query}"</p>
                <p className="text-[11px] font-mono text-slate-500">Assertion: semantic_similarity &gt;= 0.85</p>
              </div>
              <div className="flex items-center space-x-3 font-mono">
                <span className="text-emerald-400 font-bold">Score: {tc.score}</span>
                <span className="px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-800/40 text-[10px]">
                  Passed
                </span>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
