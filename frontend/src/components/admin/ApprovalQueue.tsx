import { useEffect, useState } from "react";
import { Check, X, Loader2, User as UserIcon, AlertCircle } from "lucide-react";
import { api } from "../../services/api";
import { useStore } from "../../store/useStore";

export function ApprovalQueue() {
  const [pendingUsers, setPendingUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<Record<string, "approving" | "rejecting" | null>>({});

  const addNotification = useStore((state) => state.addNotification);

  const fetchPending = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.admin.users.pending();
      setPendingUsers(res.items || []);
    } catch (err: any) {
      setError(err?.message || "Failed to load pending users.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPending();
  }, []);

  const handleApprove = async (userId: string, email: string) => {
    setActionError(null);
    setActionLoading((prev) => ({ ...prev, [userId]: "approving" }));
    try {
      await api.admin.users.approve(userId, {});
      setPendingUsers((prev) => prev.filter((u) => u.id !== userId));
      addNotification({
        type: "success",
        title: "User Approved",
        message: `Successfully approved user registration for ${email}`,
      });
      fetchPending();
    } catch (err: any) {
      const msg = err?.message || "Failed to approve user request.";
      setActionError(msg);
      addNotification({
        type: "error",
        title: "Approval Failed",
        message: msg,
      });
    } finally {
      setActionLoading((prev) => ({ ...prev, [userId]: null }));
    }
  };

  const handleReject = async (userId: string, email: string) => {
    if (!window.confirm(`Are you sure you want to reject registration request for ${email}?`)) return;
    setActionError(null);
    setActionLoading((prev) => ({ ...prev, [userId]: "rejecting" }));
    try {
      await api.admin.users.reject(userId, { reason: "Admin rejected registration." });
      setPendingUsers((prev) => prev.filter((u) => u.id !== userId));
      addNotification({
        type: "info",
        title: "User Rejected",
        message: `Rejected user registration for ${email}`,
      });
      fetchPending();
    } catch (err: any) {
      const msg = err?.message || "Failed to reject user request.";
      setActionError(msg);
      addNotification({
        type: "error",
        title: "Rejection Failed",
        message: msg,
      });
    } finally {
      setActionLoading((prev) => ({ ...prev, [userId]: null }));
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
      <div className="p-8 text-center text-xs text-red-400 bg-slate-900/50 border border-slate-800 rounded-xl space-y-3">
        <p>{error}</p>
        <button
          onClick={fetchPending}
          className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  if (pendingUsers.length === 0) {
    return (
      <div className="p-8 text-center text-xs text-slate-500 bg-slate-900/50 border border-slate-800 rounded-xl">
        Approval queue clean. No pending user registration requests.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {actionError && (
        <div className="p-3 bg-red-950/40 border border-red-800/60 rounded-xl flex items-center gap-2 text-xs text-red-300">
          <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
          <span>{actionError}</span>
        </div>
      )}

      {pendingUsers.map((user) => {
        const isApproving = actionLoading[user.id] === "approving";
        const isRejecting = actionLoading[user.id] === "rejecting";
        const isBusy = isApproving || isRejecting;

        return (
          <div key={user.id} className="bg-slate-900/40 border border-slate-800 rounded-xl p-4 flex items-center justify-between gap-4">
            <div className="flex items-center space-x-3 min-w-0">
              <div className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center overflow-hidden shrink-0">
                {user.avatar_url ? (
                  <img src={user.avatar_url} alt="avatar" className="w-full h-full object-cover" />
                ) : (
                  <UserIcon className="w-5 h-5 text-slate-400" />
                )}
              </div>
              <div className="truncate">
                <p className="text-sm font-semibold text-slate-200 truncate">{user.display_name || user.email}</p>
                <p className="text-xs text-slate-500 truncate">{user.email}</p>
              </div>
            </div>

            <div className="flex items-center space-x-2 shrink-0">
              <button
                onClick={() => handleReject(user.id, user.email)}
                disabled={isBusy}
                className="p-2 bg-red-500/10 hover:bg-red-500/20 disabled:opacity-50 text-red-400 rounded-lg transition-colors flex items-center space-x-1"
                title="Reject"
              >
                {isRejecting ? <Loader2 className="w-4 h-4 animate-spin" /> : <X className="w-4 h-4" />}
                <span className="text-xs font-semibold">Reject</span>
              </button>

              <button
                onClick={() => handleApprove(user.id, user.email)}
                disabled={isBusy}
                className="px-3 py-2 bg-emerald-600/20 hover:bg-emerald-600/30 disabled:opacity-50 border border-emerald-500/40 text-emerald-400 text-xs font-semibold rounded-lg transition-colors flex items-center space-x-1.5"
              >
                {isApproving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                <span>Approve</span>
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
