import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Bot,
  Settings,
  Layers,
  Code,
  Activity,
  Play,
  ArrowLeft,
  Save,
  RotateCcw,
  Copy,
  Check,
  Loader2,
  AlertCircle,
  Link2,
  Trash2,
} from "lucide-react";
import { useHubPermissions } from "../../../hooks/useHubPermissions";
import { api } from "../../../services/api";
import { routes } from "../../../routes";
import { ModelSelector } from "../../shared/ModelSelector";
import { Gated } from "../Gated";

type AgentDetailTab = "config" | "knowledge" | "endpoint" | "invocations" | "test";

export function AgentDetail() {
  const { hubId, agentId } = useParams<{ hubId: string; agentId: string }>();
  const navigate = useNavigate();
  const { can, isArchived } = useHubPermissions();

  const [activeTab, setActiveTab] = useState<AgentDetailTab>("config");
  const [agent, setAgent] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Configuration Form State
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [modelId, setModelId] = useState("gpt-4o");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(2048);

  const [isDirty, setIsDirty] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Knowledge Tab State
  const [boundBindings, setBoundBindings] = useState<{ hub_id: string; collection_id: string; alias?: string; top_k?: number }[]>([]);
  const [linkedHubsData, setLinkedHubsData] = useState<{ hub: any; collections: any[] }[]>([]);
  const [loadingKnowledge, setLoadingKnowledge] = useState(false);
  const [isSavingBindings, setIsSavingBindings] = useState(false);
  const [bindingsSuccess, setBindingsSuccess] = useState(false);

  // Test Tab State
  const [testPrompt, setTestPrompt] = useState("");
  const [testResult, setTestResult] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);

  const [copied, setCopied] = useState(false);
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

  const fetchAgent = async () => {
    if (!hubId || !agentId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.agents.get(hubId, agentId);
      setAgent(data);
      setName(data.name || "");
      setRole(data.role || "");
      setModelId(data.model_id || "gpt-4o");
      setSystemPrompt(data.system_prompt || "");
      setTemperature(data.temperature ?? 0.7);
      setMaxTokens(data.max_tokens ?? 2048);
      setBoundBindings(
        data.collection_bindings?.map((b: any) => ({
          hub_id: b.hub_id,
          collection_id: b.collection_id,
          alias: b.alias,
          top_k: b.top_k || 5,
        })) || []
      );
      setIsDirty(false);
    } catch (err: any) {
      setError(err?.message || "Failed to load agent detail");
    } finally {
      setLoading(false);
    }
  };

  const fetchKnowledgeData = async () => {
    if (!hubId) return;
    setLoadingKnowledge(true);
    try {
      const links = await api.hubs.links.list(hubId);
      const allHubs = await api.hubs.list();
      const hubsMap = new Map(allHubs.map((h: any) => [h.id, h]));

      const ingestionLinks = links.filter((l: any) => {
        const target = hubsMap.get(l.target_hub_id);
        return target && target.hub_type === "ingestion";
      });

      const results = await Promise.all(
        ingestionLinks.map(async (l: any) => {
          const targetHub = hubsMap.get(l.target_hub_id);
          try {
            const res = await api.ingestion.collections.list(l.target_hub_id);
            const cols = Array.isArray(res) ? res : res.collections || [];
            return { hub: targetHub, collections: cols };
          } catch {
            return { hub: targetHub, collections: [] };
          }
        })
      );
      setLinkedHubsData(results);
    } catch (err) {
      console.error("Failed to load knowledge data:", err);
    } finally {
      setLoadingKnowledge(false);
    }
  };

  useEffect(() => {
    fetchAgent();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hubId, agentId]);

  useEffect(() => {
    if (activeTab === "knowledge") {
      fetchKnowledgeData();
    }
  }, [activeTab, hubId]);

  const handleSaveBindings = async () => {
    if (!hubId || !agentId) return;
    setIsSavingBindings(true);
    try {
      await api.agents.update(hubId, agentId, {
        collection_bindings: boundBindings,
      });
      setBindingsSuccess(true);
      setTimeout(() => setBindingsSuccess(false), 3000);
      fetchAgent();
    } catch (err: any) {
      console.error("Failed to save collection bindings:", err);
    } finally {
      setIsSavingBindings(false);
    }
  };

  const handleSaveConfig = async () => {
    if (!hubId || !agentId) return;
    setIsSaving(true);
    try {
      await api.agents.update(hubId, agentId, {
        name,
        role,
        model_id: modelId,
        system_prompt: systemPrompt,
        temperature,
        max_tokens: maxTokens,
      });
      setIsDirty(false);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
      fetchAgent();
    } catch (err: any) {
      console.error("Failed to save agent config:", err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleRunTest = async () => {
    if (!hubId || !agentId || !testPrompt.trim()) return;
    setTesting(true);
    setTestResult(null);
    try {
      const res = await api.agents.invoke(hubId, agentId, { prompt: testPrompt.trim() });
      setTestResult(typeof res === "string" ? res : res.response || JSON.stringify(res, null, 2));
    } catch (err: any) {
      setTestResult(`Error: ${err?.message || "Invocation failed"}`);
    } finally {
      setTesting(false);
    }
  };

  const handleCopySnippet = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading) {
    return (
      <div className="p-8 text-center space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mx-auto" />
        <p className="text-sm text-slate-400">Loading Agent workspace...</p>
      </div>
    );
  }

  if (error || !agent) {
    return (
      <div className="p-8 text-center space-y-4">
        <AlertCircle className="w-10 h-10 text-red-500 mx-auto" />
        <h3 className="text-base font-bold text-slate-200">Agent Not Found</h3>
        <p className="text-xs text-slate-400">{error || "Could not retrieve agent metadata"}</p>
        <button
          onClick={() => navigate(routes.agentHub.agents(hubId || ""))}
          className="px-4 py-2 bg-slate-800 text-slate-200 text-xs font-medium rounded-lg hover:bg-slate-700"
        >
          Back to Agent Library
        </button>
      </div>
    );
  }

  const curlSnippet = `curl -X POST "${window.location.origin}/api/hubs/${hubId}/agents/${agent.id}/invoke" \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: $CONTAINED_API_KEY" \\
  -d '{"prompt": "Hello agent!"}'`;

  return (
    <div className="space-y-6 pb-12">
      {/* Sticky Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-4">
        <div className="flex items-center space-x-3">
          <button
            onClick={() => navigate(routes.agentHub.agents(hubId || ""))}
            className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
            title="Back to Agent Library"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <h2 className="text-xl font-bold font-display text-slate-100 flex items-center space-x-2">
              <Bot className="w-5 h-5 text-indigo-400" />
              <span>{name || agent.name}</span>
            </h2>
            <p className="text-xs text-slate-400 font-mono mt-0.5">
              endpoint: agent/{agent.endpoint_slug || agent.id.slice(0, 8)}
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {saveSuccess && (
            <span className="text-xs text-emerald-400 font-semibold flex items-center space-x-1">
              <Check className="w-3.5 h-3.5" />
              <span>Saved</span>
            </span>
          )}
          <button
            onClick={handleSaveConfig}
            disabled={!isDirty || isSaving || !can("edit_resource") || isArchived}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium text-xs rounded-xl shadow-lg shadow-indigo-500/20 transition-all flex items-center space-x-1.5"
          >
            {isSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
            <span>{isSaving ? "Saving..." : "Save Configuration"}</span>
          </button>
        </div>
      </div>

      {/* Tabs Bar */}
      <div className="flex items-center space-x-2 border-b border-slate-800/60 pb-2">
        <button
          onClick={() => setActiveTab("config")}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center space-x-1.5 ${
            activeTab === "config" ? "bg-indigo-600/20 text-indigo-300 border border-indigo-800/40" : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <Settings className="w-3.5 h-3.5" />
          <span>Config & Prompt</span>
        </button>
        <button
          onClick={() => setActiveTab("knowledge")}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center space-x-1.5 ${
            activeTab === "knowledge" ? "bg-indigo-600/20 text-indigo-300 border border-indigo-800/40" : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>Knowledge & Collections</span>
        </button>
        <button
          onClick={() => setActiveTab("endpoint")}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center space-x-1.5 ${
            activeTab === "endpoint" ? "bg-indigo-600/20 text-indigo-300 border border-indigo-800/40" : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <Code className="w-3.5 h-3.5" />
          <span>Endpoint API</span>
        </button>
        <button
          onClick={() => setActiveTab("invocations")}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center space-x-1.5 ${
            activeTab === "invocations" ? "bg-indigo-600/20 text-indigo-300 border border-indigo-800/40" : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <Activity className="w-3.5 h-3.5" />
          <span>Execution Logs</span>
        </button>
        <button
          onClick={() => setActiveTab("test")}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center space-x-1.5 ${
            activeTab === "test" ? "bg-indigo-600/20 text-indigo-300 border border-indigo-800/40" : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <Play className="w-3.5 h-3.5" />
          <span>Test Arena</span>
        </button>
      </div>

      {/* TAB 1: CONFIG */}
      {activeTab === "config" && (
        <div className="bg-slate-900/50 border border-slate-800/80 rounded-xl p-6 space-y-6 shadow-lg">
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Agent Name *</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => {
                    setName(e.target.value);
                    setIsDirty(true);
                  }}
                  disabled={!can("edit_resource") || isArchived}
                  className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-indigo-500 disabled:opacity-60"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Agent Role / Description</label>
                <input
                  type="text"
                  value={role}
                  onChange={(e) => {
                    setRole(e.target.value);
                    setIsDirty(true);
                  }}
                  disabled={!can("edit_resource") || isArchived}
                  className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-indigo-500 disabled:opacity-60"
                />
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-2">Inference Model Config</label>
                <ModelSelector
                  value={modelId}
                  onChange={(val) => {
                    setModelId(val);
                    setIsDirty(true);
                  }}
                  role="completion"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Temperature ({temperature})</label>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.05}
                    value={temperature}
                    onChange={(e) => {
                      setTemperature(parseFloat(e.target.value));
                      setIsDirty(true);
                    }}
                    disabled={!can("edit_resource") || isArchived}
                    className="w-full accent-indigo-500 cursor-pointer mt-2"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Max Tokens</label>
                  <input
                    type="number"
                    value={maxTokens}
                    onChange={(e) => {
                      setMaxTokens(parseInt(e.target.value));
                      setIsDirty(true);
                    }}
                    disabled={!can("edit_resource") || isArchived}
                    className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-xs font-mono text-slate-100 focus:outline-none focus:border-indigo-500 disabled:opacity-60"
                  />
                </div>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">System Instructions Prompt *</label>
              <textarea
                value={systemPrompt}
                onChange={(e) => {
                  setSystemPrompt(e.target.value);
                  setIsDirty(true);
                }}
                rows={8}
                disabled={!can("edit_resource") || isArchived}
                className="w-full bg-slate-950/90 border border-slate-800 rounded-xl p-4 text-xs font-mono text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 leading-relaxed disabled:opacity-60"
              />
              <p className="text-[11px] font-mono text-slate-500 mt-1">
                Estimated tokens: ~{Math.round(systemPrompt.length / 4)} tokens
              </p>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: KNOWLEDGE */}
      {activeTab === "knowledge" && (
        <div className="bg-slate-900/50 border border-slate-800/80 rounded-xl p-6 space-y-6 shadow-lg">
          <div className="flex items-center justify-between border-b border-slate-800/60 pb-3">
            <div>
              <h3 className="text-base font-bold text-slate-100 font-display flex items-center space-x-2">
                <Layers className="w-4 h-4 text-indigo-400" />
                <span>Bound Ingestion Collections</span>
              </h3>
              <p className="text-xs text-slate-400 mt-1">
                Agents may only bind collections from linked Ingestion Hubs. To consume an unlinked collection, grant a hub link in the Links tab first.
              </p>
            </div>
            <button
              onClick={handleSaveBindings}
              disabled={isSavingBindings || !can("edit_resource") || isArchived}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium text-xs rounded-xl shadow-lg shadow-indigo-500/20 transition-all flex items-center space-x-1.5"
            >
              {isSavingBindings ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : bindingsSuccess ? (
                <Check className="w-3.5 h-3.5 text-emerald-400" />
              ) : (
                <Save className="w-3.5 h-3.5" />
              )}
              <span>{isSavingBindings ? "Saving..." : bindingsSuccess ? "Saved!" : "Save Bindings"}</span>
            </button>
          </div>

          {loadingKnowledge ? (
            <div className="p-8 text-center space-y-3">
              <Loader2 className="w-6 h-6 animate-spin text-indigo-400 mx-auto" />
              <p className="text-xs text-slate-400">Loading collections from linked ingestion hubs...</p>
            </div>
          ) : linkedHubsData.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-400 border border-slate-800/60 rounded-xl bg-slate-950/40 space-y-3">
              <Link2 className="w-8 h-8 text-slate-600 mx-auto" />
              <p className="font-semibold text-slate-300">No Linked Ingestion Hubs Found</p>
              <p className="text-slate-500 max-w-sm mx-auto">
                This agent hub does not have any active outgoing links to an Ingestion Hub.
                Grant a link to an ingestion hub in the <strong>Links</strong> tab to enable vector knowledge retrieval.
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {linkedHubsData.map(({ hub, collections }) => (
                <div key={hub.id} className="border border-slate-800/80 rounded-xl bg-slate-950/40 p-4 space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-800/60 pb-2">
                    <div className="flex items-center space-x-2">
                      <div
                        className="w-3 h-3 rounded-full"
                        style={{ backgroundColor: hub.accent || "#10b981" }}
                      />
                      <span className="font-bold text-sm text-slate-100">{hub.name}</span>
                      <span className="text-xs font-mono text-slate-500">
                        ({hub.hub_type}/{hub.slug})
                      </span>
                    </div>
                    <span className="text-[11px] font-mono text-indigo-400 bg-indigo-950/50 px-2 py-0.5 rounded border border-indigo-800/40">
                      {collections.length} collection{collections.length !== 1 ? "s" : ""}
                    </span>
                  </div>

                  {collections.length === 0 ? (
                    <p className="text-xs text-slate-500 italic p-2">
                      No document collections created in this ingestion hub yet.
                    </p>
                  ) : (
                    <div className="grid grid-cols-1 gap-3">
                      {collections.map((col: any) => {
                        const isBound = boundBindings.some(
                          (b) => b.hub_id === hub.id && b.collection_id === col.id
                        );
                        const currentBinding = boundBindings.find(
                          (b) => b.hub_id === hub.id && b.collection_id === col.id
                        );

                        const toggleBinding = () => {
                          if (isBound) {
                            setBoundBindings((prev) =>
                              prev.filter(
                                (b) => !(b.hub_id === hub.id && b.collection_id === col.id)
                              )
                            );
                          } else {
                            setBoundBindings((prev) => [
                              ...prev,
                              { hub_id: hub.id, collection_id: col.id, alias: col.name, top_k: 5 },
                            ]);
                          }
                        };

                        return (
                          <div
                            key={col.id}
                            className={`p-3.5 rounded-xl border transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                              isBound
                                ? "bg-indigo-950/20 border-indigo-500/60 ring-1 ring-indigo-500/20"
                                : "bg-slate-900/40 border-slate-800/80 hover:border-slate-700"
                            }`}
                          >
                            <div className="flex items-center space-x-3">
                              <input
                                type="checkbox"
                                checked={isBound}
                                onChange={toggleBinding}
                                disabled={!can("edit_resource") || isArchived}
                                className="w-4 h-4 rounded bg-slate-950 border-slate-700 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                              />
                              <div>
                                <span className="font-semibold text-xs text-slate-200">{col.name}</span>
                                <div className="flex items-center space-x-2 mt-0.5">
                                  <span className="text-[10px] font-mono text-slate-400">
                                    Embed: {col.embedding_model || "jina-clip-v2"}
                                  </span>
                                  <span className="text-[10px] font-mono text-slate-500">
                                    Dim: {col.vector_dimension || 1024}
                                  </span>
                                </div>
                              </div>
                            </div>

                            {isBound && (
                              <div className="flex items-center space-x-3 pl-7 sm:pl-0">
                                <div className="flex items-center space-x-1.5">
                                  <label className="text-[11px] font-mono text-slate-400">Alias:</label>
                                  <input
                                    type="text"
                                    value={currentBinding?.alias || ""}
                                    onChange={(e) => {
                                      const val = e.target.value;
                                      setBoundBindings((prev) =>
                                        prev.map((b) =>
                                          b.hub_id === hub.id && b.collection_id === col.id
                                            ? { ...b, alias: val }
                                            : b
                                        )
                                      );
                                    }}
                                    placeholder={col.name}
                                    className="w-28 bg-slate-950 border border-slate-800 rounded px-2 py-1 text-[11px] font-mono text-slate-200 focus:outline-none focus:border-indigo-500"
                                  />
                                </div>
                                <div className="flex items-center space-x-1.5">
                                  <label className="text-[11px] font-mono text-slate-400">Top-K:</label>
                                  <input
                                    type="number"
                                    min={1}
                                    max={20}
                                    value={currentBinding?.top_k || 5}
                                    onChange={(e) => {
                                      const val = parseInt(e.target.value) || 5;
                                      setBoundBindings((prev) =>
                                        prev.map((b) =>
                                          b.hub_id === hub.id && b.collection_id === col.id
                                            ? { ...b, top_k: val }
                                            : b
                                        )
                                      );
                                    }}
                                    className="w-14 bg-slate-950 border border-slate-800 rounded px-2 py-1 text-[11px] font-mono text-slate-200 focus:outline-none focus:border-indigo-500"
                                  />
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 3: ENDPOINT */}
      {activeTab === "endpoint" && (
        <div className="bg-slate-900/50 border border-slate-800/80 rounded-xl p-6 space-y-6 shadow-lg">
          <div>
            <h3 className="text-base font-bold text-slate-100 font-display flex items-center space-x-2">
              <Code className="w-4 h-4 text-indigo-400" />
              <span>API Endpoint Integration</span>
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              External cURL and REST invocation snippet for this agent endpoint.
            </p>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-300 font-mono">cURL Command</span>
              <button
                onClick={() => handleCopySnippet(curlSnippet)}
                className="flex items-center space-x-1 px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-lg transition-colors"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? "Copied" : "Copy"}</span>
              </button>
            </div>
            <pre className="p-4 bg-slate-950 rounded-xl border border-slate-800 text-xs font-mono text-indigo-300 overflow-x-auto leading-relaxed">
              {curlSnippet}
            </pre>
          </div>
        </div>
      )}

      {/* TAB 4: INVOCATIONS */}
      {activeTab === "invocations" && (
        <div className="bg-slate-900/50 border border-slate-800/80 rounded-xl p-6 space-y-4 shadow-lg">
          <h3 className="text-base font-bold text-slate-100 font-display flex items-center space-x-2">
            <Activity className="w-4 h-4 text-indigo-400" />
            <span>Execution Logs</span>
          </h3>
          <div className="p-8 text-center text-xs text-slate-500 border border-slate-800/60 rounded-xl bg-slate-950/40">
            No invocation requests logged in the current window.
          </div>
        </div>
      )}

      {/* TAB 5: TEST ARENA */}
      {activeTab === "test" && (
        <div className="bg-slate-900/50 border border-slate-800/80 rounded-xl p-6 space-y-6 shadow-lg">
          <div>
            <h3 className="text-base font-bold text-slate-100 font-display flex items-center space-x-2">
              <Play className="w-4 h-4 text-indigo-400" />
              <span>Interactive Agent Test Arena</span>
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              Send test prompts directly to this agent using its current prompt and parameters.
            </p>
          </div>

          <div className="space-y-4">
            <textarea
              value={testPrompt}
              onChange={(e) => setTestPrompt(e.target.value)}
              rows={3}
              placeholder="Ask this agent a test question..."
              className="w-full bg-slate-950/90 border border-slate-800 rounded-xl p-3 text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
            />
            <div className="flex justify-end">
              <button
                onClick={handleRunTest}
                disabled={testing || !testPrompt.trim()}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium text-xs rounded-xl shadow-lg shadow-indigo-500/20 transition-all flex items-center space-x-1.5"
              >
                {testing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                <span>Run Test</span>
              </button>
            </div>
          </div>

          {testResult && (
            <div className="space-y-2 pt-4 border-t border-slate-800/60">
              <span className="text-xs font-semibold text-slate-300 font-mono">Agent Output Response</span>
              <div className="p-4 bg-slate-950 rounded-xl border border-slate-800 text-xs font-mono text-slate-200 whitespace-pre-wrap leading-relaxed">
                {testResult}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
