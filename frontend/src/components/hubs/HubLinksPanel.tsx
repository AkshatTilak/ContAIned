import { useState, useEffect, useMemo } from "react";
import {
  Link2,
  Plus,
  Trash2,
  AlertCircle,
  Loader2,
  Check,
  ArrowRight,
  ShieldAlert,
} from "lucide-react";
import { useHubPermissions } from "../../hooks/useHubPermissions";
import { useHubContext } from "./HubContext";
import { api } from "../../services/api";
import { useStore } from "../../store/useStore";
import type { HubLink, HubAccessLevel, HubType, Hub } from "../../types/api";

export const ALLOWED_LINK_TARGETS: Record<HubType, HubType[]> = {
  agent: ["ingestion"],
  workflow: ["agent", "ingestion"],
  eval: ["workflow", "agent"],
  ingestion: [], // Ingestion hubs never consume another hub
};

export function HubLinksPanel() {
  const { hub } = useHubContext();
  const { can, isArchived } = useHubPermissions();

  const hubsById = useStore((state) => state.hubsById);
  const existingHubs = useMemo(() => Object.values(hubsById), [hubsById]);

  const [outgoingLinks, setOutgoingLinks] = useState<HubLink[]>([]);
  const [incomingLinks, setIncomingLinks] = useState<HubLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [targetHubId, setTargetHubId] = useState("");
  const [accessLevel, setAccessLevel] = useState<HubAccessLevel>("use");
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const fetchLinks = async () => {
    if (!hub) return;
    setLoading(true);
    setError(null);
    try {
      const [outLinks, inLinks] = await Promise.all([
        api.hubs.links.list(hub.id),
        api.hubs.links.dependents(hub.id),
      ]);
      setOutgoingLinks(outLinks);
      setIncomingLinks(inLinks);
    } catch (err: any) {
      setError(err?.message || "Failed to load hub links");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLinks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hub?.id]);

  const legalTargetTypes = hub ? ALLOWED_LINK_TARGETS[hub.hub_type] || [] : [];
  const eligibleTargetHubs = useMemo(() => {
    if (!hub) return [];
    return existingHubs.filter(
      (h) => h.id !== hub.id && legalTargetTypes.includes(h.hub_type) && !h.is_archived
    );
  }, [existingHubs, legalTargetTypes, hub]);

  const handleCreateLink = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!hub || !targetHubId) return;
    setCreateSubmitting(true);
    setCreateError(null);
    try {
      await api.hubs.links.create(hub.id, {
        target_hub_id: targetHubId,
        access_level: accessLevel,
      });
      setIsCreateOpen(false);
      setTargetHubId("");
      fetchLinks();
    } catch (err: any) {
      setCreateError(err?.message || "Failed to create hub link");
    } finally {
      setCreateSubmitting(false);
    }
  };

  const handleRevokeLink = async (linkId: string) => {
    if (!hub) return;
    try {
      await api.hubs.links.revoke(hub.id, linkId);
      fetchLinks();
    } catch (err: any) {
      console.error("Failed to revoke link:", err);
    }
  };

  if (loading) {
    return (
      <div className="p-8 text-center space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mx-auto" />
        <p className="text-sm text-slate-400">Loading hub links...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold font-display text-slate-100 flex items-center space-x-2">
            <Link2 className="w-5 h-5 text-indigo-400" />
            <span>Hub Links & Consumption Grants</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Configure cross-hub resource binding permissions per platform direction rules.
          </p>
        </div>

        {can("manage_links") && !isArchived && legalTargetTypes.length > 0 && (
          <button
            onClick={() => setIsCreateOpen(true)}
            className="flex items-center space-x-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs rounded-xl shadow-lg shadow-indigo-500/20 transition-all shrink-0"
          >
            <Plus className="w-4 h-4" />
            <span>Grant Link</span>
          </button>
        )}
      </div>

      {error && (
        <div className="p-4 bg-red-950/40 border border-red-800/40 rounded-xl text-red-300 text-xs flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Create Link Modal / Inline Form */}
      {isCreateOpen && (
        <form onSubmit={handleCreateLink} className="p-4 bg-slate-900/80 border border-indigo-500/30 rounded-xl space-y-4">
          <h3 className="text-sm font-semibold text-slate-200">Grant Outgoing Consumption Link</h3>
          {createError && <p className="text-xs text-red-400">{createError}</p>}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <select
              value={targetHubId}
              onChange={(e) => setTargetHubId(e.target.value)}
              required
              className="sm:col-span-2 bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
            >
              <option value="">Select Target Hub...</option>
              {eligibleTargetHubs.map((h) => (
                <option key={h.id} value={h.id}>
                  {h.name} ({h.hub_type}/{h.slug})
                </option>
              ))}
            </select>

            <select
              value={accessLevel}
              onChange={(e) => setAccessLevel(e.target.value as HubAccessLevel)}
              className="bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
            >
              <option value="use">Access: Use (Execute & Bind)</option>
              <option value="read">Access: Read Only</option>
            </select>
          </div>
          <div className="flex justify-end space-x-2">
            <button
              type="button"
              onClick={() => setIsCreateOpen(false)}
              className="px-3 py-1.5 bg-slate-800 text-slate-300 text-xs font-medium rounded-lg hover:bg-slate-700"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createSubmitting || !targetHubId}
              className="px-3 py-1.5 bg-indigo-600 text-white text-xs font-medium rounded-lg hover:bg-indigo-500 flex items-center space-x-1"
            >
              {createSubmitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
              <span>Establish Grant</span>
            </button>
          </div>
        </form>
      )}

      {/* Outgoing Links Section */}
      <section className="space-y-3">
        <div className="flex items-center space-x-2">
          <ArrowRight className="w-4 h-4 text-indigo-400" />
          <h3 className="text-sm font-bold text-slate-200">Outgoing Links (Consumed Hubs)</h3>
        </div>

        <div className="bg-slate-900/50 border border-slate-800/80 rounded-xl overflow-hidden shadow-lg">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-950/60 border-b border-slate-800 text-slate-400 font-semibold">
              <tr>
                <th className="p-3.5">Target Hub</th>
                <th className="p-3.5">Target Type</th>
                <th className="p-3.5">Access Level</th>
                <th className="p-3.5">Granted Date</th>
                {can("manage_links") && !isArchived && <th className="p-3.5 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {outgoingLinks.length === 0 ? (
                <tr>
                  <td colSpan={5} className="p-6 text-center text-slate-500">
                    This hub does not consume any target hubs yet.
                  </td>
                </tr>
              ) : (
                outgoingLinks.map((link) => (
                  <tr key={link.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="p-3.5 font-semibold text-slate-100">
                      {link.target_hub_name || hubsById[link.target_hub_id]?.name || link.target_hub_id}
                    </td>
                    <td className="p-3.5 font-mono text-slate-400 uppercase">
                      {link.target_hub_type || hubsById[link.target_hub_id]?.hub_type || "—"}
                    </td>
                    <td className="p-3.5">
                      <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-indigo-950/60 text-indigo-300 border border-indigo-800/40 uppercase">
                        {link.access_level}
                      </span>
                    </td>
                    <td className="p-3.5 font-mono text-slate-400">
                      {new Date(link.created_at).toLocaleDateString()}
                    </td>
                    {can("manage_links") && !isArchived && (
                      <td className="p-3.5 text-right">
                        <button
                          onClick={() => handleRevokeLink(link.id)}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-950/40 transition-colors"
                          title="Revoke Link Grant"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    )}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Incoming Links Section */}
      <section className="space-y-3 pt-4 border-t border-slate-800/60">
        <div className="flex items-center space-x-2">
          <ShieldAlert className="w-4 h-4 text-amber-400" />
          <h3 className="text-sm font-bold text-slate-200">Incoming Links (Consuming Hubs - Read-only)</h3>
        </div>

        <div className="bg-slate-900/50 border border-slate-800/80 rounded-xl overflow-hidden shadow-lg">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-950/60 border-b border-slate-800 text-slate-400 font-semibold">
              <tr>
                <th className="p-3.5">Source Hub</th>
                <th className="p-3.5">Access Level</th>
                <th className="p-3.5">Granted Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {incomingLinks.length === 0 ? (
                <tr>
                  <td colSpan={3} className="p-6 text-center text-slate-500">
                    No other hubs consume this hub.
                  </td>
                </tr>
              ) : (
                incomingLinks.map((link) => (
                  <tr key={link.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="p-3.5">
                      <span className="font-semibold text-slate-100">
                        {link.source_hub_name || hubsById[link.source_hub_id]?.name || link.source_hub_id}
                      </span>
                      {link.source_hub_name || hubsById[link.source_hub_id]?.name ? (
                        <span className="ml-2 text-[10px] font-mono text-slate-500">{link.source_hub_id}</span>
                      ) : null}
                    </td>
                    <td className="p-3.5">
                      <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-800 text-slate-300 border border-slate-700 uppercase">
                        {link.access_level}
                      </span>
                    </td>
                    <td className="p-3.5 font-mono text-slate-400">
                      {new Date(link.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
