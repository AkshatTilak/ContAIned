import { useState } from "react";
import {
  X,
  Loader2,
  Database,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import { api } from "../../services/api";

interface CreateDatabaseConnectionDialogProps {
  isOpen: boolean;
  onClose: () => void;
  hubId: string;
  onCreated: () => void;
}

const DB_TYPES = [
  { value: "postgres", label: "PostgreSQL" },
  { value: "mysql", label: "MySQL" },
  { value: "mongodb", label: "MongoDB" },
  { value: "redis", label: "Redis" },
  { value: "snowflake", label: "Snowflake" },
  { value: "bigquery", label: "BigQuery" },
];

export function CreateDatabaseConnectionDialog({
  isOpen,
  onClose,
  hubId,
  onCreated,
}: CreateDatabaseConnectionDialogProps) {
  const [form, setForm] = useState({
    name: "",
    db_type: "postgres",
    host: "",
    port: "",
    database_name: "",
    username: "",
    password: "",
    is_read_only: true,
    max_connections: 10,
  });
  const [submitting, setSubmitting] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);

  if (!isOpen) return null;

  const update = (key: string, value: any) => setForm((f) => ({ ...f, [key]: value }));

  const handleTest = async () => {
    if (!form.name.trim()) {
      setError("Name is required before testing.");
      return;
    }
    setTesting(true);
    setError(null);
    setTestResult(null);
    try {
      // Create a temporary credential then test it.
      const created = await api.dbCredentials.create(hubId, {
        name: form.name.trim(),
        db_type: form.db_type,
        host: form.host || undefined,
        port: form.port ? Number(form.port) : undefined,
        database_name: form.database_name || undefined,
        username: form.username || undefined,
        password: form.password || undefined,
        is_read_only: form.is_read_only,
        max_connections: Number(form.max_connections) || 10,
      });
      const res = await api.dbCredentials.test(hubId, created.id);
      setTestResult({ ok: res?.ok !== false, message: res?.message || "Connection successful" });
    } catch (err: any) {
      setTestResult({ ok: false, message: err?.message || "Connection test failed" });
    } finally {
      setTesting(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) {
      setError("Name is required.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await api.dbCredentials.create(hubId, {
        name: form.name.trim(),
        db_type: form.db_type,
        host: form.host || undefined,
        port: form.port ? Number(form.port) : undefined,
        database_name: form.database_name || undefined,
        username: form.username || undefined,
        password: form.password || undefined,
        is_read_only: form.is_read_only,
        max_connections: Number(form.max_connections) || 10,
      });
      onCreated();
      onClose();
      setForm({
        name: "",
        db_type: "postgres",
        host: "",
        port: "",
        database_name: "",
        username: "",
        password: "",
        is_read_only: true,
        max_connections: 10,
      });
    } catch (err: any) {
      setError(err?.message || "Failed to create connection");
    } finally {
      setSubmitting(false);
    }
  };

  const inputCls =
    "w-full bg-slate-950/60 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-emerald-500/50";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
          <div className="flex items-center space-x-2.5">
            <Database className="w-5 h-5 text-emerald-400" />
            <h2 className="text-sm font-semibold text-slate-100">Add Database Connection</h2>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-xs font-medium text-slate-400 mb-1.5">Name</label>
              <input
                className={inputCls}
                value={form.name}
                onChange={(e) => update("name", e.target.value)}
                placeholder="Production Analytics DB"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5">Database Type</label>
              <select
                className={inputCls}
                value={form.db_type}
                onChange={(e) => update("db_type", e.target.value)}
              >
                {DB_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5">Port</label>
              <input
                className={inputCls}
                value={form.port}
                onChange={(e) => update("port", e.target.value)}
                placeholder="5432"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs font-medium text-slate-400 mb-1.5">Host</label>
              <input
                className={inputCls}
                value={form.host}
                onChange={(e) => update("host", e.target.value)}
                placeholder="db.example.com"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs font-medium text-slate-400 mb-1.5">Database Name</label>
              <input
                className={inputCls}
                value={form.database_name}
                onChange={(e) => update("database_name", e.target.value)}
                placeholder="analytics"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5">Username</label>
              <input
                className={inputCls}
                value={form.username}
                onChange={(e) => update("username", e.target.value)}
                placeholder="postgres"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5">Password</label>
              <input
                type="password"
                className={inputCls}
                value={form.password}
                onChange={(e) => update("password", e.target.value)}
                placeholder="••••••••"
              />
            </div>
          </div>

          <div className="flex items-center justify-between">
            <label className="flex items-center space-x-2 text-xs text-slate-400">
              <input
                type="checkbox"
                checked={form.is_read_only}
                onChange={(e) => update("is_read_only", e.target.checked)}
                className="accent-emerald-500"
              />
              <span>Read-only (enforce SELECT-only)</span>
            </label>
            <label className="flex items-center space-x-2 text-xs text-slate-400">
              <span>Max connections</span>
              <input
                type="number"
                min={1}
                max={50}
                value={form.max_connections}
                onChange={(e) => update("max_connections", Number(e.target.value))}
                className="w-16 bg-slate-950/60 border border-slate-800 rounded px-2 py-1 text-xs text-slate-200"
              />
            </label>
          </div>

          {error && (
            <div className="flex items-center space-x-2 text-xs text-rose-400 bg-rose-950/30 border border-rose-900/50 rounded-lg px-3 py-2">
              <AlertTriangle className="w-3.5 h-3.5" />
              <span>{error}</span>
            </div>
          )}

          {testResult && (
            <div
              className={`flex items-center space-x-2 text-xs rounded-lg px-3 py-2 border ${
                testResult.ok
                  ? "text-emerald-400 bg-emerald-950/30 border-emerald-900/50"
                  : "text-rose-400 bg-rose-950/30 border-rose-900/50"
              }`}
            >
              {testResult.ok ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}
              <span>{testResult.message}</span>
            </div>
          )}

          <div className="flex items-center justify-end space-x-3 pt-2">
            <button
              type="button"
              onClick={handleTest}
              disabled={testing}
              className="px-4 py-2 text-xs font-medium text-slate-300 border border-slate-700 rounded-lg hover:bg-slate-800 transition-colors disabled:opacity-50"
            >
              {testing ? <Loader2 className="w-3.5 h-3.5 animate-spin inline mr-1" /> : null}
              Test Connection
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 text-xs font-medium text-white bg-emerald-600 hover:bg-emerald-500 rounded-lg transition-colors disabled:opacity-50"
            >
              {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin inline mr-1" /> : null}
              Save Connection
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
