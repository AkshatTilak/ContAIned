import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import {
  Activity,
  RefreshCw,
  Play,
  XCircle,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Clock,
} from "lucide-react";
import { useHubPermissions } from "../../../hooks/useHubPermissions";
import { api } from "../../../services/api";

export function JobsWorkspace() {
  const { hubId } = useParams<{ hubId: string }>();
  const { can, isArchived } = useHubPermissions();

  const [jobs, setJobs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchJobs = async () => {
    if (!hubId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.ingestion.jobs.list(hubId, undefined, 50, 0);
      setJobs(res.items || []);
    } catch (err: any) {
      setError(err?.message || "Failed to load ingestion jobs");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 4000); // Live poll
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hubId]);

  const renderStatusBadge = (status: string) => {
    switch (status) {
      case "completed":
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-950/60 text-emerald-400 border border-emerald-800/40 flex items-center space-x-1 w-fit">
            <CheckCircle2 className="w-3 h-3" />
            <span>Completed</span>
          </span>
        );
      case "processing":
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-indigo-950/60 text-indigo-400 border border-indigo-800/40 flex items-center space-x-1 w-fit">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span>Processing</span>
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
            <span>Pending</span>
          </span>
        );
    }
  };

  if (loading && jobs.length === 0) {
    return (
      <div className="p-8 text-center space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mx-auto" />
        <p className="text-sm text-slate-400">Loading hub ingestion jobs...</p>
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
            <span>Ingestion Jobs & Task Stream</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Real-time background tasks for document parsing, chunking, and embedding generation.
          </p>
        </div>

        <button
          onClick={fetchJobs}
          className="p-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200 transition-colors self-start"
          title="Refresh Jobs"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {error && (
        <div className="p-4 bg-red-950/40 border border-red-800/40 rounded-xl text-red-300 text-xs">
          {error}
        </div>
      )}

      {/* Jobs Table */}
      <div className="bg-slate-900/50 border border-slate-800/80 rounded-xl overflow-hidden shadow-lg">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-slate-950/60 border-b border-slate-800 text-slate-400 font-semibold">
            <tr>
              <th className="p-3.5">Job ID</th>
              <th className="p-3.5">Pipeline Config</th>
              <th className="p-3.5">Progress</th>
              <th className="p-3.5">Status</th>
              <th className="p-3.5">Updated</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {jobs.length === 0 ? (
              <tr>
                <td colSpan={5} className="p-6 text-center text-slate-500">
                  No ingestion jobs logged for this hub.
                </td>
              </tr>
            ) : (
              jobs.map((job) => {
                const cfg = job.pipeline_config || {};
                return (
                  <tr key={job.job_id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="p-3.5 font-mono text-indigo-400 font-semibold">
                      {job.job_id.slice(0, 8)}...
                      {job.document_id && (
                        <span className="block text-[10px] text-slate-500 font-normal">
                          Doc: {job.document_id.slice(0, 8)}
                        </span>
                      )}
                    </td>
                    <td className="p-3.5">
                      <div className="space-y-1">
                        <div className="flex items-center space-x-1.5 flex-wrap gap-y-1">
                          {cfg.ocr_engine && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-indigo-300 border border-slate-700">
                              OCR: {cfg.ocr_engine}
                            </span>
                          )}
                          {cfg.embedding_model && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-emerald-300 border border-slate-700">
                              Embed: {cfg.embedding_model}
                            </span>
                          )}
                          {cfg.chunking_strategy && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-amber-300 border border-slate-700">
                              {cfg.chunking_strategy} ({cfg.chunk_size || 512})
                            </span>
                          )}
                        </div>
                        {Array.isArray(cfg.post_processors) && cfg.post_processors.length > 0 && (
                          <div className="text-[10px] text-slate-400 flex items-center space-x-1">
                            <span className="text-slate-500">Post:</span>
                            <span className="font-mono text-slate-300">
                              {cfg.post_processors.join(", ")}
                            </span>
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="p-3.5">
                      <div className="flex items-center space-x-3 max-w-xs">
                        <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-indigo-500 rounded-full transition-all duration-300"
                            style={{ width: `${job.progress || (job.status === "completed" ? 100 : 0)}%` }}
                          />
                        </div>
                        <span className="font-mono text-[11px] text-slate-400">{job.progress || (job.status === "completed" ? 100 : 0)}%</span>
                      </div>
                    </td>
                    <td className="p-3.5">{renderStatusBadge(job.status)}</td>
                    <td className="p-3.5 font-mono text-slate-400">
                      {job.updated_at ? new Date(job.updated_at).toLocaleTimeString() : "Just now"}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
