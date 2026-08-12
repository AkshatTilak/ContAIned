import { useState, useEffect, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  GitFork,
  Plus,
  Search,
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
import { CreateWorkflowDialog } from "./CreateWorkflowDialog";
import { EmptyState } from "../../shared/EmptyState";
import { ConfirmModal } from "../../shared/ConfirmModal";

export function WorkflowLibrary() {
  const { hubId } = useParams<{ hubId: string }>();
  const navigate = useNavigate();
  const { can, isArchived } = useHubPermissions();

  const [workflows, setWorkflows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [isCreateOpen, setIsCreateOpen] = useState(false);

  const fetchWorkflows = async () => {
    if (!hubId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.workflows.list(hubId);
      setWorkflows(data || []);
    } catch (err: any) {
      setError(err?.message || "Failed to load workflows");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkflows();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hubId]);

  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);
  const addNotification = useStore((state) => state.addNotification);

  const handleDeleteWorkflow = async (wfId: string) => {
    if (!hubId) return;
    try {
      await api.workflows.delete(hubId, wfId);
      addNotification({
        type: "success",
        title: "Workflow Deleted",
        message: "Workflow deleted successfully.",
      });
      setDeleteTarget(null);
      fetchWorkflows();
    } catch (err: any) {
      addNotification({
        type: "error",
        title: "Failed to Delete Workflow",
        message: err?.message || "Error deleting workflow.",
      });
      setDeleteTarget(null);
    }
  };

  const filteredWorkflows = useMemo(() => {
    if (!searchQuery.trim()) return workflows;
    const q = searchQuery.toLowerCase().trim();
    return workflows.filter(
      (w) =>
        w.name.toLowerCase().includes(q) ||
        (w.description && w.description.toLowerCase().includes(q))
    );
  }, [workflows, searchQuery]);

  if (loading) {
    return (
      <div className="p-8 text-center space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mx-auto" />
        <p className="text-sm text-slate-400">Loading Workflow library...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold font-display text-slate-100 flex items-center space-x-2">
            <GitFork className="w-5 h-5 text-indigo-400" />
            <span>Workflow Library</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Visual execution graphs, orchestration nodes, and version releases.
          </p>
        </div>

        {can("create_resource") && !isArchived && (
          <button
            onClick={() => setIsCreateOpen(true)}
            className="flex items-center space-x-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs rounded-xl shadow-lg shadow-indigo-500/20 transition-all shrink-0"
          >
            <Plus className="w-4 h-4" />
            <span>New Workflow</span>
          </button>
        )}
      </div>

      {error && (
        <div className="p-4 bg-red-950/40 border border-red-800/40 rounded-xl text-red-300 text-xs">
          {error}
        </div>
      )}

      <CreateWorkflowDialog
        hubId={hubId || ""}
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onSuccess={(wfId, starterGraph) => {
          setIsCreateOpen(false);
          navigate(routes.workflowHub.editor(hubId || "", wfId), {
            state: starterGraph ? { starterGraph } : undefined,
          });
        }}
      />

      {/* Filter Bar */}
      <div className="flex items-center justify-between gap-3">
        <div className="relative flex-1 w-full max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search workflows by name..."
            className="w-full bg-slate-900/60 border border-slate-800 rounded-xl pl-9 pr-4 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />
        </div>
      </div>

      {/* Workflows Grid */}
      {filteredWorkflows.length === 0 ? (
        <EmptyState
          icon={GitFork}
          title="No Workflows Created"
          description="Design your first multi-node visual graph workflow for complex task orchestration and version releases."
          actionLabel={can("create_resource") && !isArchived ? "Create Workflow" : undefined}
          onAction={() => setIsCreateOpen(true)}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredWorkflows.map((wf) => (
            <div
              key={wf.id}
              onClick={() => navigate(routes.workflowHub.editor(hubId || "", wf.id))}
              className="p-5 bg-slate-900/50 hover:bg-slate-900/80 border border-slate-800/80 hover:border-indigo-500/40 rounded-xl space-y-4 flex flex-col justify-between cursor-pointer transition-all shadow-lg"
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0">
                      <GitFork className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-bold text-slate-100 text-base font-display">{wf.name}</h3>
                      <p className="text-xs font-mono text-slate-500">{wf.id.slice(0, 12)}</p>
                    </div>
                  </div>
                </div>

                {wf.description && (
                  <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
                    {wf.description}
                  </p>
                )}
              </div>

              <div className="pt-3 border-t border-slate-800/60 flex items-center justify-between text-xs font-mono text-slate-400">
                <span className="px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-800/40 text-[10px]">
                  Published
                </span>

                <div className="flex items-center space-x-1" onClick={(e) => e.stopPropagation()}>
                  {can("delete_resource") && !isArchived && (
                    <button
                      onClick={() => setDeleteTarget({ id: wf.id, name: wf.name })}
                      className="p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-950/40 transition-colors"
                      title="Delete Workflow"
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
        title="Delete Workflow"
        message={`Are you sure you want to delete workflow "${deleteTarget?.name}"? All execution history will be removed.`}
        confirmLabel="Delete Workflow"
        cancelLabel="Cancel"
        isDanger={true}
        onConfirm={() => deleteTarget && handleDeleteWorkflow(deleteTarget.id)}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
