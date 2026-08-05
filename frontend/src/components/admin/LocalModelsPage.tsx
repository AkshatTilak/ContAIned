import { useEffect, useState } from "react";
import { Loader2, Play, Square, AlertCircle, Box, Cpu, Trash2 } from "lucide-react";
import { api } from "../../services/api";

export function LocalModelsPage() {
  const [models, setModels] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  
  // Delete Modal State
  const [deleteTarget, setDeleteTarget] = useState<any | null>(null);
  const [purgeDisk, setPurgeDisk] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const fetchModels = async () => {
    try {
      const res = await api.localModels.status();
      setModels(res.items || []);
    } catch (err: any) {
      setError(err?.message || "Failed to load local models status.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchModels();
  }, []);

  const handleStart = async (modelId: string) => {
    setActionLoading(modelId);
    setError(null);
    try {
      await api.localModels.start(modelId);
      await fetchModels();
    } catch (err: any) {
      setError(`Failed to start ${modelId}: ${err?.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleStop = async (modelId: string) => {
    setActionLoading(modelId);
    setError(null);
    try {
      await api.localModels.stop(modelId);
      await fetchModels();
    } catch (err: any) {
      setError(`Failed to stop ${modelId}: ${err?.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    setError(null);
    try {
      await api.localModels.purgeLocal(deleteTarget.model_id, purgeDisk);
      setDeleteTarget(null);
      setPurgeDisk(false);
      await fetchModels();
    } catch (err: any) {
      setError(`Failed to delete model ${deleteTarget.model_id}: ${err?.message}`);
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center p-8">
        <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-200 flex items-center space-x-2">
            <Box className="w-5 h-5 text-indigo-400" />
            <span>Local Models Management</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">Manage local GPU models, check disk cache, and load them into VRAM manually.</p>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-950/40 border border-red-800/40 rounded-xl text-red-300 text-xs flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {models.map((m) => (
          <div key={m.model_id} className="bg-slate-900/40 border border-slate-800 rounded-xl p-5 flex flex-col justify-between space-y-4 hover:border-slate-700/80 transition-colors">
            <div className="flex justify-between items-start">
              <div>
                <h3 className="text-sm font-semibold text-slate-200">{m.display_name}</h3>
                <p className="text-xs text-slate-400 font-mono mt-0.5">{m.model_id}</p>
                <div className="flex items-center space-x-2 mt-2">
                  <span className="px-2 py-0.5 rounded-full bg-slate-800 border border-slate-700 text-[10px] uppercase text-slate-300 font-semibold tracking-wider">
                    {m.role}
                  </span>
                  <span className="flex items-center space-x-1 text-xs text-slate-500">
                    <Cpu className="w-3.5 h-3.5" />
                    <span>~{m.vram_mb} MB</span>
                  </span>
                </div>
              </div>
              <div className={`px-2.5 py-1 rounded-full text-xs font-semibold ${m.is_running ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-slate-800 text-slate-400 border border-slate-700'}`}>
                {m.is_running ? "Running" : "Stopped"}
              </div>
            </div>

            {/* Local Disk Storage Path & Cache Status */}
            <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-2.5 space-y-1.5 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Disk Storage Path</span>
                <span className={`text-[10px] font-medium px-2 py-0.5 rounded ${m.is_downloaded ? 'bg-emerald-950/40 text-emerald-400 border border-emerald-900/50' : 'bg-amber-950/40 text-amber-400 border border-amber-900/50'}`}>
                  {m.is_downloaded ? "Cached on Disk" : "Not Downloaded"}
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-mono truncate select-all" title={m.local_path}>
                {m.local_path || "Path unresolved"}
              </p>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-slate-800/50">
              <button
                onClick={() => {
                  setDeleteTarget(m);
                  setPurgeDisk(false);
                }}
                className="flex items-center space-x-1 text-slate-500 hover:text-red-400 text-xs px-2 py-1 rounded hover:bg-red-950/30 transition-colors"
                title="Delete Model from Registry"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Delete</span>
              </button>

              <div className="flex space-x-2">
                {m.is_running ? (
                  <button
                    onClick={() => handleStop(m.model_id)}
                    disabled={actionLoading === m.model_id}
                    className="flex items-center space-x-1.5 px-3 py-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 font-medium text-xs rounded-lg transition-colors disabled:opacity-50"
                  >
                    {actionLoading === m.model_id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Square className="w-3.5 h-3.5" />}
                    <span>Stop</span>
                  </button>
                ) : (
                  <button
                    onClick={() => handleStart(m.model_id)}
                    disabled={actionLoading === m.model_id}
                    className="flex items-center space-x-1.5 px-3 py-1.5 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 font-medium text-xs rounded-lg transition-colors border border-indigo-500/30 disabled:opacity-50"
                  >
                    {actionLoading === m.model_id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5 fill-current" />}
                    <span>Start Model</span>
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}

        {models.length === 0 && (
          <div className="col-span-full p-8 text-center text-xs text-slate-500 bg-slate-900/20 rounded-xl border border-slate-800/50">
            No local models found in the registry.
          </div>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      {deleteTarget && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center space-x-3 text-red-400">
              <Trash2 className="w-6 h-6" />
              <h3 className="text-base font-semibold text-slate-100">Delete Model Registry Entry</h3>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              Are you sure you want to remove <strong className="text-slate-100 font-mono">{deleteTarget.display_name}</strong> (<span className="text-slate-400">{deleteTarget.model_id}</span>) from the model registry?
            </p>

            {deleteTarget.is_downloaded && (
              <label className="flex items-center space-x-2.5 p-3 bg-slate-950/60 border border-slate-800 rounded-xl cursor-pointer hover:border-slate-700 transition-colors">
                <input
                  type="checkbox"
                  checked={purgeDisk}
                  onChange={(e) => setPurgeDisk(e.target.checked)}
                  className="w-4 h-4 rounded text-red-500 focus:ring-red-500 bg-slate-900 border-slate-700"
                />
                <div className="text-xs">
                  <span className="font-semibold text-red-300 block">Purge cached model files from local disk</span>
                  <span className="text-[10px] text-slate-400 font-mono truncate block max-w-xs">{deleteTarget.local_path}</span>
                </div>
              </label>
            )}

            <div className="flex justify-end space-x-3 pt-2">
              <button
                onClick={() => {
                  setDeleteTarget(null);
                  setPurgeDisk(false);
                }}
                disabled={deleting}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-xl transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                disabled={deleting}
                className="flex items-center space-x-1.5 px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-xs font-medium rounded-xl transition-colors disabled:opacity-50"
              >
                {deleting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <span>{deleting ? "Deleting..." : "Confirm Delete"}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
