import React, { useState, useEffect } from "react";
import { Plus, Cpu, Trash2, Edit2, Check, X, Users, Search, Activity, Clock } from "lucide-react";
import { api } from "../services/api";
import { useStore, type Agent } from "../store/useStore";
import { LoadingSkeleton, EmptyState, ConfirmModal, StatusBadge, ErrorBanner, useToast } from "./shared";

export const AgentHub: React.FC = () => {
  const agents = useStore((state) => state.agents);
  const setAgents = useStore((state) => state.setAgents);
  const toast = useToast();

  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [editingAgent, setEditingAgent] = useState<Agent | null>(null);

  // Search filter
  const [searchQuery, setSearchQuery] = useState("");

  // Deletion confirm state
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [deleteTargetName, setDeleteTargetName] = useState<string>("");

  // Form states
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [modelId, setModelId] = useState("Arch-Router-1.5B");
  const [selectedTools, setSelectedTools] = useState<string[]>(["retrieval"]);
  const [temperature, setTemperature] = useState(0.2);

  const availableModels = [
    "Arch-Router-1.5B",
    "FunAudioLLM/SenseVoiceSmall",
    "THUDM/GLM-OCR",
    "jinaai/jina-clip-v2",
    "gemini/gemini-3.5-flash",
  ];

  const availableTools = [
    { id: "retrieval", label: "SyntraFlow Hybrid Retrieval Search" },
    { id: "web_search", label: "DuckDuckGo / Web Search" },
    { id: "code_sandbox", label: "Docker Code Execution Sandbox" },
  ];

  useEffect(() => {
    fetchAgents();
  }, []);

  const fetchAgents = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const data = await api.getAgents();
      setAgents(data);
    } catch (err: any) {
      console.error("Failed to load agents:", err);
      setErrorMessage(err.message || "Failed to communicate with Agent API server.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleOpenCreate = () => {
    setEditingAgent(null);
    setName("");
    setRole("");
    setSystemPrompt("You are an AI assistant node inside ContAIned platform.");
    setModelId("Arch-Router-1.5B");
    setSelectedTools(["retrieval"]);
    setTemperature(0.2);
    setShowModal(true);
  };

  const handleOpenEdit = (agent: Agent) => {
    setEditingAgent(agent);
    setName(agent.name);
    setRole(agent.role);
    setSystemPrompt(agent.system_prompt);
    setModelId(agent.model_id);
    setSelectedTools(agent.tools || []);
    setTemperature(agent.temperature || 0.2);
    setShowModal(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = {
      name,
      role,
      system_prompt: systemPrompt,
      model_id: modelId,
      tools: selectedTools,
      temperature,
      max_tokens: 2048,
    };

    try {
      if (editingAgent) {
        await api.updateAgent(editingAgent.id, payload);
        toast.success("Agent Updated", `Agent "${name}" updated successfully.`);
      } else {
        await api.createAgent(payload);
        toast.success("Agent Created", `New subagent "${name}" registered successfully.`);
      }
      setShowModal(false);
      fetchAgents();
    } catch (err: any) {
      setErrorMessage(`Failed to save agent: ${err.message}`);
      toast.error("Save Failed", err.message || "Could not save agent configuration.");
    }
  };

  const requestDelete = (agent: Agent) => {
    setDeleteTargetId(agent.id);
    setDeleteTargetName(agent.name);
  };

  const confirmDelete = async () => {
    if (!deleteTargetId) return;
    try {
      await api.deleteAgent(deleteTargetId);
      toast.success("Agent Deleted", `Agent "${deleteTargetName}" was removed.`);
      setDeleteTargetId(null);
      fetchAgents();
    } catch (err: any) {
      setErrorMessage(`Failed to delete agent: ${err.message}`);
      toast.error("Delete Failed", err.message || "Could not delete agent.");
    }
  };

  const toggleTool = (toolId: string) => {
    setSelectedTools((prev) =>
      prev.includes(toolId) ? prev.filter((t) => t !== toolId) : [...prev, toolId]
    );
  };

  // Filtered agents
  const filteredAgents = agents.filter(
    (a) =>
      a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.role.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.model_id.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex flex-col gap-8 max-w-7xl mx-auto w-full">
      {/* Header Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[var(--border-subtle)]">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-extrabold text-white font-display">
              Agent Hub & Custom Subagent Registry
            </h2>
            <span className="text-xs font-mono font-bold text-indigo-400 bg-indigo-500/15 px-2.5 py-0.5 rounded-full border border-indigo-500/30">
              {agents.length} Registered
            </span>
          </div>
          <p className="text-xs text-[var(--text-secondary)] mt-1">
            Manage custom agent personalities, tool authorizations, and system prompts.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Search Bar */}
          <div className="relative">
            <Search className="w-4 h-4 text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter by name, role, model..."
              className="pl-9 pr-4 py-2 text-xs rounded-xl bg-[var(--bg-input)] border border-[var(--border-default)] text-white focus:outline-none focus:border-indigo-500 w-64 shadow-inner"
            />
          </div>

          <button
            onClick={handleOpenCreate}
            className="px-4 py-2 rounded-xl font-bold text-xs text-white flex items-center gap-2 shadow-xl transition-all hover:scale-[1.02]"
            style={{
              backgroundColor: "var(--accent-indigo)",
              boxShadow: "0 4px 14px var(--accent-indigo-glow)",
            }}
          >
            <Plus className="w-4 h-4" /> Create Custom Agent
          </button>
        </div>
      </div>

      {errorMessage && (
        <ErrorBanner
          title="Agent Hub Error"
          message={errorMessage}
          onRetry={fetchAgents}
        />
      )}

      {/* Grid / Skeletons / Empty State */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <LoadingSkeleton variant="card" count={3} />
        </div>
      ) : filteredAgents.length === 0 ? (
        <EmptyState
          icon={Users}
          title={searchQuery ? "No Matching Agents Found" : "No Custom Agents Found"}
          description={
            searchQuery
              ? `No agents match your search filter "${searchQuery}".`
              : "Register your first subagent personality to automate workflows across ContAIned."
          }
          actionLabel={searchQuery ? "Clear Search Filter" : "Create Custom Agent"}
          onAction={searchQuery ? () => setSearchQuery("") : handleOpenCreate}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredAgents.map((agent, index) => {
            // Mock Analytics Preview per card
            const mockQueries = (index + 1) * 142 + 89;
            const mockLatency = (120 + index * 35) + "ms";

            return (
              <div
                key={agent.id}
                className="p-8 rounded-2xl border flex flex-col justify-between space-y-6 transition-all duration-200 hover:scale-[1.01] hover:border-indigo-500/50 group relative shadow-2xl bg-[#0e0e12]"
                style={{
                  borderColor: "var(--border-default)",
                }}
              >
                <div className="space-y-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="text-sm font-bold text-[var(--text-primary)] group-hover:text-indigo-300 transition-colors">
                        {agent.name}
                      </h3>
                      <div className="flex items-center gap-1.5 mt-1">
                        <StatusBadge variant="info" label={agent.role} size="sm" />
                        <StatusBadge variant="success" label="Active" size="sm" />
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handleOpenEdit(agent)}
                        className="p-1.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] rounded-md transition-colors"
                        title="Edit Agent"
                      >
                        <Edit2 className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => requestDelete(agent)}
                        className="p-1.5 text-[var(--text-muted)] hover:text-[var(--accent-rose)] hover:bg-[var(--rose-soft)] rounded-md transition-colors"
                        title="Delete Agent"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  <p
                    className="text-xs line-clamp-2 p-2.5 rounded-lg border font-mono leading-relaxed"
                    style={{
                      backgroundColor: "var(--bg-input)",
                      borderColor: "var(--border-subtle)",
                      color: "var(--text-secondary)",
                    }}
                  >
                    {agent.system_prompt}
                  </p>

                  <div className="space-y-2 text-xs">
                    <div className="flex items-center gap-1.5 text-[var(--text-secondary)]">
                      <Cpu className="w-3.5 h-3.5 text-[var(--accent-amber)]" />
                      <span>
                        Model: <strong className="text-[var(--text-primary)]">{agent.model_id}</strong>
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {agent.tools?.map((tool) => (
                        <StatusBadge key={tool} variant="neutral" label={tool} dot={false} size="sm" />
                      ))}
                    </div>
                  </div>
                </div>

                {/* Card Footer with Analytics Preview */}
                <div
                  className="text-[10px] pt-3 border-t flex items-center justify-between font-mono"
                  style={{
                    borderColor: "var(--border-subtle)",
                    color: "var(--text-muted)",
                  }}
                >
                  <div className="flex items-center gap-3">
                    <span className="flex items-center gap-1" title="Total Executed Queries">
                      <Activity className="w-3 h-3 text-emerald-400" />
                      {mockQueries} queries
                    </span>
                    <span className="flex items-center gap-1" title="Average Response Latency">
                      <Clock className="w-3 h-3 text-indigo-400" />
                      {mockLatency}
                    </span>
                  </div>
                  <span>Temp: {agent.temperature}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Confirm Deletion Modal */}
      <ConfirmModal
        isOpen={Boolean(deleteTargetId)}
        title="Delete Custom Agent?"
        message={`Are you sure you want to delete "${deleteTargetName}"? This action cannot be undone and any running workflows referencing this agent will fall back to default router.`}
        confirmLabel="Delete Agent"
        cancelLabel="Cancel"
        isDanger={true}
        onConfirm={confirmDelete}
        onCancel={() => setDeleteTargetId(null)}
      />

      {/* Edit/Create Agent Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-md flex items-center justify-center p-6">
          <div
            className="w-full max-w-lg border rounded-2xl shadow-2xl flex flex-col"
            style={{
              backgroundColor: "var(--bg-surface)",
              borderColor: "var(--border-default)",
              maxHeight: "calc(100vh - 3rem)",
            }}
          >
            <div className="flex items-center justify-between p-6 pb-4 border-b border-[var(--border-subtle)] shrink-0">
              <h3 className="text-sm font-bold text-[var(--text-primary)] font-display">
                {editingAgent ? "Edit Agent Definition" : "Register New Subagent"}
              </h3>
              <button
                onClick={() => setShowModal(false)}
                className="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1 rounded-lg hover:bg-[var(--bg-elevated)] transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSave} className="space-y-5 text-xs overflow-y-auto px-6 py-4 custom-scrollbar">
              <div>
                <label className="text-[var(--text-secondary)] font-medium block mb-1">Agent Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Code Reviewer Subagent"
                  className="w-full px-3 py-2 rounded-lg border text-[var(--text-primary)] focus:outline-none"
                  style={{
                    backgroundColor: "var(--bg-input)",
                    borderColor: "var(--border-default)",
                  }}
                />
              </div>

              <div>
                <label className="text-[var(--text-secondary)] font-medium block mb-1">Role / Specialization</label>
                <input
                  type="text"
                  required
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  placeholder="e.g. Senior Security Auditor"
                  className="w-full px-3 py-2 rounded-lg border text-[var(--text-primary)] focus:outline-none"
                  style={{
                    backgroundColor: "var(--bg-input)",
                    borderColor: "var(--border-default)",
                  }}
                />
              </div>

              <div>
                <label className="text-[var(--text-secondary)] font-medium block mb-1">LLM Model ID</label>
                <select
                  value={modelId}
                  onChange={(e) => setModelId(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border text-[var(--text-primary)] focus:outline-none"
                  style={{
                    backgroundColor: "var(--bg-input)",
                    borderColor: "var(--border-default)",
                  }}
                >
                  {availableModels.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-[var(--text-secondary)] font-medium block mb-1">System Prompt</label>
                <textarea
                  rows={4}
                  required
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border text-[var(--text-primary)] focus:outline-none resize-none font-mono"
                  style={{
                    backgroundColor: "var(--bg-input)",
                    borderColor: "var(--border-default)",
                  }}
                />
              </div>

              <div>
                <label className="text-[var(--text-secondary)] font-medium block mb-1">Tool Authorizations</label>
                <div className="space-y-1.5">
                  {availableTools.map((t) => (
                    <button
                      type="button"
                      key={t.id}
                      onClick={() => toggleTool(t.id)}
                      className={`w-full flex items-center justify-between px-3 py-2 rounded-lg border text-left transition-colors ${
                        selectedTools.includes(t.id)
                          ? "bg-[var(--indigo-soft)] border-[var(--accent-indigo)] text-[var(--accent-indigo)]"
                          : "bg-[var(--bg-input)] border-[var(--border-default)] text-[var(--text-muted)]"
                      }`}
                    >
                      <span>{t.label}</span>
                      {selectedTools.includes(t.id) && <Check className="w-3.5 h-3.5" />}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between text-[var(--text-secondary)] mb-1">
                  <span>Temperature</span>
                  <span className="font-mono text-[var(--accent-indigo)]">{temperature}</span>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="1.0"
                  step="0.05"
                  value={temperature}
                  onChange={(e) => setTemperature(Number(e.target.value))}
                  className="w-full accent-[var(--accent-indigo)]"
                />
              </div>

            </form>

            <div className="flex items-center justify-end gap-3 p-6 pt-4 border-t border-[var(--border-subtle)] shrink-0">
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="px-5 py-2.5 rounded-lg bg-[var(--bg-elevated)] hover:bg-[var(--bg-surface-alt)] text-[var(--text-secondary)] font-medium transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={(e) => {
                  const form = (e.target as HTMLElement).closest('.flex-col')?.querySelector('form');
                  if (form) form.requestSubmit();
                }}
                className="px-5 py-2.5 rounded-lg bg-[var(--accent-indigo)] hover:opacity-90 text-white font-medium shadow-md transition-all"
              >
                Save Agent
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AgentHub;

