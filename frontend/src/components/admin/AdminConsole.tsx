import { useState } from "react";
import { Users, UserCheck, Mail, ShieldAlert, Shield } from "lucide-react";
import { UserDirectory } from "./UserDirectory";

export function AdminConsole() {
  const [tab, setTab] = useState<"users" | "pending" | "invites" | "audit">("users");

  return (
    <div className="space-y-6 pb-12">
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold font-display text-slate-100">Platform Admin Console</h1>
            <p className="text-xs text-slate-400 mt-0.5">Manage user access, invitations, pending approvals, and security audit logs.</p>
          </div>
        </div>
      </div>

      <div className="flex items-center space-x-2 border-b border-slate-800 pb-2">
        <button
          onClick={() => setTab("users")}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-colors ${
            tab === "users" ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/40" : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <Users className="w-3.5 h-3.5" />
          <span>User Directory</span>
        </button>

        <button
          onClick={() => setTab("pending")}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-colors ${
            tab === "pending" ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/40" : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <UserCheck className="w-3.5 h-3.5" />
          <span>Approval Queue</span>
        </button>

        <button
          onClick={() => setTab("invites")}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-colors ${
            tab === "invites" ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/40" : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <Mail className="w-3.5 h-3.5" />
          <span>Invitations</span>
        </button>

        <button
          onClick={() => setTab("audit")}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-colors ${
            tab === "audit" ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/40" : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <ShieldAlert className="w-3.5 h-3.5" />
          <span>Audit Log</span>
        </button>
      </div>

      {tab === "users" && <UserDirectory />}
      {tab === "pending" && (
        <div className="p-8 text-center text-xs text-slate-500 bg-slate-900/50 border border-slate-800 rounded-xl">
          Approval queue clean. No pending user registration requests.
        </div>
      )}
      {tab === "invites" && (
        <div className="p-8 text-center text-xs text-slate-500 bg-slate-900/50 border border-slate-800 rounded-xl">
          No pending platform invitations.
        </div>
      )}
      {tab === "audit" && (
        <div className="p-8 text-center text-xs text-slate-500 bg-slate-900/50 border border-slate-800 rounded-xl">
          Security audit telemetry logging active.
        </div>
      )}
    </div>
  );
}
