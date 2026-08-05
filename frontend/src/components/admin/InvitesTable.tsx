import { useEffect, useState } from "react";
import { Loader2, Mail, RefreshCw, X, CheckCircle, Clock } from "lucide-react";
import { api } from "../../services/api";

export function InvitesTable() {
  const [invites, setInvites] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchInvites = async () => {
    setLoading(true);
    try {
      const res = await api.admin.invites.list();
      setInvites(res.items || []);
    } catch (err: any) {
      setError(err?.message || "Failed to load invitations.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInvites();
  }, []);

  const handleResend = async (inviteId: string) => {
    try {
      await api.admin.invites.resend(inviteId);
      fetchInvites();
    } catch (err) {
      console.error("Failed to resend invite:", err);
    }
  };

  const handleRevoke = async (inviteId: string) => {
    if (!window.confirm("Are you sure you want to revoke this invitation?")) return;
    try {
      await api.admin.invites.revoke(inviteId);
      fetchInvites();
    } catch (err) {
      console.error("Failed to revoke invite:", err);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center p-8">
        <Loader2 className="w-5 h-5 animate-spin text-slate-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-center text-xs text-red-400 bg-slate-900/50 border border-slate-800 rounded-xl">
        {error}
      </div>
    );
  }

  if (invites.length === 0) {
    return (
      <div className="p-8 text-center text-xs text-slate-500 bg-slate-900/50 border border-slate-800 rounded-xl">
        No platform invitations found.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs">
        <thead className="text-slate-400 bg-slate-900/50 border-b border-slate-800">
          <tr>
            <th className="px-4 py-3 font-semibold">Email</th>
            <th className="px-4 py-3 font-semibold">Role</th>
            <th className="px-4 py-3 font-semibold">Status</th>
            <th className="px-4 py-3 font-semibold">Invited By</th>
            <th className="px-4 py-3 font-semibold text-right">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/50">
          {invites.map((invite) => (
            <tr key={invite.id} className="hover:bg-slate-800/20 transition-colors">
              <td className="px-4 py-3 font-medium text-slate-300 flex items-center space-x-2">
                <Mail className="w-4 h-4 text-slate-500" />
                <span>{invite.email}</span>
              </td>
              <td className="px-4 py-3 text-slate-400 capitalize">{invite.platform_role}</td>
              <td className="px-4 py-3">
                {invite.status === "pending" && (
                  <span className="inline-flex items-center space-x-1 text-amber-400 bg-amber-400/10 px-2 py-0.5 rounded-md">
                    <Clock className="w-3 h-3" />
                    <span>Pending</span>
                  </span>
                )}
                {invite.status === "accepted" && (
                  <span className="inline-flex items-center space-x-1 text-emerald-400 bg-emerald-400/10 px-2 py-0.5 rounded-md">
                    <CheckCircle className="w-3 h-3" />
                    <span>Accepted</span>
                  </span>
                )}
                {invite.status === "revoked" && (
                  <span className="inline-flex items-center space-x-1 text-slate-400 bg-slate-400/10 px-2 py-0.5 rounded-md">
                    <X className="w-3 h-3" />
                    <span>Revoked</span>
                  </span>
                )}
                {invite.status === "expired" && (
                  <span className="inline-flex items-center space-x-1 text-red-400 bg-red-400/10 px-2 py-0.5 rounded-md">
                    <Clock className="w-3 h-3" />
                    <span>Expired</span>
                  </span>
                )}
              </td>
              <td className="px-4 py-3 text-slate-400">{invite.invited_by}</td>
              <td className="px-4 py-3 text-right">
                {invite.status === "pending" || invite.status === "expired" ? (
                  <div className="flex items-center justify-end space-x-2">
                    <button
                      onClick={() => handleResend(invite.id)}
                      className="p-1.5 text-slate-400 hover:text-indigo-400 hover:bg-indigo-500/10 rounded-lg transition-colors"
                      title="Resend Invite"
                    >
                      <RefreshCw className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleRevoke(invite.id)}
                      className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                      title="Revoke Invite"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
