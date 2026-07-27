import React, { useEffect, useState } from "react";
import { Database, Plus, Trash2, Layers, Cpu, Hash, RefreshCw, Server, AlertCircle } from "lucide-react";
import { api } from "../../services/api";

export interface CollectionItem {
  id: string;
  name: string;
  tenant_id: string;
  embedding_model: string;
  vector_dimension: number;
  description?: string;
  points_count: number;
  status: "active" | "unreachable";
  created_at?: string;
}

export const CollectionManager: React.FC = () => {
  const [collections, setCollections] = useState<CollectionItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Modal State
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [name, setName] = useState<string>("");
  const [tenantId, setTenantId] = useState<string>("default");
  const [embeddingModel, setEmbeddingModel] = useState<string>("jina-clip-v2");
  const [vectorDimension, setVectorDimension] = useState<number>(1024);
  const [description, setDescription] = useState<string>("");
  const [creating, setCreating] = useState<boolean>(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchCollections = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getCollections();
      setCollections(res.collections || []);
    } catch (err: any) {
      setError(err.message || "Failed to fetch vector collections.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCollections();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    setCreating(true);
    try {
      await api.createCollection({
        name: name.trim().toLowerCase().replace(/\s+/g, "_"),
        tenant_id: tenantId.trim() || "default",
        embedding_model: embeddingModel,
        vector_dimension: Number(vectorDimension),
        description: description.trim() || undefined,
      });

      setShowCreateModal(false);
      setName("");
      setDescription("");
      await fetchCollections();
    } catch (err: any) {
      alert(err.message || "Failed to create collection");
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: string, colName: string) => {
    if (!confirm(`Are you sure you want to delete collection "${colName}"? All vectors will be purged.`)) return;

    setDeletingId(id);
    try {
      await api.deleteCollection(id);
      await fetchCollections();
    } catch (err: any) {
      alert(err.message || "Failed to delete collection");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header bar */}
      <div className="flex items-center justify-between bg-slate-900/60 p-4 rounded-xl border border-slate-800">
        <div>
          <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
            <Database className="w-5 h-5 text-indigo-400" />
            Qdrant Vector Collections
          </h3>
          <p className="text-sm text-slate-400">Manage dynamic multi-tenant vector store collections and schemas.</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchCollections}
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
            title="Refresh list"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-indigo-400" : ""}`} />
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-medium text-sm flex items-center gap-2 transition-all shadow-lg shadow-indigo-600/20"
          >
            <Plus className="w-4 h-4" />
            Create Collection
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-950/40 border border-red-800/50 text-red-300 text-sm flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-red-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Grid of collections */}
      {loading ? (
        <div className="flex items-center justify-center p-12 text-slate-400 text-sm gap-3">
          <RefreshCw className="w-5 h-5 animate-spin text-indigo-400" />
          <span>Loading collections...</span>
        </div>
      ) : collections.length === 0 ? (
        <div className="text-center p-12 bg-slate-900/40 rounded-xl border border-slate-800/80 text-slate-400 space-y-3">
          <Database className="w-10 h-10 mx-auto text-slate-600" />
          <p className="font-medium text-slate-300">No Vector Collections Registered</p>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Create a new vector store collection to organize document embeddings dynamically per tenant or dataset.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {collections.map((col) => (
            <div
              key={col.id}
              className="bg-slate-900/70 border border-slate-800 hover:border-slate-700 rounded-xl p-5 space-y-4 transition-all shadow-md hover:shadow-indigo-950/20 relative group"
            >
              <div className="flex items-start justify-between">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-semibold text-indigo-300">{col.name}</span>
                    <span
                      className={`px-2 py-0.5 text-[10px] font-semibold rounded-full uppercase tracking-wider ${
                        col.status === "active"
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                      }`}
                    >
                      {col.status}
                    </span>
                  </div>
                  {col.description && <p className="text-xs text-slate-400 line-clamp-2">{col.description}</p>}
                </div>
                <button
                  onClick={() => handleDelete(col.id, col.name)}
                  disabled={deletingId === col.id}
                  className="p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-colors opacity-80 group-hover:opacity-100"
                  title="Delete collection"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs border-t border-slate-800/80 pt-3">
                <div className="flex items-center gap-2 text-slate-400">
                  <Server className="w-3.5 h-3.5 text-slate-500" />
                  <span>Tenant:</span>
                  <span className="text-slate-200 font-mono">{col.tenant_id}</span>
                </div>
                <div className="flex items-center gap-2 text-slate-400">
                  <Hash className="w-3.5 h-3.5 text-slate-500" />
                  <span>Vectors:</span>
                  <span className="text-slate-200 font-mono font-semibold">{col.points_count.toLocaleString()}</span>
                </div>
                <div className="flex items-center gap-2 text-slate-400 col-span-2">
                  <Cpu className="w-3.5 h-3.5 text-slate-500" />
                  <span>Model:</span>
                  <span className="text-slate-300 font-mono">{col.embedding_model} ({col.vector_dimension}d)</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal: Create Collection */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 max-w-md w-full space-y-4 shadow-2xl">
            <h4 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
              <Plus className="w-5 h-5 text-indigo-400" />
              Create Vector Collection
            </h4>

            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Collection Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. finance_docs_v1"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 font-mono"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Tenant ID</label>
                  <input
                    type="text"
                    value={tenantId}
                    onChange={(e) => setTenantId(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Dimension</label>
                  <input
                    type="number"
                    value={vectorDimension}
                    onChange={(e) => setVectorDimension(Number(e.target.value))}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Embedding Model</label>
                <input
                  type="text"
                  value={embeddingModel}
                  onChange={(e) => setEmbeddingModel(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Description</label>
                <textarea
                  rows={2}
                  placeholder="Optional dataset description..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-all flex items-center gap-2"
                >
                  {creating && <RefreshCw className="w-4 h-4 animate-spin" />}
                  <span>{creating ? "Creating..." : "Create Collection"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
