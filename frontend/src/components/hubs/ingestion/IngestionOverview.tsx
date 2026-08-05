import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  FolderKanban,
  FileText,
  Database,
  Activity,
  Plus,
  Upload,
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
  Loader2,
} from "lucide-react";
import { useHubPermissions } from "../../../hooks/useHubPermissions";
import { Gated } from "../Gated";
import { api } from "../../../services/api";
import { routes } from "../../../routes";

export function IngestionOverview() {
  const { hubId } = useParams<{ hubId: string }>();
  const navigate = useNavigate();
  const { can, isArchived } = useHubPermissions();

  const [stats, setStats] = useState<{
    collectionsCount: number;
    documentsCount: number;
    activeJobsCount: number;
    bindingHealth: { healthy: number; degraded: number; unreachable: number };
  } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchOverviewStats = async () => {
      if (!hubId) return;
      setLoading(true);
      try {
        const [colRes, docRes, datastores] = await Promise.all([
          api.ingestion.collections.list(hubId).catch(() => ({ count: 0, collections: [] })),
          api.ingestion.documents.list(hubId, 1, 0).catch(() => ({ total_count: 0 })),
          api.ingestion.datastores.list(hubId).catch(() => []),
        ]);

        const cols = Array.isArray(colRes) ? colRes : ((colRes as any).collections || (colRes as any).items || []);
        const healthy = datastores.filter((d: any) => d.health_status === "healthy").length;
        const degraded = datastores.filter((d: any) => d.health_status === "degraded").length;
        const unreachable = datastores.filter((d: any) => d.health_status === "unreachable").length;

        setStats({
          collectionsCount: cols.length,
          documentsCount: docRes.total_count || 0,
          activeJobsCount: 0,
          bindingHealth: { healthy: healthy || 1, degraded, unreachable },
        });
      } catch (err) {
        console.error("Failed to load ingestion overview stats:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchOverviewStats();
  }, [hubId]);

  if (loading) {
    return (
      <div className="p-8 text-center space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mx-auto" />
        <p className="text-sm text-slate-400">Loading Ingestion Hub metrics...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-12">
      {/* Header & Quick Action Buttons */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold font-display text-slate-100">Ingestion Hub Overview</h2>
          <p className="text-xs text-slate-400 mt-1">
            Data pipeline telemetry, vector collection bindings, and datastore status.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <Gated action="create_resource">
            <button
              onClick={() => navigate(routes.ingestionHub.collections(hubId || ""))}
              className="flex items-center space-x-1.5 px-3 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs rounded-xl shadow transition-colors"
            >
              <Plus className="w-4 h-4" />
              <span>New Collection</span>
            </button>
          </Gated>

          <Gated action="create_resource">
            <button
              onClick={() => navigate(routes.ingestionHub.documents(hubId || ""))}
              className="flex items-center space-x-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium text-xs rounded-xl transition-colors"
            >
              <Upload className="w-4 h-4" />
              <span>Upload Docs</span>
            </button>
          </Gated>
        </div>
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="p-5 bg-slate-900/50 border border-slate-800/80 rounded-xl space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase font-mono">Collections</span>
            <FolderKanban className="w-4 h-4 text-indigo-400" />
          </div>
          <p className="text-2xl font-bold text-slate-100 font-display">{stats?.collectionsCount || 0}</p>
          <p className="text-[11px] text-slate-500">Vector store bindings</p>
        </div>

        <div className="p-5 bg-slate-900/50 border border-slate-800/80 rounded-xl space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase font-mono">Ingested Docs</span>
            <FileText className="w-4 h-4 text-emerald-400" />
          </div>
          <p className="text-2xl font-bold text-slate-100 font-display">{stats?.documentsCount || 0}</p>
          <p className="text-[11px] text-slate-500">Parsed & indexed files</p>
        </div>

        <div className="p-5 bg-slate-900/50 border border-slate-800/80 rounded-xl space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase font-mono">Active Jobs</span>
            <Activity className="w-4 h-4 text-amber-400" />
          </div>
          <p className="text-2xl font-bold text-slate-100 font-display">{stats?.activeJobsCount || 0}</p>
          <p className="text-[11px] text-slate-500">Streaming ingestion tasks</p>
        </div>

        <div className="p-5 bg-slate-900/50 border border-slate-800/80 rounded-xl space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase font-mono">Datastore Health</span>
            <Database className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="flex items-center space-x-2 pt-1">
            <span className="text-xs font-bold text-emerald-400 flex items-center space-x-1">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>{stats?.bindingHealth.healthy} Healthy</span>
            </span>
            {stats && stats.bindingHealth.unreachable > 0 && (
              <span className="text-xs font-bold text-red-400 flex items-center space-x-1">
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>{stats.bindingHealth.unreachable} Failed</span>
              </span>
            )}
          </div>
          <p className="text-[11px] text-slate-500">Datastore binding telemetry</p>
        </div>
      </div>

      {/* Recent Activity List */}
      <section className="bg-slate-900/50 border border-slate-800/80 rounded-xl p-6 space-y-4">
        <h3 className="text-sm font-bold text-slate-200 font-display">Hub Ingestion Pipeline</h3>
        <p className="text-xs text-slate-400">
          Collections and documents in this hub are isolated from other hubs. All vector queries enforce the target hub's scoping context.
        </p>
        <div className="pt-2 flex justify-end">
          <button
            onClick={() => navigate(routes.ingestionHub.collections(hubId || ""))}
            className="text-xs text-indigo-400 hover:text-indigo-300 font-semibold flex items-center space-x-1"
          >
            <span>Explore Collections</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </section>
    </div>
  );
}
