import React, { useEffect, useState, useCallback, useRef } from "react";
import { RefreshCw, AlertCircle, ChevronDown, ChevronUp, Clock, FileText } from "lucide-react";
import { api } from "../../services/api";
import { StatusBadge } from "../shared/StatusBadge";
import type { StatusVariant } from "../shared/StatusBadge";
import { LoadingSkeleton } from "../shared/LoadingSkeleton";
import { ErrorBanner } from "../shared/ErrorBanner";
import type { IngestionJobResponse } from "../../types/api";

type FilterStatus = "ALL" | "QUEUED" | "PROCESSING" | "COMPLETED" | "FAILED";

export const JobTracker: React.FC = () => {
  const [jobs, setJobs] = useState<IngestionJobResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterStatus>("ALL");
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
  const pollTimerRef = useRef<any>(null);

  const fetchJobs = useCallback(async () => {
    try {
      setError(null);
      const res = await api.getJobs();
      setJobs(res.items || []);
    } catch (err: any) {
      setError(err?.message || "Failed to load ingestion jobs");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  // Polling active jobs (queued / processing)
  useEffect(() => {
    const activeJobs = jobs.filter(
      (j) => j.status === "queued" || j.status === "processing"
    );

    if (activeJobs.length === 0) {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      return;
    }

    pollTimerRef.current = setInterval(async () => {
      let updatedAny = false;
      const updatedJobs = await Promise.all(
        jobs.map(async (job) => {
          if (job.status === "queued" || job.status === "processing") {
            try {
              const statusRes = await api.getJobStatus(job.job_id);
              updatedAny = true;
              return statusRes;
            } catch {
              return job;
            }
          }
          return job;
        })
      );

      if (updatedAny) {
        setJobs(updatedJobs);
      }
    }, 2000);

    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, [jobs]);

  const filteredJobs = jobs.filter((j) => {
    if (filter === "ALL") return true;
    return j.status.toUpperCase() === filter;
  });

  const toggleExpand = (jobId: string) => {
    setExpandedJobId((prev) => (prev === jobId ? null : jobId));
  };

  const getBadgeVariant = (status: string): StatusVariant => {
    const s = status.toLowerCase();
    if (s === "completed") return "success";
    if (s === "failed") return "error";
    if (s === "processing") return "info";
    if (s === "queued") return "warning";
    return "neutral";
  };

  if (loading) {
    return (
      <div className="p-6 bg-[var(--bg-surface)] rounded-xl border border-[var(--border-default)]">
        <LoadingSkeleton variant="card" count={3} />
      </div>
    );
  }

  return (
    <div className="p-6 bg-[var(--bg-surface)] rounded-xl border border-[var(--border-default)] space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[var(--border-default)] pb-4">
        <div>
          <h3 className="text-base font-semibold text-white flex items-center gap-2">
            <Clock className="w-5 h-5 text-emerald-400" />
            Ingestion Job Tracker
          </h3>
          <p className="text-xs text-zinc-400 mt-1">
            Monitor real-time document parsing, chunking, and embedding progress.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchJobs}
            className="p-2 rounded-lg bg-[var(--bg-input)] hover:bg-[var(--bg-hover)] text-zinc-300 hover:text-white border border-[var(--border-default)] transition-colors text-xs flex items-center gap-1.5"
            title="Refresh Jobs"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {error && <ErrorBanner message={error} onRetry={fetchJobs} />}

      {/* Filter Tabs */}
      <div className="flex flex-wrap gap-2 pt-1">
        {(["ALL", "QUEUED", "PROCESSING", "COMPLETED", "FAILED"] as FilterStatus[]).map(
          (status) => {
            const count =
              status === "ALL"
                ? jobs.length
                : jobs.filter((j) => j.status.toUpperCase() === status).length;
            const isActive = filter === status;
            return (
              <button
                key={status}
                onClick={() => setFilter(status)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border ${
                  isActive
                    ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-400"
                    : "bg-[var(--bg-input)] border-[var(--border-default)] text-zinc-400 hover:text-zinc-200"
                }`}
              >
                {status.charAt(0) + status.slice(1).toLowerCase()} ({count})
              </button>
            );
          }
        )}
      </div>

      {/* Job List */}
      {filteredJobs.length === 0 ? (
        <div className="py-12 text-center text-zinc-500 text-xs">
          No ingestion jobs found for the selected filter.
        </div>
      ) : (
        <div className="space-y-3 pt-2">
          {filteredJobs.map((job) => {
            const progress = Math.min(100, Math.max(0, job.progress || 0));
            const isExpanded = expandedJobId === job.job_id;

            return (
              <div
                key={job.job_id}
                className="p-4 rounded-lg bg-[var(--bg-surface-alt)] border border-[var(--border-default)] hover:border-[var(--border-hover)] transition-all space-y-3"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-400 shrink-0">
                      <FileText className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono font-medium text-white">
                          Job #{job.job_id.slice(0, 8)}
                        </span>
                        <StatusBadge variant={getBadgeVariant(job.status)} label={job.status} />
                      </div>
                      <span className="text-[11px] font-mono text-zinc-500">
                        Doc ID: {job.document_id || "N/A"}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 text-xs text-zinc-400">
                    {job.created_at && (
                      <span className="text-[11px]">
                        {new Date(job.created_at).toLocaleTimeString()}
                      </span>
                    )}

                    {job.error_msg && (
                      <button
                        onClick={() => toggleExpand(job.job_id)}
                        className="text-red-400 hover:text-red-300 flex items-center gap-1 text-[11px] font-medium"
                      >
                        <AlertCircle className="w-3.5 h-3.5" />
                        <span>Error Info</span>
                        {isExpanded ? (
                          <ChevronUp className="w-3 h-3" />
                        ) : (
                          <ChevronDown className="w-3 h-3" />
                        )}
                      </button>
                    )}
                  </div>
                </div>

                {/* Progress Bar for active/completed jobs */}
                {(job.status === "processing" || job.status === "queued" || job.status === "completed") && (
                  <div className="space-y-1">
                    <div className="flex justify-between text-[11px] text-zinc-400">
                      <span>Progress</span>
                      <span>{progress}%</span>
                    </div>
                    <div className="w-full bg-[var(--bg-input)] rounded-full h-1.5 overflow-hidden">
                      <div
                        className={`h-1.5 transition-all duration-300 ${
                          job.status === "completed"
                            ? "bg-emerald-500"
                            : "bg-emerald-400 animate-pulse"
                        }`}
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                  </div>
                )}

                {/* Expanded Error Details */}
                {isExpanded && job.error_msg && (
                  <div className="p-3 rounded bg-red-500/10 border border-red-500/20 text-red-300 text-xs font-mono whitespace-pre-wrap">
                    <div className="font-semibold text-red-400 mb-1 flex items-center gap-1.5">
                      <AlertCircle className="w-4 h-4" />
                      Failure Traceback:
                    </div>
                    {job.error_msg}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
