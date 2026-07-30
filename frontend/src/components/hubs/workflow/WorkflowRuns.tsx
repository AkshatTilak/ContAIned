import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import {
  Activity,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Loader2,
  RefreshCw,
  Eye,
  X,
  Code,
} from "lucide-react";
import { api } from "../../../services/api";

export function WorkflowRuns() {
  const { hubId, workflowId } = useParams<{ hubId: string; workflowId: string }>();

  const [runs, setRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedRun, setSelectedRun] = useState<any | null>(null);

  const fetchRuns = async () => {
    if (!hubId || !workflowId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.workflows.runs.list(hubId, workflowId);
      setRuns(data || []);
    } catch (err: any) {
      setError(err?.message || "Failed to load workflow execution runs");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRuns();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hubId, workflowId]);

  const renderStatusBadge = (status: string) => {
    switch (status) {
      case "succeeded":
      case "completed":
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-950/60 text-emerald-400 border border-emerald-800/40 flex items-center space-x-1 w-fit">
            <CheckCircle2 className="w-3 h-3" />
            <span>Succeeded</span>
          </span>
        );
      case "running":
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-indigo-950/60 text-indigo-400 border border-indigo-800/40 flex items-center space-x-1 w-fit">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span>Running</span>
          </span>
        );
      case "failed":
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-red-950/60 text-red-400 border border-red-800/40 flex items-center space-x-1 w-fit">
            <AlertTriangle className="w-3 h-3" />
            <span>Failed</span>
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-800 text-slate-400 border border-slate-700 flex items-center space-x-1 w-fit">
            <Clock className="w-3 h-3" />
            <span>Queued</span>
          </span>
        );
    }
  };

  if (loading) {
    return (
      <div className="p-8 text-center space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mx-auto" />
        <p className="text-sm text-slate-400">Loading Workflow execution runs...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold font-display text-slate-100 flex items-center space-x-2">
            <Activity className="w-5 h-5 text-indigo-400" />
            <span>Execution Runs & Traces</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Persisted execution logs, node-level latency traces, and graph inputs/outputs.
          </p>
        </div>

        <button
          onClick={fetchRuns}
          className="p-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200 transition-colors self-start"
          title="Refresh Runs"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {error && (
        <div className="p-4 bg-red-950/40 border border-red-800/40 rounded-xl text-red-300 text-xs">
          {error}
        </div>
      )}

      {/* Runs Table */}
      <div className="bg-slate-900/50 border border-slate-800/80 rounded-xl overflow-hidden shadow-lg">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-slate-950/60 border-b border-slate-800 text-slate-400 font-semibold">
            <tr>
              <th className="p-3.5">Run ID</th>
              <th className="p-3.5">Trigger</th>
              <th className="p-3.5">Version</th>
              <th className="p-3.5">Status</th>
              <th className="p-3.5">Started</th>
              <th className="p-3.5 text-right">Inspect</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {runs.length === 0 ? (
              <tr>
                <td colSpan={6} className="p-6 text-center text-slate-500">
                  No workflow execution runs recorded yet.
                </td>
              </tr>
            ) : (
              runs.map((run) => (
                <tr key={run.id} className="hover:bg-slate-800/30 transition-colors">
                  <td className="p-3.5 font-mono text-indigo-400 font-semibold">{run.id.slice(0, 8)}...</td>
                  <td className="p-3.5 font-mono text-slate-400 uppercase">{run.trigger || "manual"}</td>
                  <td className="p-3.5 font-mono text-slate-300">v{run.version_number || 1}</td>
                  <td className="p-3.5">{renderStatusBadge(run.status)}</td>
                  <td className="p-3.5 font-mono text-slate-400">
                    {run.created_at ? new Date(run.created_at).toLocaleTimeString() : "Recently"}
                  </td>
                  <td className="p-3.5 text-right">
                    <button
                      onClick={() => setSelectedRun(run)}
                      className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
                      title="Inspect Run Trace"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Selected Run Drawer */}
      {selectedRun && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm">
          <div className="w-full max-w-lg bg-[#0f1117] border-l border-slate-800 p-6 space-y-6 overflow-y-auto custom-scrollbar">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <h3 className="font-bold text-slate-100 text-base font-display">Execution Run Detail</h3>
                <p className="text-xs font-mono text-slate-500">ID: {selectedRun.id}</p>
              </div>
              <button
                onClick={() => setSelectedRun(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div className="flex items-center justify-between p-3 bg-slate-950/60 border border-slate-800 rounded-xl">
                <span>Execution Status:</span>
                {renderStatusBadge(selectedRun.status)}
              </div>

              <div className="space-y-2">
                <span className="font-semibold text-slate-300 font-mono flex items-center space-x-1.5">
                  <Code className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Output Payload</span>
                </span>
                <pre className="p-3 bg-slate-950 rounded-xl border border-slate-800 font-mono text-slate-200 overflow-x-auto text-[11px] leading-relaxed">
                  {JSON.stringify(selectedRun.output_json || { status: "success" }, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
