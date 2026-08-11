import { useState, useEffect, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  FolderKanban,
  Plus,
  Search,
  Database,
  Trash2,
  Edit2,
  ArrowUpDown,
  Check,
  AlertCircle,
  Loader2,
  ExternalLink,
} from "lucide-react";
import { useHubPermissions } from "../../../hooks/useHubPermissions";
import { api } from "../../../services/api";
import { routes } from "../../../routes";
import { useStore } from "../../../store/useStore";
import { ModelSelector } from "../../shared/ModelSelector";
import { ConfirmModal } from "../../shared/ConfirmModal";

export function CollectionsWorkspace() {
  const { hubId } = useParams<{ hubId: string }>();
  const navigate = useNavigate();
  const { can, isArchived } = useHubPermissions();

  const [collections, setCollections] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [strategyFilter, setStrategyFilter] = useState("all");
  const [sortBy, setSortBy] = useState<"name" | "vectors" | "date">("name");

  // Create Modal state
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [embeddingModel, setEmbeddingModel] = useState("text-embedding-3-small");
  const [dimension, setDimension] = useState(1536);
  const [strategy, setStrategy] = useState("vector");
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [datastores, setDatastores] = useState<any[]>([]);
  const [datastoreId, setDatastoreId] = useState("");
  const [availableModels, setAvailableModels] = useState<{ id: string; name: string; provider: string; is_selectable?: boolean }[]>([]);

  const fetchData = async () => {
    if (!hubId) return;
    setLoading(true);
    setError(null);
    try {
      const [colRes, dsRes, modRes] = await Promise.all([
        api.ingestion.collections.list(hubId),
        api.ingestion.datastores.list(hubId),
        api.getModels().catch(() => ({})), // Fallback to empty if error
      ]);
      const listData = Array.isArray(colRes) ? colRes : (colRes.collections || (colRes as any).items || []);
      setCollections(listData);
      setDatastores(dsRes || []);
      if (dsRes && dsRes.length > 0) {
        setDatastoreId(dsRes[0].id);
      }
      
      const items: { id: string; name: string; provider: string; is_selectable?: boolean }[] = [];
      const embeddingObj = (modRes as any).embedding;
      if (embeddingObj) {
        if (embeddingObj.active) {
          items.push({
            id: embeddingObj.active.model_id,
            name: embeddingObj.active.display_name,
            provider: embeddingObj.active.provider,
            is_selectable: embeddingObj.active.is_selectable,
          });
        }
        embeddingObj.available?.forEach((entry: any) => {
          if (!items.some((m) => m.id === entry.model_id)) {
            items.push({
              id: entry.model_id,
              name: entry.display_name,
              provider: entry.provider,
              is_selectable: entry.is_selectable,
            });
          }
        });
      }
      if (items.length > 0) {
        setAvailableModels(items);
        setEmbeddingModel(items[0].id);
      }
    } catch (err: any) {
      setError(err?.message || "Failed to load workspace data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hubId]);

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!hubId || !name.trim()) return;

    setCreateSubmitting(true);
    setCreateError(null);
    try {
      await api.ingestion.collections.create(hubId, {
        name: name.trim(),
        description,
        embedding_model: embeddingModel,
        vector_dimension: dimension,
        strategy,
        datastore_binding_id: datastoreId || undefined,
      });
      setIsCreateOpen(false);
      setName("");
      setDescription("");
      fetchData();
    } catch (err: any) {
      setCreateError(err?.message || "Failed to create collection");
    } finally {
      setCreateSubmitting(false);
    }
  };

  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);
  const [forceDeleteTarget, setForceDeleteTarget] = useState<{ id: string; name: string } | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const addNotification = useStore((state) => state.addNotification);

  const handleDeleteCollection = async (collectionId: string, force: boolean = false) => {
    if (!hubId) return;
    setIsDeleting(true);
    try {
      await api.ingestion.collections.delete(hubId, collectionId, force);
      addNotification({
        type: "success",
        title: "Collection Deleted",
        message: force ? "Collection and all contained documents force deleted." : "Collection deleted successfully.",
      });
      setDeleteTarget(null);
      setForceDeleteTarget(null);
      fetchData();
    } catch (err: any) {
      const msg = err?.message || "";
      if (!force && (err?.status === 409 || msg.toLowerCase().includes("not empty"))) {
        const name = deleteTarget?.name || collections.find((c) => c.id === collectionId)?.name || "Collection";
        setDeleteTarget(null);
        setForceDeleteTarget({ id: collectionId, name });
      } else {
        addNotification({
          type: "error",
          title: "Failed to Delete Collection",
          message: msg || "An unexpected error occurred",
        });
        setDeleteTarget(null);
        setForceDeleteTarget(null);
      }
    } finally {
      setIsDeleting(false);
    }
  };

  const filteredCollections = useMemo(() => {
    let result = collections;

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      result = result.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          (c.description && c.description.toLowerCase().includes(q))
      );
    }

    if (strategyFilter !== "all") {
      result = result.filter((c) => (c.strategy || "vector") === strategyFilter);
    }

    return result.sort((a, b) => {
      if (sortBy === "vectors") return (b.vector_count || 0) - (a.vector_count || 0);
      if (sortBy === "date")
        return new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime();
      return a.name.localeCompare(b.name);
    });
  }, [collections, searchQuery, strategyFilter, sortBy]);

  if (loading) {
    return (
      <div className="p-8 text-center space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mx-auto" />
        <p className="text-sm text-slate-400">Loading vector collections...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold font-display text-slate-100 flex items-center space-x-2">
            <FolderKanban className="w-5 h-5 text-indigo-400" />
            <span>Vector Collections</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Dynamic vector store collections bound to this Ingestion Hub.
          </p>
        </div>

        {can("create_resource") && !isArchived && (
          <button
            onClick={() => setIsCreateOpen(true)}
            className="flex items-center space-x-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs rounded-xl shadow-lg shadow-indigo-500/20 transition-all shrink-0"
          >
            <Plus className="w-4 h-4" />
            <span>New Collection</span>
          </button>
        )}
      </div>

      {error && (
        <div className="p-4 bg-red-950/40 border border-red-800/40 rounded-xl text-red-300 text-xs flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Create Modal Form */}
      {isCreateOpen && (
        <form onSubmit={handleCreateSubmit} className="p-6 bg-slate-900/90 border border-indigo-500/40 rounded-2xl space-y-4 shadow-2xl">
          <h3 className="text-base font-bold text-slate-100 font-display">Create Vector Collection</h3>
          {createError && <p className="text-xs text-red-400">{createError}</p>}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Collection Name *</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="kb-documents"
                required
                className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div className="col-span-full">
              <label className="block text-xs font-semibold text-slate-300 mb-2">Embedding Model Config</label>
              <ModelSelector
                value={embeddingModel}
                onChange={(val) => {
                  setEmbeddingModel(val);
                  const lowerVal = val.toLowerCase();
                  if (lowerVal.includes("small") || lowerVal.includes("bge") || lowerVal.includes("1536")) setDimension(1536);
                  else if (lowerVal.includes("large") || lowerVal.includes("3072")) setDimension(3072);
                  else if (lowerVal.includes("harrier") || lowerVal.includes("768")) setDimension(768);
                  else if (lowerVal.includes("clip") || lowerVal.includes("1024")) setDimension(1024);
                  else setDimension(768);
                }}
                role="embedding"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Datastore Binding</label>
              <select
                value={datastoreId}
                onChange={(e) => setDatastoreId(e.target.value)}
                className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
              >
                {datastores.map((ds) => {
                  const isOffline = ds.health_status === "unhealthy" || ds.health_status === "unreachable";
                  return (
                    <option key={ds.id} value={ds.id} disabled={isOffline}>
                      {ds.name} ({ds.store_type || ds.datastore_type || "qdrant"}) — [{ds.health_status || "healthy"}]
                    </option>
                  );
                })}
                {datastores.length === 0 && (
                  <option value="" disabled>Platform Default (Qdrant)</option>
                )}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Description</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Primary knowledge base for customer support..."
              className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div className="flex justify-end space-x-2 pt-2">
            <button
              type="button"
              onClick={() => setIsCreateOpen(false)}
              className="px-4 py-2 bg-slate-800 text-slate-300 text-xs font-medium rounded-xl hover:bg-slate-700"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createSubmitting || !name.trim()}
              className="px-4 py-2 bg-indigo-600 text-white text-xs font-medium rounded-xl hover:bg-indigo-500 flex items-center space-x-1"
            >
              {createSubmitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
              <span>Create Collection</span>
            </button>
          </div>
        </form>
      )}

      {/* Filter & Sort Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="relative flex-1 w-full max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search collections by name..."
            className="w-full bg-slate-900/60 border border-slate-800 rounded-xl pl-9 pr-4 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />
        </div>

        <div className="flex items-center space-x-3 text-xs">
          <div className="flex items-center space-x-1 bg-slate-900 border border-slate-800 rounded-lg px-2 py-1">
            <span className="text-slate-500">Strategy:</span>
            <select
              value={strategyFilter}
              onChange={(e) => setStrategyFilter(e.target.value)}
              className="bg-transparent text-slate-200 focus:outline-none text-xs cursor-pointer"
            >
              <option value="all" className="bg-slate-900">All Strategies</option>
              <option value="vector" className="bg-slate-900">Vector</option>
              <option value="hybrid" className="bg-slate-900">Hybrid</option>
              <option value="graph" className="bg-slate-900">Graph</option>
            </select>
          </div>

          <div className="flex items-center space-x-1 bg-slate-900 border border-slate-800 rounded-lg px-2 py-1">
            <ArrowUpDown className="w-3.5 h-3.5 text-slate-500" />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="bg-transparent text-slate-200 focus:outline-none text-xs cursor-pointer"
            >
              <option value="name" className="bg-slate-900">Name</option>
              <option value="vectors" className="bg-slate-900">Vector Count</option>
              <option value="date" className="bg-slate-900">Date Created</option>
            </select>
          </div>
        </div>
      </div>

      {/* Collections Grid */}
      {filteredCollections.length === 0 ? (
        <div className="p-12 text-center border border-slate-800/60 bg-slate-900/30 rounded-2xl text-slate-500 text-xs">
          No collections found in this hub.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredCollections.map((col) => (
            <div
              key={col.id}
              className="p-5 bg-slate-900/50 hover:bg-slate-900/80 border border-slate-800/80 rounded-xl space-y-4 flex flex-col justify-between transition-all"
            >
              <div className="space-y-2">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-bold text-slate-100 text-base font-display flex items-center space-x-2">
                      <span>{col.name}</span>
                    </h3>
                    <p className="text-[11px] font-mono text-slate-500">
                      Physical: {col.physical_name || `${hubId}__${col.name}`}
                    </p>
                  </div>
                  <span className="px-2 py-0.5 rounded text-[10px] font-semibold uppercase font-mono bg-indigo-950/60 text-indigo-400 border border-indigo-800/40">
                    {col.strategy || "vector"}
                  </span>
                </div>

                {col.description && (
                  <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
                    {col.description}
                  </p>
                )}
              </div>

              <div className="space-y-3 pt-3 border-t border-slate-800/60 text-xs text-slate-400">
                <div className="flex items-center justify-between font-mono">
                  <span>Vectors:</span>
                  <span className="font-bold text-slate-200">{col.vector_count || 0}</span>
                </div>
                <div className="flex items-center justify-between font-mono">
                  <span>Embedding:</span>
                  <span className="text-slate-300 truncate max-w-[150px]">
                    {col.embedding_model || "text-embedding-3-small"}
                  </span>
                </div>

                <div className="flex items-center justify-between pt-2">
                  <button
                    onClick={() => navigate(routes.ingestionHub.collection(hubId || "", col.id))}
                    className="flex items-center space-x-1 text-indigo-400 hover:text-indigo-300 text-xs font-semibold"
                  >
                    <span>View Detail & Tester</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </button>

                  {can("delete_resource") && !isArchived && (
                    <button
                      onClick={() => setDeleteTarget({ id: col.id, name: col.name })}
                      className="p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-950/40 transition-colors"
                      title="Delete Collection"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Standard Delete Modal */}
      <ConfirmModal
        isOpen={Boolean(deleteTarget)}
        title="Delete Collection"
        message={`Are you sure you want to delete collection "${deleteTarget?.name}"? This action cannot be undone.`}
        confirmLabel="Delete Collection"
        cancelLabel="Cancel"
        isDanger={true}
        isLoading={isDeleting}
        onConfirm={() => deleteTarget && handleDeleteCollection(deleteTarget.id, false)}
        onCancel={() => setDeleteTarget(null)}
      />

      {/* Force Delete Modal for 409 Conflict (non-empty collection) */}
      <ConfirmModal
        isOpen={Boolean(forceDeleteTarget)}
        title="Force Delete Collection"
        message={`Collection "${forceDeleteTarget?.name}" is not empty. Do you want to FORCE delete this collection along with all documents and vector embeddings inside it?`}
        confirmLabel="Force Delete All"
        cancelLabel="Cancel"
        isDanger={true}
        isLoading={isDeleting}
        onConfirm={() => forceDeleteTarget && handleDeleteCollection(forceDeleteTarget.id, true)}
        onCancel={() => setForceDeleteTarget(null)}
      />
    </div>
  );
}
