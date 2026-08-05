import React, { useEffect, useState, useRef } from "react";
import { api } from "../../services/api";
import { Loader2, AlertCircle } from "lucide-react";

interface ModelSelectorProps {
  value: string;
  onChange: (modelId: string) => void;
  role: "completion" | "embedding" | "ocr" | "asr" | "classifier";
}

const CLOUD_PROVIDERS = [
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

export const ModelSelector: React.FC<ModelSelectorProps> = ({ value, onChange, role }) => {
  const [registry, setRegistry] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [fetchingLiteLLM, setFetchingLiteLLM] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Selector choices
  const [mode, setMode] = useState<"local" | "cloud">("cloud");
  const [provider, setProvider] = useState<string>("google");
  const [modelsList, setModelsList] = useState<any[]>([]);
  
  const initializedRef = useRef(false);

  // 1. Initial Load of DB Registry (runs ONCE per role, NOT on every value change)
  useEffect(() => {
    const fetchRegistry = async () => {
      setLoading(true);
      try {
        const reg = await api.getModels();
        setRegistry(reg);
        
        if (!initializedRef.current) {
          initializedRef.current = true;
          
          // Try to deduce mode/provider from current value
          let matched: any = null;
          for (const roleKey of Object.keys(reg)) {
            const list = reg[roleKey]?.available || [];
            matched = list.find((m: any) => m.model_id === value);
            if (matched) break;
          }

          if (matched) {
            setMode(matched.mode);
            setProvider(matched.provider);
          } else if (value) {
            // Deduce from string prefix if not in DB
            const valLower = value.toLowerCase();
            if (valLower.startsWith("openai/") || valLower.includes("text-embedding")) {
              setMode("cloud");
              setProvider("openai");
            } else if (valLower.startsWith("anthropic/")) {
              setMode("cloud");
              setProvider("anthropic");
            } else if (valLower.startsWith("groq/")) {
              setMode("cloud");
              setProvider("groq");
            } else if (valLower.startsWith("openrouter/")) {
              setMode("cloud");
              setProvider("openrouter");
            } else {
              setMode("cloud");
              setProvider("google");
            }
          } else {
            setMode("cloud");
            setProvider("google");
          }
        }
      } catch (err: any) {
        setError("Failed to fetch model registry.");
      } finally {
        setLoading(false);
      }
    };
    fetchRegistry();
  }, [role]);

  // Check if provider API key is configured from the registry payload
  const isProviderConfigured = (prov: string) => {
    if (!registry) return true;
    for (const r of Object.keys(registry)) {
      const list = registry[r]?.available || [];
      const found = list.find(
        (m: any) => m.provider.toLowerCase() === prov.toLowerCase() && m.mode === "cloud"
      );
      if (found) {
        return found.is_selectable;
      }
    }
    return true; // fallback
  };

  // 2. Fetch or filter models when Mode or Provider changes
  useEffect(() => {
    if (!registry) return;

    if (mode === "local") {
      // Local models are purely read from DB registry
      const list = registry[role]?.available || [];
      const filtered = list.filter((m: any) => m.mode === "local" && (provider === "" || m.provider === provider));
      setModelsList(filtered);
      
      // Auto select first local if current value is not in filtered list
      if (filtered.length > 0 && !filtered.some((m) => m.model_id === value)) {
        onChange(filtered[0].model_id);
      }
    } else {
      // Cloud models: dynamic LiteLLM query based on provider!
      const fetchLiteLLM = async () => {
        if (!provider) return;
        setFetchingLiteLLM(true);
        try {
          const res = await api.localModels.getLiteLLMModels(provider);
          // Filter models matching role mode
          const matches = (res.items || []).filter((m: any) => {
            if (role === "embedding") return m.mode === "embedding";
            return m.mode !== "embedding";
          });

          const mapped = matches.map((m: any) => ({
            model_id: m.name,
            display_name: m.name.split("/").pop() || m.name,
            provider: provider,
            is_selectable: isProviderConfigured(provider),
          }));
          
          setModelsList(mapped);

          // Auto select first match if current value is empty or not in mapped list
          if (mapped.length > 0 && !mapped.some((m) => m.model_id === value)) {
            onChange(mapped[0].model_id);
          }
        } catch (err) {
          console.warn("Dynamic LiteLLM query failed, falling back to DB registry", err);
          const list = registry[role]?.available || [];
          const filtered = list.filter((m: any) => m.mode === "cloud" && m.provider === provider);
          setModelsList(filtered);
        } finally {
          setFetchingLiteLLM(false);
        }
      };
      
      fetchLiteLLM();
    }
  }, [registry, mode, provider, role]);

  // 3. Handle Mode Switch explicitly
  const handleModeChange = (newMode: "local" | "cloud") => {
    setMode(newMode);
    if (newMode === "cloud") {
      setProvider("google");
    } else {
      if (registry) {
        const list = registry[role]?.available || [];
        const localProviders = list.filter((m: any) => m.mode === "local").map((m: any) => m.provider);
        if (localProviders.length > 0) {
          setProvider(localProviders[0]);
        }
      }
    }
  };

  // 4. Populate Provider Dropdown options based on Mode
  const providersOptions = React.useMemo(() => {
    if (mode === "cloud") {
      return CLOUD_PROVIDERS;
    } else {
      if (!registry) return [];
      const list = registry[role]?.available || [];
      const localProviders = list
        .filter((m: any) => m.mode === "local")
        .map((m: any) => m.provider);
      const unique = Array.from(new Set(localProviders));
      return unique.map((p: any) => ({ id: p, name: String(p).toUpperCase() }));
    }
  }, [registry, mode, role]);

  if (loading) {
    return (
      <div className="flex items-center space-x-2 py-2">
        <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
        <span className="text-xs text-slate-400">Loading model selectors...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-xs text-red-400 flex items-center space-x-1.5 py-1">
        <AlertCircle className="w-4.5 h-4.5" />
        <span>{error}</span>
      </div>
    );
  }

  const isConfigured = mode === "local" || isProviderConfigured(provider);

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 bg-slate-900/25 border border-slate-800/60 rounded-xl p-4">
        {/* 1. Mode Selector */}
        <div className="space-y-1">
          <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Mode</label>
          <select
            value={mode}
            onChange={(e) => handleModeChange(e.target.value as "local" | "cloud")}
            className="w-full bg-slate-950/80 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-indigo-500 cursor-pointer"
          >
            <option value="cloud">Cloud API</option>
            <option value="local">Local execution</option>
          </select>
        </div>

        {/* 2. Provider Selector */}
        <div className="space-y-1">
          <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Provider</label>
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            className="w-full bg-slate-950/80 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-indigo-500 capitalize cursor-pointer"
          >
            {providersOptions.map((prov) => (
              <option key={prov.id} value={prov.id}>{prov.name}</option>
            ))}
            {providersOptions.length === 0 && (
              <option value="">No providers</option>
            )}
          </select>
        </div>

        {/* 3. Model Selector */}
        <div className="space-y-1">
          <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center space-x-1">
            <span>Model</span>
            {fetchingLiteLLM && <Loader2 className="w-3 h-3 animate-spin text-slate-400" />}
          </label>
          <select
            value={value}
            onChange={(e) => onChange(e.target.value)}
            disabled={fetchingLiteLLM}
            className="w-full bg-slate-950/80 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-indigo-500 font-mono cursor-pointer disabled:opacity-50"
          >
            {modelsList.map((m) => (
              <option key={m.model_id} value={m.model_id} disabled={!m.is_selectable}>
                {m.display_name} {!m.is_selectable ? "(Key Missing)" : ""}
              </option>
            ))}
            {modelsList.length === 0 && !fetchingLiteLLM && (
              <option value="" disabled>No models available</option>
            )}
          </select>
        </div>
      </div>

      {!isConfigured && (
        <div className="text-[10px] text-amber-400 bg-amber-950/20 border border-amber-900/40 rounded-lg px-3 py-1.5 flex items-center space-x-1.5">
          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
          <span>Warning: API key is not configured for {provider.toUpperCase()} provider in Settings.</span>
        </div>
      )}
    </div>
  );
};
