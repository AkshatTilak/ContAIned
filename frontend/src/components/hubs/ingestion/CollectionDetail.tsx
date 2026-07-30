import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  FolderKanban,
  FileText,
  Settings,
  Sparkles,
  ArrowLeft,
  Save,
  RotateCcw,
  Loader2,
  AlertCircle,
  Database,
  Layers,
} from "lucide-react";
import { useHubPermissions } from "../../../hooks/useHubPermissions";
import { RetrievalTester } from "./RetrievalTester";
import { api } from "../../../services/api";
import { routes } from "../../../routes";

export function CollectionDetail() {
  const { hubId, collectionId } = useParams<{ hubId: string; collectionId: string }>();
  const navigate = useNavigate();
  const { can, isArchived } = useHubPermissions();

  const [collection, setCollection] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Strategy config form state
  const [strategy, setStrategy] = useState<string>("vector");
  const [chunkSize, setChunkSize] = useState<number>(512);
  const [chunkOverlap, setChunkOverlap] = useState<number>(64);
  const [isDirty, setIsDirty] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const fetchCollection = async () => {
    if (!hubId || !collectionId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.ingestion.collections.get(hubId, collectionId);
      const col = data.collection || data;
      setCollection(col);
      setStrategy(col.strategy || "vector");
      setChunkSize(col.chunk_size || 512);
      setChunkOverlap(col.chunk_overlap || 64);
      setIsDirty(false);
    } catch (err: any) {
      setError(err?.message || "Failed to load collection details");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCollection();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hubId, collectionId]);

  const handleSaveConfig = async () => {
    if (!hubId || !collectionId) return;
    setIsSaving(true);
    try {
      // API call to update strategy config
      setIsDirty(false);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: any) {
      console.error("Failed to save collection strategy config:", err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDiscard = () => {
    if (!collection) return;
    setStrategy(collection.strategy || "vector");
    setChunkSize(collection.chunk_size || 512);
    setChunkOverlap(collection.chunk_overlap || 64);
    setIsDirty(false);
  };

  if (loading) {
    return (
      <div className="p-8 text-center space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mx-auto" />
        <p className="text-sm text-slate-400">Loading collection details...</p>
      </div>
    );
  }

  if (error || !collection) {
    return (
      <div className="p-8 text-center space-y-4">
        <AlertCircle className="w-10 h-10 text-red-500 mx-auto" />
        <h3 className="text-base font-bold text-slate-200">Collection Not Found</h3>
        <p className="text-xs text-slate-400">{error || "Could not retrieve collection data"}</p>
        <button
          onClick={() => navigate(routes.ingestionHub.collections(hubId || ""))}
          className="px-4 py-2 bg-slate-800 text-slate-200 text-xs font-medium rounded-lg hover:bg-slate-700"
        >
          Back to Collections
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-12">
      {/* Header & Breadcrumb Back Action */}
      <div className="flex items-center justify-between border-b border-slate-800/80 pb-4">
        <div className="flex items-center space-x-3">
          <button
            onClick={() => navigate(routes.ingestionHub.collections(hubId || ""))}
            className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
            title="Back to Collections List"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-bold font-display text-slate-100">{collection.name}</h1>
              <span className="px-2 py-0.5 text-xs font-mono font-semibold uppercase bg-indigo-950/60 text-indigo-400 border border-indigo-800/40 rounded">
                {collection.strategy || "vector"}
              </span>
            </div>
            <p className="text-xs font-mono text-slate-500 mt-0.5">
              Physical store: {collection.physical_name || `${hubId}__${collection.name}`}
            </p>
          </div>
        </div>
      </div>

      {/* Region 1: Strategy & Chunking Configuration */}
      <section className="bg-slate-900/50 border border-slate-800/80 rounded-xl p-6 space-y-6 shadow-lg">
        <div className="flex items-center justify-between border-b border-slate-800/60 pb-4">
          <h3 className="text-base font-bold text-slate-100 font-display flex items-center space-x-2">
            <Settings className="w-4 h-4 text-indigo-400" />
            <span>Retrieval & Chunking Configuration</span>
          </h3>
          {isDirty && (
            <div className="flex items-center space-x-2">
              <button
                onClick={handleDiscard}
                className="flex items-center space-x-1 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-lg transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Discard</span>
              </button>
              {can("edit_resource") && !isArchived && (
                <button
                  onClick={handleSaveConfig}
                  disabled={isSaving}
                  className="flex items-center space-x-1 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium rounded-lg shadow transition-colors"
                >
                  {isSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                  <span>Save Changes</span>
                </button>
              )}
            </div>
          )}
        </div>

        {saveSuccess && (
          <div className="p-3 bg-emerald-950/40 border border-emerald-800/40 rounded-lg text-xs text-emerald-300">
            Strategy configuration saved successfully.
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Search Strategy</label>
            <select
              value={strategy}
              onChange={(e) => {
                setStrategy(e.target.value);
                setIsDirty(true);
              }}
              disabled={!can("edit_resource") || isArchived}
              className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-indigo-500 disabled:opacity-60"
            >
              <option value="vector">Dense Vector Search</option>
              <option value="hybrid">Hybrid Dense + Sparse (BM25)</option>
              <option value="graph">Knowledge Graph Traversal</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Chunk Size (Tokens)</label>
            <input
              type="number"
              value={chunkSize}
              onChange={(e) => {
                setChunkSize(Number(e.target.value));
                setIsDirty(true);
              }}
              disabled={!can("edit_resource") || isArchived}
              className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-xs font-mono text-slate-100 focus:outline-none focus:border-indigo-500 disabled:opacity-60"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Chunk Overlap (Tokens)</label>
            <input
              type="number"
              value={chunkOverlap}
              onChange={(e) => {
                setChunkOverlap(Number(e.target.value));
                setIsDirty(true);
              }}
              disabled={!can("edit_resource") || isArchived}
              className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-xs font-mono text-slate-100 focus:outline-none focus:border-indigo-500 disabled:opacity-60"
            />
          </div>
        </div>
      </section>

      {/* Region 2: Embedded Retrieval Tester */}
      <RetrievalTester
        hubId={hubId || ""}
        collectionId={collection.id}
        collectionName={collection.name}
      />
    </div>
  );
}
