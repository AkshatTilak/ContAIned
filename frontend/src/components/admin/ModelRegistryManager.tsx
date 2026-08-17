import { useEffect, useState } from "react";
import { Loader2, Plus, Star, Trash2, AlertCircle, Box, Settings, Cpu, ShieldCheck, RefreshCw, Layers, Save } from "lucide-react";
import { api } from "../../services/api";
import { useStore } from "../../store/useStore";

const PROVIDERS = [
  { id: "google", name: "Google (Gemini)" },
  { id: "openai", name: "OpenAI" },
  { id: "anthropic", name: "Anthropic" },
  { id: "openrouter", name: "OpenRouter" },
  { id: "groq", name: "Groq" },
  { id: "cerebras", name: "Cerebras" },
  { id: "mistral", name: "Mistral AI" },
  { id: "cohere", name: "Cohere" },
  { id: "xai", name: "xAI (Grok)" },
];

const ROLES = [
  { id: "completion", name: "Text Completion (LLM)" },
  { id: "embedding", name: "Vector Embedding" },
  { id: "classifier", name: "Routing Classifier" },
  { id: "ocr", name: "OCR Extraction" },
  { id: "asr", name: "Speech Recognition (ASR)" },
];

export function ModelRegistryManager() {
  const [registry, setRegistry] = useState<any>(null);
  const [localStatus, setLocalStatus] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form State
  const [mode, setMode] = useState<"local" | "cloud">("cloud");
  const [provider, setProvider] = useState(PROVIDERS[0].id);
  const [role, setRole] = useState(ROLES[0].id);
  const [modelId, setModelId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [vramMb, setVramMb] = useState(0);
  const [makeDefault, setMakeDefault] = useState(false);

  // LiteLLM Dynamic Options
  const [availableLiteLLM, setAvailableLiteLLM] = useState<any[]>([]);
  const [fetchingLiteLLM, setFetchingLiteLLM] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const addNotification = useStore((state) => state.addNotification);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const regRes = await api.getModels();
      setRegistry(regRes);

      const localRes = await api.localModels.status();
      setLocalStatus(localRes.items || []);
    } catch (err: any) {
      setError(err?.message || "Failed to load model registry.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Fetch LiteLLM Models dynamically when Provider or Role changes
  useEffect(() => {
    if (mode === "cloud") {
      fetchLiteLLMModels();
    }
  }, [provider, role, mode]);

  const fetchLiteLLMModels = async () => {
    setFetchingLiteLLM(true);
    setAvailableLiteLLM([]);
    try {
      const res = await api.localModels.getLiteLLMModels(provider);
      // Filter models that match target role/mode
      const matches = (res.items || []).filter((m: any) => {
        if (role === "embedding") return m.mode === "embedding";
        return m.mode !== "embedding";
      });
      setAvailableLiteLLM(matches);
      if (matches.length > 0) {
        setModelId(matches[0].name);
        setDisplayName(matches[0].name.split("/").pop() || matches[0].name);
      } else {
        setModelId("");
        setDisplayName("");
      }
    } catch (err) {
      console.warn("Could not fetch LiteLLM models dynamically:", err);
    } finally {
      setFetchingLiteLLM(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!modelId.trim() || !displayName.trim()) return;

    setActionLoading("registering");
    setError(null);
    try {
      await api.localModels.register({
        role,
        mode,
        provider,
        model_id: modelId.trim(),
        display_name: displayName.trim(),
        vram_mb: vramMb,
        is_default: makeDefault,
      });

      addNotification({
        type: "success",
        title: "Model Registered",
        message: `Registered model ${displayName} successfully.`,
      });

      // Clear/Reset form
      setApiKeyInputIfNeeded();
      setMakeDefault(false);
      await loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to register model");
    } finally {
      setActionLoading(null);
    }
  };

  const setApiKeyInputIfNeeded = () => {
    if (mode === "local") {
      setModelId("");
      setDisplayName("");
      setVramMb(0);
    }
  };

  const handleSelectDefault = async (role: string, modelId: string) => {
    setActionLoading(`select-${role}`);
    try {
      await api.localModels.selectActive(role, modelId);
      addNotification({
        type: "success",
        title: "Default Model Updated",
        message: `Set ${modelId} as the active default model for ${role}.`,
      });
      await loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to set default model");
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeleteModel = async (modelId: string, displayName: string) => {
    if (!window.confirm(`Are you sure you want to delete ${displayName} from the model registry?`)) {
      return;
    }
    setActionLoading(`delete-${modelId}`);
    try {
      await api.localModels.delete(modelId);
      addNotification({
        type: "info",
        title: "Model Deleted",
        message: `Removed ${displayName} from registry.`,
      });
      await loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to delete model");
    } finally {
      setActionLoading(null);
    }
  };

  const handleToggleLocal = async (modelId: string, isRunning: boolean) => {
    setActionLoading(`local-${modelId}`);
    try {
      if (isRunning) {
        await api.localModels.stop(modelId);
        addNotification({ type: "info", title: "Model Stopped", message: `Unloaded ${modelId} from VRAM.` });
      } else {
        await api.localModels.start(modelId);
        addNotification({ type: "success", title: "Model Loaded", message: `Loaded ${modelId} into VRAM.` });
      }
      await loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to alter local model execution state.");
    } finally {
      setActionLoading(null);
    }
  };

  if (loading && !registry) {
    return (
      <div className="flex justify-center p-8">
        <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
      </div>
    );
  }

  // Flatten all available models in the registry
  const allRegisteredModels: any[] = [];
  if (registry) {
    Object.keys(registry).forEach((roleKey) => {
      const info = registry[roleKey];
      if (info?.available) {
        info.available.forEach((m: any) => {
          allRegisteredModels.push({
            ...m,
            roleKey,
            isActiveDefault: info.active?.model_id === m.model_id,
          });
        });
      }
    });
  }

  return (
    <div className="space-y-8">
      {error && (
        <div className="p-4 bg-red-950/40 border border-red-800/40 rounded-xl text-red-300 text-xs flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Row 1: Default Model Selectors */}
      <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-6 space-y-4 shadow-lg">
        <div className="flex justify-between items-center">
          <h3 className="text-sm font-bold text-slate-200 flex items-center space-x-2 font-display">
            <Settings className="w-4 h-4 text-indigo-400" />
            <span>Active Default Models</span>
          </h3>
          <button onClick={loadData} className="p-1.5 hover:bg-slate-800 rounded-lg text-slate-400 transition-colors">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
          {ROLES.map((r) => {
            const currentActive = registry?.[r.id]?.active;
            const availableList = registry?.[r.id]?.available || [];

            return (
              <div key={r.id} className="bg-slate-950/60 border border-slate-800/60 rounded-xl p-3.5 space-y-2.5 flex flex-col justify-between">
                <div>
                  <span className="text-[10px] font-mono uppercase bg-slate-800 px-2 py-0.5 rounded border border-slate-700 text-slate-400">
                    {r.name}
                  </span>
                  <p className="text-xs text-slate-200 font-semibold mt-2 truncate">
                    {currentActive?.display_name || "None Selected"}
                  </p>
                  <p className="text-[10px] text-slate-500 font-mono truncate mt-0.5">
                    {currentActive?.model_id || "No model active"}
                  </p>
                </div>

                <div className="pt-2 border-t border-slate-800/50">
                  <select
                    disabled={actionLoading === `select-${r.id}`}
                    value={currentActive?.model_id || ""}
                    onChange={(e) => handleSelectDefault(r.id, e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded px-2 py-1 text-xs text-slate-300 focus:outline-none"
                  >
                    <option value="" disabled>Select active model...</option>
                    {availableList.map((m: any) => (
                      <option key={m.model_id} value={m.model_id}>
                        {m.display_name} ({m.mode})
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Row 2: Register New Model Form */}
      <form onSubmit={handleRegister} className="p-6 bg-slate-900/40 border border-slate-800 rounded-xl space-y-4 shadow-lg">
        <h3 className="text-sm font-bold text-slate-200 flex items-center space-x-2 font-display">
          <Plus className="w-4.5 h-4.5 text-indigo-400" />
          <span>Register New Model</span>
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400">Execution Mode</label>
            <select
              value={mode}
              onChange={(e: any) => setMode(e.target.value)}
              className="w-full bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none"
            >
              <option value="cloud">Cloud (LiteLLM / API Keys)</option>
              <option value="local">Local (Inference Server / VRAM)</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400">Provider</label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="w-full bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none"
            >
              {mode === "cloud" ? (
                PROVIDERS.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))
              ) : (
                <>
                  <option value="huggingface">HuggingFace (GGUF/Gemma)</option>
                  <option value="funasr">FunASR</option>
                  <option value="baidu">Baidu OCR</option>
                  <option value="pip">Python PIP package</option>
                </>
              )}
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400">Model Role</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="w-full bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none"
            >
              {ROLES.map((r) => (
                <option key={r.id} value={r.id}>{r.name}</option>
              ))}
            </select>
          </div>

          {mode === "cloud" ? (
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-400 flex items-center space-x-1">
                <span>Select LiteLLM Model</span>
                {fetchingLiteLLM && <Loader2 className="w-3 h-3 animate-spin text-slate-400" />}
              </label>
              <select
                value={modelId}
                onChange={(e) => {
                  setModelId(e.target.value);
                  const selectedName = availableLiteLLM.find((x) => x.name === e.target.value)?.name || e.target.value;
                  setDisplayName(selectedName.split("/").pop() || selectedName);
                }}
                disabled={fetchingLiteLLM}
                className="w-full bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none"
              >
                {availableLiteLLM.length === 0 ? (
                  <option value="">No models found for provider</option>
                ) : (
                  availableLiteLLM.map((m) => (
                    <option key={m.name} value={m.name}>{m.name}</option>
                  ))
                )}
              </select>
            </div>
          ) : (
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-400">Model ID / Hub Path</label>
              <input
                type="text"
                value={modelId}
                onChange={(e) => setModelId(e.target.value)}
                placeholder="e.g. Qwen/Qwen2.5-7B"
                className="w-full bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none font-mono"
              />
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          <div className="space-y-1.5 sm:col-span-2">
            <label className="text-xs font-medium text-slate-400">Display Name</label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="e.g. Gemini 2.5 Flash Cloud"
              className="w-full bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none"
            />
          </div>

          {mode === "local" && (
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-400">VRAM Budget (MB)</label>
              <input
                type="number"
                value={vramMb}
                onChange={(e) => setVramMb(parseInt(e.target.value) || 0)}
                placeholder="0"
                className="w-full bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none font-mono"
              />
            </div>
          )}

          <div className="flex items-center gap-2 pt-8">
            <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={makeDefault}
                onChange={(e) => setMakeDefault(e.target.checked)}
                className="rounded bg-slate-950 border-slate-800 text-indigo-600 focus:ring-0"
              />
              <span>Set as Active Default</span>
            </label>
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={actionLoading === "registering" || !modelId.trim() || !displayName.trim()}
            className="flex items-center space-x-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium text-xs rounded-lg transition-colors cursor-pointer"
          >
            {actionLoading === "registering" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            <span>Register Model</span>
          </button>
        </div>
      </form>

      {/* Row 3: Model Listing & Controls */}
      <div className="bg-slate-900/40 border border-slate-800 rounded-xl overflow-hidden shadow-lg">
        <div className="px-6 py-4 border-b border-slate-800 flex justify-between items-center">
          <div>
            <h3 className="text-sm font-bold text-slate-200 font-display">Registered Models Registry</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Available models configured in the local orchestrator database.
            </p>
          </div>
          <span className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-slate-950 border border-slate-800 text-[11px] text-slate-400">
            <Layers className="w-3.5 h-3.5 text-indigo-400" />
            <span>Total Registered: <strong>{allRegisteredModels.length}</strong></span>
          </span>
        </div>

        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-slate-950/60 text-slate-400 border-b border-slate-800 font-semibold">
            <tr>
              <th className="px-6 py-3.5">Model Name & ID</th>
              <th className="px-6 py-3.5">Role</th>
              <th className="px-6 py-3.5">Provider / Mode</th>
              <th className="px-6 py-3.5">Local Execution Status</th>
              <th className="px-6 py-3.5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50">
            {allRegisteredModels.map((m) => {
              const localInfo = localStatus.find((l) => l.model_id === m.model_id);
              const isLocal = m.mode === "local";
              const isLocalRunning = localInfo?.is_running;

              return (
                <tr key={m.model_id} className="hover:bg-slate-800/25 transition-colors">
                  <td className="px-6 py-3.5 font-medium text-slate-200">
                    <div className="flex items-center space-x-2">
                      <span>{m.display_name}</span>
                      {m.isActiveDefault && (
                        <span className="flex items-center space-x-0.5 bg-indigo-500/10 text-indigo-400 border border-indigo-500/30 px-1.5 py-0.5 rounded text-[9px] uppercase font-mono">
                          <Star className="w-2.5 h-2.5 fill-current" />
                          <span>Active Default</span>
                        </span>
                      )}
                    </div>
                    <div className="text-[10px] text-slate-500 font-mono mt-0.5">{m.model_id}</div>
                  </td>
                  <td className="px-6 py-3.5">
                    <span className="px-2.5 py-1 rounded bg-slate-800 text-slate-400 font-semibold uppercase tracking-wider text-[9px] border border-slate-700/50">
                      {m.role}
                    </span>
                  </td>
                  <td className="px-6 py-3.5">
                    <div className="flex items-center space-x-1.5">
                      <span className="capitalize text-slate-300 font-medium">{m.provider}</span>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-mono ${isLocal ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20' : 'bg-blue-500/10 text-blue-400 border border-blue-500/20'}`}>
                        {m.mode}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-3.5">
                    {isLocal ? (
                      <div className="flex items-center space-x-2">
                        <span className={`w-2 h-2 rounded-full ${isLocalRunning ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'}`} />
                        <span className="text-slate-400">{isLocalRunning ? "Running" : "Stopped"}</span>
                        <button
                          disabled={actionLoading === `local-${m.model_id}`}
                          onClick={() => handleToggleLocal(m.model_id, !!isLocalRunning)}
                          className={`ml-2 px-2 py-1 rounded text-[10px] font-semibold cursor-pointer border ${isLocalRunning ? 'bg-red-500/10 border-red-500/20 text-red-400 hover:bg-red-500/20' : 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700'}`}
                        >
                          {isLocalRunning ? "Stop / Unload" : "Start / Load"}
                        </button>
                      </div>
                    ) : (
                      <span className="text-slate-500 font-mono text-[10px]">Cloud Execution</span>
                    )}
                  </td>
                  <td className="px-6 py-3.5 text-right">
                    <button
                      disabled={actionLoading === `delete-${m.model_id}`}
                      onClick={() => handleDeleteModel(m.model_id, m.display_name)}
                      className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors cursor-pointer"
                      title="Delete Model Configuration"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
