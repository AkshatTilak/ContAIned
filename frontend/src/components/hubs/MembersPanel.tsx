import { useState, useEffect, useMemo } from "react";
import {
  Users,
  Search,
  UserPlus,
  Shield,
  Trash2,
  AlertCircle,
  Loader2,
  Check,
} from "lucide-react";
import { useHubPermissions } from "../../hooks/useHubPermissions";
import { useHubContext } from "./HubContext";
import { api } from "../../services/api";
import type { HubMember, HubRole } from "../../types/api";

export function MembersPanel() {
  const { hub } = useHubContext();
  const { can, isArchived } = useHubPermissions();

  const [members, setMembers] = useState<HubMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState<string>("all");

  const [isInviteOpen, setIsInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<HubRole>("contributor");
  const [inviteSubmitting, setInviteSubmitting] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);

  const fetchMembers = async () => {
    if (!hub) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.hubs.members.list(hub.id);
      setMembers(data);
    } catch (err: any) {
      setError(err?.message || "Failed to load hub members");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMembers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hub?.id]);

  const handleRoleChange = async (userId: string, newRole: HubRole) => {
    if (!hub) return;
    try {
      await api.hubs.members.updateRole(hub.id, userId, newRole);
      fetchMembers();
    } catch (err: any) {
      console.error("Failed to update role:", err);
    }
  };

  const handleRemoveMember = async (userId: string) => {
    if (!hub) return;
    try {
      await api.hubs.members.remove(hub.id, userId);
      fetchMembers();
    } catch (err: any) {
      console.error("Failed to remove member:", err);
    }
  };

  const handleInviteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!hub || !inviteEmail.trim()) return;
    setInviteSubmitting(true);
    setInviteError(null);
    try {
      await api.hubs.members.invite(hub.id, {
        email: inviteEmail.trim(),
        hub_role: inviteRole,
      });
      setInviteEmail("");
      setIsInviteOpen(false);
      fetchMembers();
    } catch (err: any) {
      setInviteError(err?.message || "Failed to invite member");
    } finally {
      setInviteSubmitting(false);
    }
  };

  const filteredMembers = useMemo(() => {
    return members.filter((m) => {
      const email = (m.email ?? "").toLowerCase();
      const displayName = (m.display_name ?? "").toLowerCase();
      const q = searchQuery.toLowerCase();
      const matchesSearch =
        email.includes(q) || displayName.includes(q);
      const matchesRole = roleFilter === "all" || m.hub_role === roleFilter;
      return matchesSearch && matchesRole;
    });
  }, [members, searchQuery, roleFilter]);

  const ownerCount = useMemo(() => members.filter((m) => m.hub_role === "owner").length, [members]);

  if (loading) {
    return (
      <div className="p-8 text-center space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mx-auto" />
        <p className="text-sm text-slate-400">Loading hub members...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold font-display text-slate-100 flex items-center space-x-2">
            <Users className="w-5 h-5 text-indigo-400" />
            <span>Hub Members</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Manage access grants and member roles for this hub.
          </p>
        </div>

        {can("manage_members") && !isArchived && (
          <button
            onClick={() => setIsInviteOpen(true)}
            className="flex items-center space-x-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs rounded-xl shadow-lg shadow-indigo-500/20 transition-all shrink-0"
          >
            <UserPlus className="w-4 h-4" />
            <span>Add Member</span>
          </button>
        )}
      </div>

      {error && (
        <div className="p-4 bg-red-950/40 border border-red-800/40 rounded-xl text-red-300 text-xs flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Invite Modal / Inline Form */}
      {isInviteOpen && (
        <form onSubmit={handleInviteSubmit} className="p-4 bg-slate-900/80 border border-indigo-500/30 rounded-xl space-y-4">
          <h3 className="text-sm font-semibold text-slate-200">Invite User to Hub</h3>
          {inviteError && <p className="text-xs text-red-400">{inviteError}</p>}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <input
              type="email"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="user@company.com"
              required
              className="sm:col-span-2 bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
            />
            <select
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value as HubRole)}
              className="bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
            >
              <option value="maintainer">Maintainer</option>
              <option value="contributor">Contributor</option>
              <option value="viewer">Viewer</option>
            </select>
          </div>
          <div className="flex justify-end space-x-2">
            <button
              type="button"
              onClick={() => setIsInviteOpen(false)}
              className="px-3 py-1.5 bg-slate-800 text-slate-300 text-xs font-medium rounded-lg hover:bg-slate-700"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={inviteSubmitting}
              className="px-3 py-1.5 bg-indigo-600 text-white text-xs font-medium rounded-lg hover:bg-indigo-500 flex items-center space-x-1"
            >
              {inviteSubmitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
              <span>Send Grant</span>
            </button>
          </div>
        </form>
      )}

      {/* Filter & Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="relative flex-1 w-full max-w-sm">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filter members by name or email..."
            className="w-full bg-slate-900/60 border border-slate-800 rounded-xl pl-9 pr-4 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />
        </div>

        <div className="flex items-center space-x-2 text-xs">
          <span className="text-slate-400">Role:</span>
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            className="bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none"
          >
            <option value="all">All Roles</option>
            <option value="owner">Owner</option>
            <option value="maintainer">Maintainer</option>
            <option value="contributor">Contributor</option>
            <option value="viewer">Viewer</option>
          </select>
        </div>
      </div>

      {/* Members Table */}
      <div className="bg-slate-900/50 border border-slate-800/80 rounded-xl overflow-hidden shadow-lg">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-slate-950/60 border-b border-slate-800 text-slate-400 font-semibold">
            <tr>
              <th className="p-3.5">User</th>
              <th className="p-3.5">Role</th>
              <th className="p-3.5">Joined</th>
              {can("manage_members") && !isArchived && <th className="p-3.5 text-right">Actions</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {filteredMembers.length === 0 ? (
              <tr>
                <td colSpan={4} className="p-6 text-center text-slate-500">
                  No members match your filter.
                </td>
              </tr>
            ) : (
              filteredMembers.map((m) => {
                const displayName = m.display_name || m.email || `Hub member (${(m.user_id || m.id || "").slice(0, 8)})`;
                const avatarInitial = (m.display_name || m.email || "?").charAt(0).toUpperCase();
                return (
                <tr key={m.id} className="hover:bg-slate-800/30 transition-colors">
                  <td className="p-3.5">
                    <div className="flex items-center space-x-3">
                      <div className="w-8 h-8 rounded-full bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center font-bold text-indigo-200">
                        {avatarInitial}
                      </div>
                      <div>
                        <p className="font-semibold text-slate-100">{displayName}</p>
                        {m.email ? (
                          <p className="text-[11px] text-slate-500 font-mono">{m.email}</p>
                        ) : (
                          <p className="text-[11px] text-slate-500 font-mono">{m.user_id || m.id}</p>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="p-3.5">
                    {can("manage_members") && !isArchived && m.hub_role !== "owner" ? (
                      <select
                        value={m.hub_role}
                        onChange={(e) => handleRoleChange(m.user_id, e.target.value as HubRole)}
                        className="bg-slate-950 border border-slate-800 rounded px-2 py-1 text-xs text-slate-200 focus:outline-none"
                      >
                        <option value="maintainer">Maintainer</option>
                        <option value="contributor">Contributor</option>
                        <option value="viewer">Viewer</option>
                      </select>
                    ) : (
                      <span className="capitalize font-semibold text-indigo-400 bg-indigo-950/40 px-2.5 py-1 rounded border border-indigo-800/40">
                        {m.hub_role}
                      </span>
                    )}
                  </td>
                  <td className="p-3.5 font-mono text-slate-400">
                    {new Date(m.created_at).toLocaleDateString()}
                  </td>
                  {can("manage_members") && !isArchived && (
                    <td className="p-3.5 text-right">
                      {m.hub_role === "owner" && ownerCount <= 1 ? (
                        <span
                          className="text-[11px] text-slate-500 italic"
                          title="A hub must always have at least one owner"
                        >
                          Last Owner
                        </span>
                      ) : (
                        <button
                          onClick={() => handleRemoveMember(m.user_id)}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-950/40 transition-colors"
                          title="Revoke Hub Membership"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </td>
                  )}
                </tr>
                );
              })}
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
