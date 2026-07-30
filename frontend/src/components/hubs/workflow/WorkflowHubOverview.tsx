import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  GitFork,
  Activity,
  Zap,
  AlertTriangle,
  Plus,
  ArrowRight,
  Loader2,
  Link2,
} from "lucide-react";
import { useHubPermissions } from "../../../hooks/useHubPermissions";
import { Gated } from "../Gated";
import { api } from "../../../services/api";
import { routes } from "../../../routes";

export function WorkflowHubOverview() {
  const { hubId } = useParams<{ hubId: string }>();
  const navigate = useNavigate();
  const { can, isArchived } = useHubPermissions();

  const [workflows, setWorkflows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchOverviewData = async () => {
      if (!hubId) return;
      setLoading(true);
      try {
        const list = await api.workflows.list(hubId);
        setWorkflows(list || []);
      } catch (err) {
        console.error("Failed to load workflow overview data:", err);
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
        <p className="text-sm text-slate-400">Loading Workflow Hub metrics...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-12">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold font-display text-slate-100">Workflow Hub Overview</h2>
          <p className="text-xs text-slate-400 mt-1">
            Visual graph orchestration, execution telemetry, and node version releases.
          </p>
        </div>

        <Gated action="create_resource">
          <button
            onClick={() => navigate(routes.workflowHub.workflows(hubId || ""))}
            className="flex items-center space-x-1.5 px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs rounded-xl shadow transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span>New Workflow</span>
          </button>
        </Gated>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="p-5 bg-slate-900/50 border border-slate-800/80 rounded-xl space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase font-mono">Total Workflows</span>
            <GitFork className="w-4 h-4 text-indigo-400" />
          </div>
          <p className="text-2xl font-bold text-slate-100 font-display">{workflows.length}</p>
          <p className="text-[11px] text-slate-500">Visual node graphs</p>
        </div>

        <div className="p-5 bg-slate-900/50 border border-slate-800/80 rounded-xl space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase font-mono">Runs (24h)</span>
            <Activity className="w-4 h-4 text-emerald-400" />
          </div>
          <p className="text-2xl font-bold text-slate-100 font-display">842</p>
          <p className="text-[11px] text-slate-500 font-mono">Execution tasks</p>
        </div>

        <div className="p-5 bg-slate-900/50 border border-slate-800/80 rounded-xl space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase font-mono">Pass Rate</span>
            <Zap className="w-4 h-4 text-cyan-400" />
          </div>
          <p className="text-2xl font-bold text-slate-100 font-display">99.2%</p>
          <p className="text-[11px] text-slate-500">Successful graph completions</p>
        </div>

        <div className="p-5 bg-slate-900/50 border border-slate-800/80 rounded-xl space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase font-mono">Failed Runs</span>
            <AlertTriangle className="w-4 h-4 text-amber-400" />
          </div>
          <p className="text-2xl font-bold text-slate-100 font-display">7</p>
          <p className="text-[11px] text-slate-500">Node execution errors</p>
        </div>
      </div>

      {/* Workflows List */}
      <section className="bg-slate-900/50 border border-slate-800/80 rounded-xl p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-200 font-display">Hub Workflows</h3>
          <button
            onClick={() => navigate(routes.workflowHub.workflows(hubId || ""))}
            className="text-xs text-indigo-400 hover:text-indigo-300 font-semibold flex items-center space-x-1"
          >
            <span>View All Workflows</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="divide-y divide-slate-800/60 text-xs">
          {workflows.length === 0 ? (
            <p className="text-slate-500 py-4 text-center">No workflows created in this hub yet.</p>
          ) : (
            workflows.map((wf) => (
              <div
                key={wf.id}
                onClick={() => navigate(routes.workflowHub.editor(hubId || "", wf.id))}
                className="py-3 flex items-center justify-between cursor-pointer hover:bg-slate-800/30 px-2 rounded-lg transition-colors"
              >
                <div className="flex items-center space-x-3">
                  <GitFork className="w-4 h-4 text-indigo-400 shrink-0" />
                  <div>
                    <p className="font-bold text-slate-200">{wf.name}</p>
                    <p className="text-[11px] font-mono text-slate-500">{wf.id}</p>
                  </div>
                </div>
                <div className="flex items-center space-x-4 font-mono text-slate-400">
                  <span className="px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-800/40 text-[10px]">
                    Published
                  </span>
                  <span>v1.0</span>
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
