import { useState, useEffect } from "react";
import {
  Database,
  Plus,
  Trash2,
  Loader2,
  AlertCircle,
  CheckCircle2,
  XCircle,
  RefreshCw,
} from "lucide-react";
import { api } from "../../services/api";
import { useHubContext } from "../hubs/HubContext";
import { CreateDatabaseConnectionDialog } from "./CreateDatabaseConnectionDialog";

const DB_TYPE_BADGES: Record<string, { label: string; color: string }> = {
  postgres: { label: "PostgreSQL", color: "bg-sky-500/15 text-sky-300 border-sky-500/30" },
  mysql: { label: "MySQL", color: "bg-orange-500/15 text-orange-300 border-orange-500/30" },
  mongodb: { label: "MongoDB", color: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
  redis: { label: "Redis", color: "bg-rose-500/15 text-rose-300 border-rose-500/30" },
  snowflake: { label: "Snowflake", color: "bg-blue-500/15 text-blue-300 border-blue-500/30" },
  bigquery: { label: "BigQuery", color: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30" },
};

export function DatabaseConnectionsTab() {
  const { hub } = useHubContext();
  const [connections, setConnections] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [health, setHealth] = useState<Record<string, { ok: boolean; message: string }>>({});

  const fetchConnections = async () => {
    if (!hub) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.dbCredentials.list(hub.id);
      setConnections(data);
    } catch (err: any) {
      setError(err?.message || "Failed to load database connections");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConnections();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hub?.id]);

  const handleTest = async (id: string) => {
    if (!hub) return;
    setTestingId(id);
    try {
      const res = await api.dbCredentials.test(hub.id, id);
      setHealth((h) => ({ ...h, [id]: { ok: res?.ok !== false, message: res?.message || "OK" } }));
    } catch (err: any) {
      setHealth((h) => ({ ...h, [id]: { ok: false, message: err?.message || "Failed" } }));
    } finally {
      setTestingId(null);
    }
  };

  const handleDelete = async (id: string) => {
    if (!hub) return;
    if (!window.confirm("Delete this database connection?")) return;
    try {
      await api.dbCredentials.remove(hub.id, id);
      fetchConnections();
    } catch (err: any) {
      console.error("Failed to delete connection:", err);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-100 flex items-center space-x-2">
            <Database className="w-4 h-4 text-emerald-400" />
            <span>External Database Connections</span>
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Hub-scoped credentials for workflow database nodes and LLM agent MCP tools.
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={fetchConnections}
            className="p-2 text-slate-400 hover:text-slate-200 border border-slate-800 rounded-lg hover:bg-slate-800/50 transition-colors"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <button
            onClick={() => setIsCreateOpen(true)}
            className="flex items-center space-x-1.5 px-3 py-2 text-xs font-medium text-white bg-emerald-600 hover:bg-emerald-500 rounded-lg transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Connection</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center space-x-2 text-xs text-rose-400 bg-rose-950/30 border border-rose-900/50 rounded-lg px-3 py-2">
          <AlertCircle className="w-3.5 h-3.5" />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-16 text-slate-500">
          <Loader2 className="w-5 h-5 animate-spin mr-2" />
          <span className="text-sm">Loading connections...</span>
        </div>
      ) : connections.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 border border-dashed border-slate-800 rounded-xl text-slate-500">
          <Database className="w-8 h-8 mb-3 text-slate-700" />
          <p className="text-sm">No database connections yet.</p>
          <p className="text-xs text-slate-600 mt-1">Add a connection to query external databases in workflows.</p>
        </div>
      ) : (
        <div className="border border-slate-800 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-950/60 text-left text-xs text-slate-500">
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Engine</th>
                <th className="px-4 py-3 font-medium">Host</th>
                <th className="px-4 py-3 font-medium">Read-only</th>
                <th className="px-4 py-3 font-medium">Health</th>
                <th className="px-4 py-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {connections.map((conn) => {
                const badge = DB_TYPE_BADGES[conn.db_type] || {
                  label: conn.db_type,
                  color: "bg-slate-500/15 text-slate-300 border-slate-500/30",
                };
                const h = health[conn.id];
                return (
                  <tr key={conn.id} className="hover:bg-slate-900/40 transition-colors">
                    <td className="px-4 py-3 text-slate-200 font-medium">{conn.name}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium border ${badge.color}`}>
                        {badge.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-400 font-mono text-xs">
                      {conn.host || "-"}:{conn.port || "-"}
                    </td>
                    <td className="px-4 py-3">
                      {conn.is_read_only ? (
                        <span className="text-[10px] font-medium text-amber-400 bg-amber-500/10 border border-amber-500/30 rounded-full px-2 py-0.5">
                          Read-only
                        </span>
                      ) : (
                        <span className="text-[10px] font-medium text-slate-400 bg-slate-500/10 border border-slate-500/30 rounded-full px-2 py-0.5">
                          Read-write
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {testingId === conn.id ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin text-slate-500" />
                      ) : h ? (
                        <span className={`flex items-center space-x-1 text-[10px] ${h.ok ? "text-emerald-400" : "text-rose-400"}`}>
                          {h.ok ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                          <span>{h.ok ? "Healthy" : "Failed"}</span>
                        </span>
                      ) : (
                        <button
                          onClick={() => handleTest(conn.id)}
                          className="text-[10px] text-slate-500 hover:text-slate-300 underline"
                        >
                          Test
                        </button>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => handleDelete(conn.id)}
                        className="p-1.5 text-slate-500 hover:text-rose-400 hover:bg-rose-950/30 rounded-lg transition-colors"
                        title="Delete"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <CreateDatabaseConnectionDialog
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        hubId={hub?.id || ""}
        onCreated={fetchConnections}
      />
    </div>
  );
}
