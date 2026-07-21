import React, { useState, useEffect } from "react";
import { Plus, Users, Cpu, Trash2, Edit2, Check, X } from "lucide-react";
import { api } from "../services/api";
import { useStore, type Agent } from "../store/useStore";

export const AgentHub: React.FC = () => {
  const agents = useStore((state) => state.agents);
  const setAgents = useStore((state) => state.setAgents);

  const [isLoading, setIsLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [editingAgent, setEditingAgent] = useState<Agent | null>(null);

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
    "gemini/gemini-3.5-flash"
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
    try {
      const data = await api.getAgents();
      setAgents(data);
    } catch (err) {
      console.error("Failed to load agents:", err);
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
      max_tokens: 2048
    };

    try {
      if (editingAgent) {
        await api.updateAgent(editingAgent.id, payload);
      } else {
        await api.createAgent(payload);
      }
      setShowModal(false);
      fetchAgents();
    } catch (err: any) {
      alert(`Failed to save agent: ${err.message}`);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this agent?")) return;
    try {
      await api.deleteAgent(id);
      fetchAgents();
    } catch (err: any) {
      alert(`Failed to delete agent: ${err.message}`);
    }
  };

  const toggleTool = (toolId: string) => {
    setSelectedTools((prev) =>
      prev.includes(toolId) ? prev.filter((t) => t !== toolId) : [...prev, toolId]
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-white">Agent Hub & Custom Subagent Registry</h2>
          <p className="text-xs text-zinc-400">Manage custom agent personalities, tool authorizations, and system prompts.</p>
        </div>

        <button
          onClick={handleOpenCreate}
          className="px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-600 font-medium text-xs text-white flex items-center gap-1.5 shadow-lg shadow-emerald-500/20 transition-colors"
        >
          <Plus className="w-4 h-4" /> Create Custom Agent
        </button>
      </div>

      {/* Grid */}
      {isLoading ? (
        <div className="text-xs text-zinc-400 py-12 text-center">Loading registered agents...</div>
      ) : agents.length === 0 ? (
        <div className="p-8 rounded-xl bg-[#15171e] border border-[#26282d] text-center space-y-3">
          <Users className="w-8 h-8 text-zinc-500 mx-auto" />
          <div className="text-sm font-medium text-white">No Custom Agents Found</div>
          <p className="text-xs text-zinc-400">Click "Create Custom Agent" to register your first subagent.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {agents.map((agent) => (
            <div key={agent.id} className="p-5 rounded-xl bg-[#15171e] border border-[#26282d] flex flex-col justify-between space-y-4 hover:border-emerald-500/30 transition-colors">
              <div className="space-y-3">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-white">{agent.name}</h3>
                    <span className="text-xs text-emerald-400 font-mono">{agent.role}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <button onClick={() => handleOpenEdit(agent)} className="p-1 text-zinc-400 hover:text-white rounded">
                      <Edit2 className="w-3.5 h-3.5" />
                    </button>
                    <button onClick={() => handleDelete(agent.id)} className="p-1 text-zinc-400 hover:text-red-400 rounded">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                <p className="text-xs text-zinc-300 line-clamp-2 bg-[#121316] p-2 rounded border border-[#22252c] font-mono">
                  {agent.system_prompt}
                </p>

                <div className="space-y-2 text-xs">
                  <div className="flex items-center gap-1.5 text-zinc-400">
                    <Cpu className="w-3.5 h-3.5 text-amber-400" />
                    <span>Model: <strong className="text-zinc-200">{agent.model_id}</strong></span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {agent.tools?.map((tool) => (
                      <span key={tool} className="px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-[10px] text-emerald-400 font-mono">
                        {tool}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              <div className="text-[10px] text-zinc-500 pt-3 border-t border-[#22252c]">
                Temp: {agent.temperature} | Max Tokens: {agent.max_tokens || 2048}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Dialog Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-[#15171e] border border-[#26282d] rounded-xl p-6 shadow-2xl space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-[#26282d]">
              <h3 className="text-sm font-bold text-white">
                {editingAgent ? "Edit Agent Definition" : "Register New Subagent"}
              </h3>
              <button onClick={() => setShowModal(false)} className="text-zinc-400 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSave} className="space-y-4 text-xs">
              <div>
                <label className="text-zinc-300 font-medium block mb-1">Agent Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Code Reviewer Subagent"
                  className="w-full px-3 py-2 rounded bg-[#121316] border border-[#2d3039] text-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="text-zinc-300 font-medium block mb-1">Role / Specialization</label>
                <input
                  type="text"
                  required
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  placeholder="e.g. Senior Security Auditor"
                  className="w-full px-3 py-2 rounded bg-[#121316] border border-[#2d3039] text-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="text-zinc-300 font-medium block mb-1">LLM Model ID</label>
                <select
                  value={modelId}
                  onChange={(e) => setModelId(e.target.value)}
                  className="w-full px-3 py-2 rounded bg-[#121316] border border-[#2d3039] text-white focus:outline-none focus:border-emerald-500"
                >
                  {availableModels.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-zinc-300 font-medium block mb-1">System Prompt</label>
                <textarea
                  rows={4}
                  required
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  className="w-full px-3 py-2 rounded bg-[#121316] border border-[#2d3039] text-white focus:outline-none focus:border-emerald-500 resize-none font-mono"
                />
              </div>

              <div>
                <label className="text-zinc-300 font-medium block mb-1">Tool Authorizations</label>
                <div className="space-y-1.5">
                  {availableTools.map((t) => (
                    <button
                      type="button"
                      key={t.id}
                      onClick={() => toggleTool(t.id)}
                      className={`w-full flex items-center justify-between px-3 py-2 rounded border text-left transition-colors ${
                        selectedTools.includes(t.id)
                          ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                          : "bg-[#121316] border-[#2d3039] text-zinc-400"
                      }`}
                    >
                      <span>{t.label}</span>
                      {selectedTools.includes(t.id) && <Check className="w-3.5 h-3.5" />}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between text-zinc-300 mb-1">
                  <span>Temperature</span>
                  <span className="font-mono text-emerald-400">{temperature}</span>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="1.0"
                  step="0.05"
                  value={temperature}
                  onChange={(e) => setTemperature(Number(e.target.value))}
                  className="w-full accent-emerald-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-[#26282d]">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 rounded bg-[#1f2128] hover:bg-[#282b34] text-zinc-300 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded bg-emerald-500 hover:bg-emerald-600 text-white font-medium shadow-lg shadow-emerald-500/20"
                >
                  Save Agent
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
