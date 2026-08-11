import { useState, useEffect, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Sparkles,
  Plus,
  Search,
  Trash2,
  Play,
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
import { EmptyState } from "../../shared/EmptyState";
import { ConfirmModal } from "../../shared/ConfirmModal";

export function SuiteManager() {
  const { hubId } = useParams<{ hubId: string }>();
  const navigate = useNavigate();
  const { can, isArchived } = useHubPermissions();

  const [suites, setSuites] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [targetType, setTargetType] = useState<"agent" | "workflow">("agent");
  const [submitting, setSubmitting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const fetchSuites = async () => {
    if (!hubId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.evals.suites.list(hubId);
      setSuites(data || []);
    } catch (err: any) {
      setError(err?.message || "Failed to load evaluation suites");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSuites();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hubId]);

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!hubId || !name.trim()) return;

    setSubmitting(true);
    setCreateError(null);
    try {
      await api.evals.suites.create(hubId, {
        name: name.trim(),
        description,
        target_type: targetType,
      });
      setIsCreateOpen(false);
      setName("");
      fetchSuites();
    } catch (err: any) {
      setCreateError(err?.message || "Failed to create eval suite");
    } finally {
      setSubmitting(false);
    }
  };

  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);
  const addNotification = useStore((state) => state.addNotification);

  const handleDeleteSuite = async (suiteId: string) => {
    if (!hubId) return;
    try {
      await api.evals.suites.delete(hubId, suiteId);
      addNotification({
        type: "success",
        title: "Eval Suite Deleted",
        message: "Evaluation suite deleted successfully.",
      });
      setDeleteTarget(null);
      fetchSuites();
    } catch (err: any) {
      addNotification({
        type: "error",
        title: "Failed to Delete Suite",
        message: err?.message || "Error deleting eval suite.",
      });
      setDeleteTarget(null);
    }
  };

  const filteredSuites = useMemo(() => {
    if (!searchQuery.trim()) return suites;
    const q = searchQuery.toLowerCase().trim();
    return suites.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        (s.description && s.description.toLowerCase().includes(q))
    );
  }, [suites, searchQuery]);

  if (loading) {
    return (
      <div className="p-8 text-center space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mx-auto" />
        <p className="text-sm text-slate-400">Loading Evaluation suites...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold font-display text-slate-100 flex items-center space-x-2">
            <Sparkles className="w-5 h-5 text-indigo-400" />
            <span>Evaluation Suites</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Polymorphic evaluation benchmark suites targeting Agents or Workflows.
          </p>
        </div>

        {can("create_resource") && !isArchived && (
          <button
            onClick={() => setIsCreateOpen(true)}
            className="flex items-center space-x-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs rounded-xl shadow-lg shadow-indigo-500/20 transition-all shrink-0"
          >
            <Plus className="w-4 h-4" />
            <span>New Suite</span>
          </button>
        )}
      </div>

      {error && (
        <div className="p-4 bg-red-950/40 border border-red-800/40 rounded-xl text-red-300 text-xs">
          {error}
        </div>
      )}

      {/* Create Modal Form */}
      {isCreateOpen && (
        <form onSubmit={handleCreateSubmit} className="p-6 bg-slate-900/90 border border-indigo-500/40 rounded-2xl space-y-4 shadow-2xl">
          <h3 className="text-base font-bold text-slate-100 font-display">Create Evaluation Suite</h3>
          {createError && <p className="text-xs text-red-400">{createError}</p>}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Suite Name *</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="RAG QA Benchmark Suite"
                required
                className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Target Type</label>
              <select
                value={targetType}
                onChange={(e) => setTargetType(e.target.value as any)}
                className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
              >
                <option value="agent">Agent Target</option>
                <option value="workflow">Workflow Graph Target</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Description</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Ground truth evaluation suite for customer service bot..."
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
              disabled={submitting || !name.trim()}
              className="px-4 py-2 bg-indigo-600 text-white text-xs font-medium rounded-xl hover:bg-indigo-500 flex items-center space-x-1"
            >
              {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
              <span>Create Suite</span>
            </button>
          </div>
        </form>
      )}

      {/* Filter Bar */}
      <div className="flex items-center justify-between gap-3">
        <div className="relative flex-1 w-full max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search evaluation suites by name..."
            className="w-full bg-slate-900/60 border border-slate-800 rounded-xl pl-9 pr-4 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />
        </div>
      </div>

      {/* Suites Grid */}
      {filteredSuites.length === 0 ? (
        <EmptyState
          icon={Sparkles}
          title="No Evaluation Suites"
          description="Create your first polymorphic benchmark suite to test Agent outputs and Workflow trace assertions."
          actionLabel={can("create_resource") && !isArchived ? "New Suite" : undefined}
          onAction={() => setIsCreateOpen(true)}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredSuites.map((s) => (
            <div
              key={s.id}
              onClick={() => navigate(routes.evalHub.suite(hubId || "", s.id))}
              className="p-5 bg-slate-900/50 hover:bg-slate-900/80 border border-slate-800/80 hover:border-indigo-500/40 rounded-xl space-y-4 flex flex-col justify-between cursor-pointer transition-all shadow-lg"
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0">
                      <Sparkles className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-bold text-slate-100 text-base font-display">{s.name}</h3>
                      <p className="text-xs font-mono text-slate-500">Target: {s.target_type}</p>
                    </div>
                  </div>
                </div>

                {s.description && (
                  <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
                    {s.description}
                  </p>
                )}
              </div>

              <div className="pt-3 border-t border-slate-800/60 flex items-center justify-between text-xs font-mono text-slate-400">
                <span className="px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-800/40 text-[10px]">
                  Score: 0.92
                </span>

                <div className="flex items-center space-x-1" onClick={(e) => e.stopPropagation()}>
                  {can("delete_resource") && !isArchived && (
                    <button
                      onClick={() => setDeleteTarget({ id: s.id, name: s.name })}
                      className="p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-950/40 transition-colors"
                      title="Delete Suite"
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

      <ConfirmModal
        isOpen={Boolean(deleteTarget)}
        title="Delete Eval Suite"
        message={`Are you sure you want to delete evaluation suite "${deleteTarget?.name}"? All associated test cases and test run metrics will be permanently removed.`}
        confirmLabel="Delete Suite"
        cancelLabel="Cancel"
        isDanger={true}
        onConfirm={() => deleteTarget && handleDeleteSuite(deleteTarget.id)}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
