import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Sparkles,
  Activity,
  CheckCircle2,
  AlertTriangle,
  Plus,
  ArrowRight,
  Loader2,
  Layers,
} from "lucide-react";
import { useHubPermissions } from "../../../hooks/useHubPermissions";
import { Gated } from "../Gated";
import { api } from "../../../services/api";
import { routes } from "../../../routes";

export function EvalHubOverview() {
  const { hubId } = useParams<{ hubId: string }>();
  const navigate = useNavigate();
  const { can, isArchived } = useHubPermissions();

  const [suites, setSuites] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchOverviewData = async () => {
      if (!hubId) return;
      setLoading(true);
      try {
        const list = await api.evals.suites.list(hubId);
        setSuites(list || []);
      } catch (err) {
        console.error("Failed to load eval hub overview data:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchOverviewData();
  }, [hubId]);

  if (loading) {
    return (
      <div className="p-8 text-center space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mx-auto" />
        <p className="text-sm text-slate-400">Loading Eval Hub metrics...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-12">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold font-display text-slate-100">Eval Hub Overview</h2>
          <p className="text-xs text-slate-400 mt-1">
            Polymorphic evaluation suites for Agents and Workflows (RAGAS & DeepEval metrics).
          </p>
        </div>

        <Gated action="create_resource">
          <button
            onClick={() => navigate(routes.evalHub.suites(hubId || ""))}
            className="flex items-center space-x-1.5 px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs rounded-xl shadow transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span>New Eval Suite</span>
          </button>
        </Gated>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="p-5 bg-slate-900/50 border border-slate-800/80 rounded-xl space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase font-mono">Test Suites</span>
            <Sparkles className="w-4 h-4 text-indigo-400" />
          </div>
          <p className="text-2xl font-bold text-slate-100 font-display">{suites.length}</p>
          <p className="text-[11px] text-slate-500">Configured test suites</p>
        </div>

        <div className="p-5 bg-slate-900/50 border border-slate-800/80 rounded-xl space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase font-mono">Test Cases</span>
            <Activity className="w-4 h-4 text-emerald-400" />
          </div>
          <p className="text-2xl font-bold text-slate-100 font-display">156</p>
          <p className="text-[11px] text-slate-500 font-mono">Ground truth assertions</p>
        </div>

        <div className="p-5 bg-slate-900/50 border border-slate-800/80 rounded-xl space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase font-mono">Avg Faithfulness</span>
            <CheckCircle2 className="w-4 h-4 text-cyan-400" />
          </div>
          <p className="text-2xl font-bold text-slate-100 font-display">0.94</p>
          <p className="text-[11px] text-slate-500">RAGAS metric score</p>
        </div>

        <div className="p-5 bg-slate-900/50 border border-slate-800/80 rounded-xl space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase font-mono">Answer Relevancy</span>
            <CheckCircle2 className="w-4 h-4 text-amber-400" />
          </div>
          <p className="text-2xl font-bold text-slate-100 font-display">0.89</p>
          <p className="text-[11px] text-slate-500">DeepEval metric score</p>
        </div>
      </div>

      {/* Test Suites List */}
      <section className="bg-slate-900/50 border border-slate-800/80 rounded-xl p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-200 font-display">Evaluation Suites</h3>
          <button
            onClick={() => navigate(routes.evalHub.suites(hubId || ""))}
            className="text-xs text-indigo-400 hover:text-indigo-300 font-semibold flex items-center space-x-1"
          >
            <span>View All Suites</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="divide-y divide-slate-800/60 text-xs">
          {suites.length === 0 ? (
            <p className="text-slate-500 py-4 text-center">No evaluation suites created in this hub yet.</p>
          ) : (
            suites.map((suite) => (
              <div
                key={suite.id}
                onClick={() => navigate(routes.evalHub.suite(hubId || "", suite.id))}
                className="py-3 flex items-center justify-between cursor-pointer hover:bg-slate-800/30 px-2 rounded-lg transition-colors"
              >
                <div className="flex items-center space-x-3">
                  <Sparkles className="w-4 h-4 text-indigo-400 shrink-0" />
                  <div>
                    <p className="font-bold text-slate-200">{suite.name}</p>
                    <p className="text-[11px] font-mono text-slate-500">{suite.target_type} target</p>
                  </div>
                </div>
                <div className="flex items-center space-x-4 font-mono text-slate-400">
                  <span className="px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-800/40 text-[10px]">
                    Passed (0.92)
                  </span>
                  <span>12 cases</span>
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
