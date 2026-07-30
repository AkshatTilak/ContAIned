import { useState, useEffect } from "react";
import { Users, Search, Shield, Trash2, CheckCircle2, XCircle, AlertCircle, Loader2 } from "lucide-react";
import { api } from "../../services/api";

export function UserDirectory() {
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchUsers = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listUsers();
      setUsers(data || []);
    } catch (err: any) {
      setError(err?.message || "Failed to load user directory");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  if (loading) {
    return (
      <div className="p-8 text-center space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mx-auto" />
        <p className="text-sm text-slate-400">Loading user directory...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      <div>
        <h2 className="text-xl font-bold font-display text-slate-100 flex items-center space-x-2">
          <Users className="w-5 h-5 text-indigo-400" />
          <span>User Directory</span>
        </h2>
        <p className="text-xs text-slate-400 mt-1">
          Platform members, role assignments, and authentication status.
        </p>
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
              <th className="p-3.5">Joined</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {users.length === 0 ? (
              <tr>
                <td colSpan={4} className="p-6 text-center text-slate-500">
                  No users registered on this platform instance.
                </td>
              </tr>
            ) : (
              users.map((u) => (
                <tr key={u.id} className="hover:bg-slate-800/30 transition-colors">
                  <td className="p-3.5 font-semibold text-slate-100">{u.email}</td>
                  <td className="p-3.5">
                    <span className="px-2 py-0.5 rounded bg-indigo-950/60 text-indigo-400 border border-indigo-800/40 font-mono text-[10px]">
                      {u.is_platform_admin ? "Platform Admin" : "Member"}
                    </span>
                  </td>
                  <td className="p-3.5 font-mono text-emerald-400">Active</td>
                  <td className="p-3.5 font-mono text-slate-400">Recently</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
