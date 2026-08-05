import { useEffect, useState } from "react";
import { Loader2, Key, Trash2, AlertCircle, Save, Edit2, ShieldCheck } from "lucide-react";
import { api } from "../../services/api";
import { useStore } from "../../store/useStore";

const PROVIDERS = [
  { id: "google", name: "Google (Gemini)", envVar: "GOOGLE_API_KEY" },
  { id: "openai", name: "OpenAI", envVar: "OPENAI_API_KEY" },
  { id: "openrouter", name: "OpenRouter", envVar: "OPENROUTER_API_KEY" },
  { id: "groq", name: "Groq", envVar: "GROQ_API_KEY" },
  { id: "anthropic", name: "Anthropic", envVar: "ANTHROPIC_API_KEY" },
  { id: "cerebras", name: "Cerebras", envVar: "CEREBRAS_API_KEY" },
  { id: "mistral", name: "Mistral AI", envVar: "MISTRAL_API_KEY" },
  { id: "cohere", name: "Cohere", envVar: "COHERE_API_KEY" },
  { id: "langsmith", name: "LangSmith", envVar: "LANGSMITH_API_KEY" },
];

export function CredentialsSettings() {
  const [credentials, setCredentials] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [provider, setProvider] = useState(PROVIDERS[0].id);
  const [apiKey, setApiKey] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const addNotification = useStore((state) => state.addNotification);

  const fetchCredentials = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.admin.credentials.list();
      setCredentials(res.items || []);
    } catch (err: any) {
      setError(err?.message || "Failed to load credentials.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCredentials();
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKey.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.admin.credentials.upsert({
        provider,
        api_key: apiKey.trim(),
      });
      const selectedP = PROVIDERS.find((p) => p.id === provider);
      addNotification({
        type: "success",
        title: "Credential Saved",
        message: `Successfully updated ${selectedP?.name || provider} API key credential.`,
      });
      setApiKey("");
      fetchCredentials();
    } catch (err: any) {
      const msg = err?.message || "Failed to save credential";
      setError(msg);
      addNotification({
        type: "error",
        title: "Save Failed",
        message: msg,
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleRemove = async (providerId: string) => {
    const selectedP = PROVIDERS.find((p) => p.id === providerId);
    const pName = selectedP?.name || providerId;

    if (!window.confirm(`Are you sure you want to remove the ${pName} credential? Models relying on it will stop working.`)) {
      return;
    }
    try {
      await api.admin.credentials.remove(providerId);
      addNotification({
        type: "info",
        title: "Credential Removed",
        message: `Removed ${pName} credential.`,
      });
      fetchCredentials();
    } catch (err: any) {
      setError(err?.message || "Failed to remove credential");
    }
  };

  const handleEditSelect = (providerId: string) => {
    setProvider(providerId);
    setApiKey("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  if (loading) {
    return (
      <div className="flex justify-center p-8">
        <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {error && (
        <div className="p-4 bg-red-950/40 border border-red-800/40 rounded-xl text-red-300 text-xs flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Input Form */}
      <form onSubmit={handleSave} className="p-6 bg-slate-900/40 border border-slate-800 rounded-xl space-y-4 shadow-lg">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-200 flex items-center space-x-2 font-display">
            <Key className="w-4 h-4 text-indigo-400" />
            <span>Add or Update Provider Credential</span>
          </h3>
          <span className="text-[11px] font-mono text-slate-500">
            Keys override .env defaults dynamically in memory & DB
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400">Provider</label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="w-full bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
            >
              {PROVIDERS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.envVar})
                </option>
              ))}
            </select>
          </div>

          <div className="sm:col-span-2 space-y-1.5">
            <label className="text-xs font-medium text-slate-400">API Key</label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={`Enter new API Key for ${PROVIDERS.find((p) => p.id === provider)?.name || provider}...`}
              className="w-full bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500 font-mono"
            />
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={submitting || !apiKey.trim()}
            className="flex items-center space-x-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium text-xs rounded-lg transition-colors cursor-pointer"
          >
            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            <span>Save Credential</span>
          </button>
        </div>
      </form>

      {/* Configured Credentials Table */}
      <div className="bg-slate-900/40 border border-slate-800 rounded-xl overflow-hidden shadow-lg">
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-200 font-display">Configured Provider Credentials</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Active LLM API keys detected from local <code>.env</code> file or saved database overrides.
            </p>
          </div>
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-slate-950 border border-slate-800 text-[11px] text-slate-400">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>Active Keys: <strong>{credentials.length}</strong></span>
          </div>
        </div>

        {credentials.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-500 space-y-2">
            <p>No provider credentials configured in environment or database.</p>
            <p className="text-[11px] text-slate-600 font-mono">Set GOOGLE_API_KEY, OPENAI_API_KEY, etc. in .env or add them using the form above.</p>
          </div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-950/60 text-slate-400 border-b border-slate-800 text-xs">
              <tr>
                <th className="px-6 py-3.5 font-semibold">Provider</th>
                <th className="px-6 py-3.5 font-semibold">Configuration Source</th>
                <th className="px-6 py-3.5 font-semibold">Masked API Key</th>
                <th className="px-6 py-3.5 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {credentials.map((cred) => {
                const providerInfo = PROVIDERS.find((p) => p.id === cred.provider.lower?.() || p.id === cred.provider);
                const displayName = providerInfo?.name || cred.provider.toUpperCase();
                const isEnv = cred.source === "env";

                return (
                  <tr key={cred.id} className="hover:bg-slate-800/20 transition-colors">
                    <td className="px-6 py-3.5 font-semibold text-slate-200">
                      <div className="flex items-center space-x-2">
                        <span>{displayName}</span>
                        {providerInfo?.envVar && (
                          <span className="text-[10px] font-mono text-slate-500 bg-slate-950 px-1.5 py-0.5 rounded border border-slate-800">
                            {providerInfo.envVar}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-3.5">
                      {isEnv ? (
                        <span className="px-2.5 py-1 rounded-full text-[11px] font-mono font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20">
                          .env File
                        </span>
                      ) : (
                        <span className="px-2.5 py-1 rounded-full text-[11px] font-mono font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                          DB Override
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-3.5 font-mono text-xs text-slate-300">
                      {cred.masked_key || "****"}
                    </td>
                    <td className="px-6 py-3.5 text-right">
                      <div className="flex items-center justify-end space-x-2">
                        <button
                          onClick={() => handleEditSelect(cred.provider)}
                          className="p-1.5 text-indigo-400 hover:text-indigo-300 hover:bg-indigo-500/10 rounded-lg transition-colors flex items-center space-x-1 text-xs"
                          title="Update Credential"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                          <span>Change</span>
                        </button>
                        <button
                          onClick={() => handleRemove(cred.provider)}
                          className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                          title="Remove Credential"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
