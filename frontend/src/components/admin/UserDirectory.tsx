import { useState, useEffect } from "react";
import { Users, Search, Shield, Trash2, CheckCircle2, XCircle, AlertCircle, Loader2 } from "lucide-react";
import { api } from "../../services/api";

export function UserDirectory() {
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [includeDeleted, setIncludeDeleted] = useState(true);
  const [actionUserId, setActionUserId] = useState<string | null>(null);

  const fetchUsers = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listUsers({ include_deleted: includeDeleted });
      const items = res.items || res;
      setUsers(items || []);
    } catch (err: any) {
      setError(err?.message || "Failed to load user directory");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, [includeDeleted]);

  const handleDeleteUser = async (userId: string, hard: boolean) => {
    setActionUserId(userId);
    try {
      await api.deleteUser(userId, hard);
      await fetchUsers();
    } catch (err: any) {
      setError(err?.message || "Failed to delete user");
    } finally {
      setActionUserId(null);
    }
  };

  if (loading && users.length === 0) {
    return (
      <div className="p-8 text-center space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mx-auto" />
        <p className="text-sm text-slate-400">Loading user directory...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold font-display text-slate-100 flex items-center space-x-2">
            <Users className="w-5 h-5 text-indigo-400" />
            <span>User Directory</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Platform members, role assignments, and authentication status.
          </p>
        </div>
        <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
          <input
            type="checkbox"
            checked={includeDeleted}
            onChange={(e) => setIncludeDeleted(e.target.checked)}
            className="rounded bg-slate-950 border-slate-800 text-indigo-600 focus:ring-0"
          />
          <span>Include Soft Deleted Users</span>
        </label>
      </div>

      {error && (
        <div className="p-4 bg-red-950/40 border border-red-800/40 rounded-xl text-red-300 text-xs">
          {error}
        </div>
      )}

      <div className="bg-slate-900/50 border border-slate-800/80 rounded-xl overflow-hidden shadow-lg">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-slate-950/60 border-b border-slate-800 text-slate-400 font-semibold">
            <tr>
              <th className="p-3.5">User</th>
              <th className="p-3.5">Platform Role</th>
              <th className="p-3.5">Status</th>
              <th className="p-3.5">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {users.length === 0 ? (
              <tr>
                <td colSpan={4} className="p-6 text-center text-slate-500">
                  No users found in directory.
                </td>
              </tr>
            ) : (
              users.map((u) => (
                <tr key={u.id} className="hover:bg-slate-800/30 transition-colors">
                  <td className="p-3.5 font-semibold text-slate-100">{u.email}</td>
                  <td className="p-3.5">
                    <span className="px-2 py-0.5 rounded bg-indigo-950/60 text-indigo-400 border border-indigo-800/40 font-mono text-[10px]">
                      {u.platform_role || "member"}
                    </span>
                  </td>
                  <td className="p-3.5 font-mono">
                    {u.is_deleted ? (
                      <span className="px-2 py-0.5 rounded bg-red-950/80 text-red-400 border border-red-800/60 text-[10px]">
                        Soft Deleted
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-800/60 text-[10px]">
                        {u.status}
                      </span>
                    )}
                  </td>
                  <td className="p-3.5">
                    <div className="flex items-center gap-2">
                      {!u.is_deleted ? (
                        <button
                          type="button"
                          disabled={actionUserId === u.id}
                          onClick={() => handleDeleteUser(u.id, false)}
                          className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-[10px] font-medium text-slate-300 cursor-pointer"
                        >
                          Soft Delete
                        </button>
                      ) : (
                        <button
                          type="button"
                          disabled={actionUserId === u.id}
                          onClick={() => handleDeleteUser(u.id, true)}
                          className="px-2.5 py-1 rounded bg-red-950/80 hover:bg-red-900 border border-red-800/60 text-[10px] font-semibold text-red-300 cursor-pointer flex items-center gap-1"
                        >
                          <Trash2 className="w-3 h-3" />
                          <span>Hard Purge</span>
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
