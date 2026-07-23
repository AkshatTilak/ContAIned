import React, { useEffect, useState } from "react";
import { api } from "../../services/api";
import { useStore } from "../../store/useStore";
import { Users, Shield, UserX, CheckCircle, RefreshCw } from "lucide-react";

export interface UserItem {
  id: string;
  email: string;
  display_name?: string;
  avatar_url?: string;
  provider: string;
  role: string;
  is_active: boolean;
  created_at: string;
  last_login?: string;
}

export const UserManagement: React.FC = () => {
  const [users, setUsers] = useState<UserItem[]>([]);
  const [loading, setLoading] = useState(true);
  const addNotification = useStore((state) => state.addNotification);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const data = await api.listUsers();
      setUsers(data);
    } catch (e: any) {
      addNotification({
        type: "error",
        title: "Failed to fetch users",
        message: e?.message || "Could not retrieve user list",
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleRoleChange = async (userId: string, newRole: string) => {
    try {
      await api.updateUserRole(userId, newRole);
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, role: newRole } : u))
      );
      addNotification({
        type: "success",
        title: "Role Updated",
        message: `User role changed to ${newRole}`,
      });
    } catch (e: any) {
      addNotification({
        type: "error",
        title: "Failed to update role",
        message: e?.message || "Role change failed",
      });
    }
  };

  const handleToggleDeactivate = async (userId: string, currentActive: boolean) => {
    if (currentActive) {
      try {
        await api.deactivateUser(userId);
        setUsers((prev) =>
          prev.map((u) => (u.id === userId ? { ...u, is_active: false } : u))
        );
        addNotification({
          type: "info",
          title: "User Deactivated",
          message: "User account deactivated",
        });
      } catch (e: any) {
        addNotification({
          type: "error",
          title: "Deactivation failed",
          message: e?.message,
        });
      }
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold text-slate-100 flex items-center gap-2">
            <Users className="w-5 h-5 text-purple-400" />
            User Management & RBAC
          </h3>
          <p className="text-xs text-slate-400 mt-1">
            Manage active user identities, assign RBAC roles, and control access permissions.
          </p>
        </div>
        <button
          onClick={fetchUsers}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs text-slate-300 transition-colors cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl overflow-hidden shadow-inner">
        {loading ? (
          <div className="p-8 text-center text-slate-400 text-sm">
            Loading user registry...
          </div>
        ) : users.length === 0 ? (
          <div className="p-8 text-center text-slate-500 text-sm">
            No registered users found. (Local Admin mode active)
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider">
                <tr>
                  <th className="py-3 px-4">User</th>
                  <th className="py-3 px-4">Provider</th>
                  <th className="py-3 px-4">Role</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Last Login</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-3 px-4 flex items-center gap-3">
                      {u.avatar_url ? (
                        <img
                          src={u.avatar_url}
                          alt={u.display_name || u.email}
                          className="w-8 h-8 rounded-full object-cover border border-slate-700"
                        />
                      ) : (
                        <div className="w-8 h-8 rounded-full bg-purple-950/60 border border-purple-800/60 flex items-center justify-center font-bold text-purple-300">
                          {(u.display_name || u.email).charAt(0).toUpperCase()}
                        </div>
                      )}
                      <div>
                        <p className="font-semibold text-slate-200">
                          {u.display_name || "Anonymous User"}
                        </p>
                        <p className="text-[10px] text-slate-400">{u.email}</p>
                      </div>
                    </td>
                    <td className="py-3 px-4 capitalize font-mono text-slate-400">
                      {u.provider}
                    </td>
                    <td className="py-3 px-4">
                      <select
                        value={u.role}
                        onChange={(e) => handleRoleChange(u.id, e.target.value)}
                        className="bg-slate-950 border border-slate-800 text-slate-200 rounded px-2 py-1 text-xs font-semibold focus:outline-none focus:border-purple-500 cursor-pointer"
                      >
                        <option value="admin">Admin</option>
                        <option value="editor">Editor</option>
                        <option value="viewer">Viewer</option>
                      </select>
                    </td>
                    <td className="py-3 px-4">
                      {u.is_active ? (
                        <span className="inline-flex items-center gap-1 text-emerald-400 bg-emerald-950/40 border border-emerald-800/50 px-2 py-0.5 rounded text-[10px] font-medium">
                          <CheckCircle className="w-3 h-3" /> Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-red-400 bg-red-950/40 border border-red-800/50 px-2 py-0.5 rounded text-[10px] font-medium">
                          <UserX className="w-3 h-3" /> Deactivated
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-slate-400">
                      {u.last_login
                        ? new Date(u.last_login).toLocaleString()
                        : "Never"}
                    </td>
                    <td className="py-3 px-4 text-right">
                      {u.is_active && (
                        <button
                          onClick={() => handleToggleDeactivate(u.id, u.is_active)}
                          className="px-2.5 py-1 rounded bg-red-950/50 hover:bg-red-900/60 border border-red-800/60 text-red-300 text-[11px] font-medium transition-colors cursor-pointer"
                        >
                          Deactivate
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
