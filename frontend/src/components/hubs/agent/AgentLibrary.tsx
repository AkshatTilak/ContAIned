import { useState, useEffect, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Bot,
  Plus,
  Search,
  Trash2,
  Copy,
  ToggleLeft,
  ToggleRight,
  ArrowUpDown,
  Check,
  AlertCircle,
  Loader2,
  ExternalLink,
} from "lucide-react";
import { useHubPermissions } from "../../../hooks/useHubPermissions";
import { api } from "../../../services/api";
import { routes } from "../../../routes";
import type { AgentResponse } from "../../../types/api";
import { EmptyState } from "../../shared/EmptyState";
import { ModelSelector } from "../../shared/ModelSelector";

export function AgentLibrary() {
  const { hubId } = useParams<{ hubId: string }>();
  const navigate = useNavigate();
  const { can, isArchived } = useHubPermissions();

  const [agents, setAgents] = useState<AgentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortBy, setSortBy] = useState<"name" | "model" | "date">("name");

  // Create Modal state
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [name, setName] = useState("");
  const [role, setRole] = useState("Assistant");
  const [endpointSlug, setEndpointSlug] = useState("");
  const [modelId, setModelId] = useState("gpt-4o");
  const [systemPrompt, setSystemPrompt] = useState("You are a helpful AI assistant.");
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [availableModels, setAvailableModels] = useState<{ id: string; name: string; provider: string; is_selectable?: boolean }[]>([]);

  useEffect(() => {
    const fetchModels = async () => {
      try {
        const reg = await api.getModels();
        const items: { id: string; name: string; provider: string; is_selectable?: boolean }[] = [];
        Object.values(reg).forEach((roleObj: any) => {
          if (roleObj.active) {
            items.push({
              id: roleObj.active.model_id,
              name: roleObj.active.display_name,
              provider: roleObj.active.provider,
              is_selectable: roleObj.active.is_selectable,
            });
          }
          roleObj.available?.forEach((entry: any) => {
            if (!items.some((m) => m.id === entry.model_id)) {
              items.push({
                id: entry.model_id,
                name: entry.display_name,
                provider: entry.provider,
                is_selectable: entry.is_selectable,
              });
            }
          });
        });
        if (items.length > 0) setAvailableModels(items);
      } catch (err) {}
    };
    fetchModels();
  }, []);

  const fetchAgents = async () => {
    if (!hubId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.agents.list(hubId);
      setAgents(data || []);
    } catch (err: any) {
      setError(err?.message || "Failed to load hub agents");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAgents();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hubId]);

  // Auto-derive endpoint slug from name
  useEffect(() => {
    if (name) {
      const slugified = name
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "");
      setEndpointSlug(slugified);
    }
  }, [name]);

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!hubId || !name.trim()) return;

    setCreateSubmitting(true);
    setCreateError(null);
    try {
      await api.agents.create(hubId, {
        name: name.trim(),
        role,
        system_prompt: systemPrompt,
        model_id: modelId,
      });
      setIsCreateOpen(false);
      setName("");
      fetchAgents();
    } catch (err: any) {
      setCreateError(err?.message || "Failed to create agent");
    } finally {
      setCreateSubmitting(false);
    }
  };

  const handleToggleActive = async (agent: AgentResponse) => {
    if (!hubId) return;
    try {
      await api.agents.update(hubId, agent.id, {
        name: agent.name,
      });
      fetchAgents();
    } catch (err: any) {
      console.error("Failed to toggle agent active state:", err);
    }
  };

  const handleDeleteAgent = async (agentId: string) => {
    if (!hubId) return;
    try {
      await api.agents.delete(hubId, agentId);
      fetchAgents();
    } catch (err: any) {
      console.error("Failed to delete agent:", err);
    }
  };

  const filteredAgents = useMemo(() => {
    let result = agents;

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      result = result.filter(
        (a) =>
          a.name.toLowerCase().includes(q) ||
          a.role.toLowerCase().includes(q) ||
          (a.endpoint_slug && a.endpoint_slug.toLowerCase().includes(q))
      );
    }

    if (statusFilter === "active") {
      result = result.filter((a) => a.is_active !== false);
    } else if (statusFilter === "disabled") {
      result = result.filter((a) => a.is_active === false);
    }

    return result.sort((a, b) => {
      if (sortBy === "model") return a.model_id.localeCompare(b.model_id);
      if (sortBy === "date") return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      return a.name.localeCompare(b.name);
    });
  }, [agents, searchQuery, statusFilter, sortBy]);

  if (loading) {
    return (
      <div className="p-8 text-center space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mx-auto" />
        <p className="text-sm text-slate-400">Loading Agent library...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold font-display text-slate-100 flex items-center space-x-2">
            <Bot className="w-5 h-5 text-indigo-400" />
            <span>Agent Library</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Autonomous AI agent definitions, models, and endpoints managed within this Hub.
          </p>
        </div>

        {can("create_resource") && !isArchived && (
          <button
            onClick={() => setIsCreateOpen(true)}
            className="flex items-center space-x-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs rounded-xl shadow-lg shadow-indigo-500/20 transition-all shrink-0"
          >
            <Plus className="w-4 h-4" />
            <span>New Agent</span>
          </button>
        )}
      </div>

      {error && (
        <div className="p-4 bg-red-950/40 border border-red-800/40 rounded-xl text-red-300 text-xs">
          {error}
        </div>
      )}

      {/* Create Agent Form Modal */}
      {isCreateOpen && (
        <form onSubmit={handleCreateSubmit} className="p-6 bg-slate-900/90 border border-indigo-500/40 rounded-2xl space-y-4 shadow-2xl">
          <h3 className="text-base font-bold text-slate-100 font-display">Create AI Agent</h3>
          {createError && <p className="text-xs text-red-400">{createError}</p>}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Agent Name *</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Support Triager Agent"
                required
                className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Agent Role</label>
              <input
                type="text"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                placeholder="Customer Support Assistant"
                className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
              />
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-2">Inference Model Config</label>
              <ModelSelector
                value={modelId}
                onChange={setModelId}
                role="completion"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Endpoint Slug</label>
              <input
                type="text"
                value={endpointSlug}
                readOnly
                className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-xs font-mono text-slate-400 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">System Prompt</label>
            <textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              rows={3}
              className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-xs font-mono text-slate-100 focus:outline-none focus:border-indigo-500"
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
              <span>Create Agent</span>
            </button>
          </div>
        </form>
      )}

      {/* Filter & Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="relative flex-1 w-full max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search agents by name or role..."
            className="w-full bg-slate-900/60 border border-slate-800 rounded-xl pl-9 pr-4 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />
        </div>

        <div className="flex items-center space-x-3 text-xs">
          <div className="flex items-center space-x-1 bg-slate-900 border border-slate-800 rounded-lg px-2 py-1">
            <span className="text-slate-500">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-transparent text-slate-200 focus:outline-none text-xs cursor-pointer"
            >
              <option value="all" className="bg-slate-900">All Agents</option>
              <option value="active" className="bg-slate-900">Active Only</option>
              <option value="disabled" className="bg-slate-900">Disabled Only</option>
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
              <option value="model" className="bg-slate-900">Model</option>
              <option value="date" className="bg-slate-900">Created Date</option>
            </select>
          </div>
        </div>
      </div>

      {/* Agent Cards Grid */}
      {filteredAgents.length === 0 ? (
        <EmptyState
          icon={Bot}
          title="No AI Agents Configured"
          description="Build your first autonomous AI agent with system prompts, inference models, and endpoint bindings."
          actionLabel={can("create_resource") && !isArchived ? "Build an Agent" : undefined}
          onAction={() => setIsCreateOpen(true)}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredAgents.map((agent) => (
            <div
              key={agent.id}
              onClick={() => navigate(routes.agentHub.agent(hubId || "", agent.id))}
              className="p-5 bg-slate-900/50 hover:bg-slate-900/80 border border-slate-800/80 hover:border-indigo-500/40 rounded-xl space-y-4 flex flex-col justify-between cursor-pointer transition-all shadow-lg"
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0">
                      <Bot className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-bold text-slate-100 text-base font-display">{agent.name}</h3>
                      <p className="text-xs text-slate-400">{agent.role}</p>
                    </div>
                  </div>
                </div>

                <p className="text-xs font-mono text-slate-500 truncate">
                  endpoint: {agent.endpoint_slug || agent.id}
                </p>
              </div>

              <div className="pt-3 border-t border-slate-800/60 flex items-center justify-between text-xs font-mono text-slate-400">
                <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                  {agent.model_id}
                </span>

                <div className="flex items-center space-x-1" onClick={(e) => e.stopPropagation()}>
                  {can("delete_resource") && !isArchived && (
                    <button
                      onClick={() => handleDeleteAgent(agent.id)}
                      className="p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-950/40 transition-colors"
                      title="Delete Agent"
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
    </div>
  );
}
