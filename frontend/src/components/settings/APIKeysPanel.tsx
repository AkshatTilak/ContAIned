import React, { useState, useEffect } from "react";
import { Key, Plus, Trash2, Copy, Check, ShieldAlert, Activity, RefreshCw } from "lucide-react";
import { useToast } from "../shared";

interface APIKeyItem {
  id: number;
  prefix: string;
  name: string;
  rate_limit: number;
  usage_count: number;
  is_active: boolean;
  last_used_at: string | null;
  created_at: string;
}

export const APIKeysPanel: React.FC = () => {
  const [keys, setKeys] = useState<APIKeyItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [newKeyName, setNewKeyName] = useState<string>("");
  const [newKeyRateLimit, setNewKeyRateLimit] = useState<number>(60);
  const [createdRawKey, setCreatedRawKey] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<boolean>(false);

  const { success, error } = useToast();

  const fetchKeys = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/settings/api-keys");
      if (!res.ok) throw new Error("Failed to fetch API keys");
      const data = await res.json();
      setKeys(data);
    } catch (err: any) {
      error("Error", err.message || "Failed to load API keys.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchKeys();
  }, []);

  const handleCreateKey = async () => {
    if (!newKeyName.trim()) {
      error("Validation Error", "Please provide a name for the API key.");
      return;
    }
    try {
      const res = await fetch("/api/settings/api-keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newKeyName, rate_limit: newKeyRateLimit }),
      });
      if (!res.ok) throw new Error("Failed to generate API key");
      const data = await res.json();
      setCreatedRawKey(data.raw_key);
      success("API Key Generated", "Your new API key has been generated.");
      fetchKeys();
    } catch (err: any) {
      error("Error", err.message || "Failed to create API key.");
    }
  };

  const handleToggleActive = async (keyItem: APIKeyItem) => {
    try {
      const res = await fetch(`/api/settings/api-keys/${keyItem.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: !keyItem.is_active }),
      });
      if (!res.ok) throw new Error("Failed to update key status");
      success("Status Updated", `Key '${keyItem.name}' is now ${!keyItem.is_active ? "active" : "inactive"}.`);
      fetchKeys();
    } catch (err: any) {
      error("Error", err.message || "Failed to update key status.");
    }
  };

  const handleRevokeKey = async (id: number, name: string) => {
    if (!confirm(`Are you sure you want to revoke API key '${name}'? This action cannot be undone.`)) return;
    try {
      const res = await fetch(`/api/settings/api-keys/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Failed to revoke API key");
      success("Key Revoked", `API key '${name}' has been revoked.`);
      fetchKeys();
    } catch (err: any) {
      error("Error", err.message || "Failed to revoke key.");
    }
  };

  const copyToClipboard = (text: str) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2000);
  };

  return (
    <div className="bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-xl p-6 space-y-6 shadow-sm">
      <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <Key className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold font-display text-[var(--text-primary)]">
              OpenAI API Keys Gateway
            </h3>
            <p className="text-xs text-[var(--text-muted)]">
              Manage secret keys (`sk-...`) for OpenAI SDK compatibility and external REST API access.
            </p>
          </div>
        </div>
        <button
          onClick={() => {
            setNewKeyName("");
            setNewKeyRateLimit(60);
            setCreatedRawKey(null);
            setShowCreateModal(true);
          }}
          className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-xs font-semibold text-white shadow-md transition-all"
        >
          <Plus className="w-4 h-4" />
          <span>Generate New Key</span>
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-8 text-xs text-[var(--text-muted)] gap-2">
          <RefreshCw className="w-4 h-4 animate-spin text-emerald-400" />
          <span>Loading API keys...</span>
        </div>
      ) : keys.length === 0 ? (
        <div className="text-center py-8 border border-dashed border-[var(--border-default)] rounded-xl">
          <Key className="w-8 h-8 text-[var(--text-muted)] mx-auto mb-2 opacity-50" />
          <p className="text-xs text-[var(--text-secondary)] font-medium">No API Keys Generated</p>
          <p className="text-[11px] text-[var(--text-muted)] mt-0.5">Create your first API key to use external SDKs.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-[var(--border-default)] text-[var(--text-muted)] uppercase tracking-wider text-[10px]">
                <th className="py-2.5 px-3">Name</th>
                <th className="py-2.5 px-3">Key Prefix</th>
                <th className="py-2.5 px-3">Rate Limit</th>
                <th className="py-2.5 px-3">Invocations</th>
                <th className="py-2.5 px-3">Last Used</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-subtle)]">
              {keys.map((k) => (
                <tr key={k.id} className="hover:bg-[var(--bg-elevated)] transition-colors">
                  <td className="py-3 px-3 font-semibold text-[var(--text-primary)]">{k.name}</td>
                  <td className="py-3 px-3 font-mono text-zinc-400">{k.prefix}...</td>
                  <td className="py-3 px-3 text-[var(--text-secondary)]">{k.rate_limit} req/min</td>
                  <td className="py-3 px-3 text-[var(--text-secondary)]">{k.usage_count}</td>
                  <td className="py-3 px-3 text-[var(--text-muted)]">
                    {k.last_used_at ? new Date(k.last_used_at).toLocaleDateString() : "Never"}
                  </td>
                  <td className="py-3 px-3">
                    <button
                      onClick={() => handleToggleActive(k)}
                      className={`px-2 py-0.5 rounded-full text-[10px] font-semibold transition-all ${
                        k.is_active
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          : "bg-zinc-500/10 text-zinc-400 border border-zinc-500/20"
                      }`}
                    >
                      {k.is_active ? "Active" : "Inactive"}
                    </button>
                  </td>
                  <td className="py-3 px-3 text-right">
                    <button
                      onClick={() => handleRevokeKey(k.id, k.name)}
                      className="p-1.5 rounded hover:bg-rose-500/10 text-rose-400 transition-colors"
                      title="Revoke Key"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-xl max-w-md w-full p-6 space-y-4 shadow-xl">
            <h3 className="text-sm font-bold font-display text-[var(--text-primary)]">
              {createdRawKey ? "API Key Generated Successfully" : "Generate New API Key"}
            </h3>

            {!createdRawKey ? (
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">Key Name</label>
                  <input
                    type="text"
                    value={newKeyName}
                    onChange={(e) => setNewKeyName(e.target.value)}
                    placeholder="e.g. Production Server Key"
                    className="w-full px-3.5 py-2 rounded-lg bg-[var(--bg-input)] border border-[var(--border-default)] text-xs text-[var(--text-primary)] focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">Rate Limit (requests / min)</label>
                  <input
                    type="number"
                    value={newKeyRateLimit}
                    onChange={(e) => setNewKeyRateLimit(parseInt(e.target.value) || 60)}
                    min={1}
                    max={1000}
                    className="w-full px-3.5 py-2 rounded-lg bg-[var(--bg-input)] border border-[var(--border-default)] text-xs text-[var(--text-primary)] focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <button
                    onClick={() => setShowCreateModal(false)}
                    className="px-3 py-1.5 rounded-lg bg-[var(--bg-input)] hover:bg-[var(--bg-elevated)] border border-[var(--border-default)] text-xs text-[var(--text-muted)]"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleCreateKey}
                    className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-xs font-semibold text-white"
                  >
                    Generate
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg flex items-start gap-2 text-xs text-amber-300">
                  <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>Copy this key now. For security reasons, you will not be able to view it again.</span>
                </div>

                <div className="flex items-center gap-2 p-3 bg-[var(--bg-input)] border border-[var(--border-default)] rounded-lg font-mono text-xs text-emerald-400">
                  <span className="truncate select-all">{createdRawKey}</span>
                  <button
                    onClick={() => copyToClipboard(createdRawKey)}
                    className="p-1 hover:bg-[var(--bg-elevated)] rounded text-zinc-300 ml-auto shrink-0"
                  >
                    {copiedKey ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                  </button>
                </div>

                <div className="flex justify-end pt-2">
                  <button
                    onClick={() => setShowCreateModal(false)}
                    className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-xs font-semibold text-white"
                  >
                    Done
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
