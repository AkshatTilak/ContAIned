import React from "react";
import { NavLink } from "react-router-dom";
import {
  Server,
  Layers,
  Activity,
  Users,
  ShieldCheck,
  Settings,
  Wifi,
  WifiOff
} from "lucide-react";
import { useStore } from "../store/useStore";

interface SidebarProps {
  onOpenCommandPalette?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = () => {
  const isConnected = useStore((state) => state.isConnected);
  const telemetryStatus = useStore((state) => state.telemetry.status);

  const navItems = [
    { path: "/system", label: "System Metrics", icon: Activity },
    { path: "/ingestion", label: "Ingestion Pipeline", icon: Layers },
    { path: "/workflow", label: "Workflow Builder", icon: Server },
    { path: "/agents", label: "Agent Hub", icon: Users },
    { path: "/evalops", label: "EvalOps Benchmark", icon: ShieldCheck },
  ] as const;

  return (
    <aside className="w-64 bg-[var(--bg-input)] border-r border-[var(--border-default)] flex flex-col justify-between p-4 select-none shrink-0">
      <div>
        {/* Brand Header */}
        <NavLink to="/system" className="flex items-center gap-3 px-2 py-3 mb-6 group">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-emerald-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-emerald-500/20 group-hover:scale-105 transition-transform">
            <Server className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-white tracking-wide text-base leading-tight font-display">
              Cont<span className="text-emerald-400">AI</span>ned
            </h1>
            <span className="text-xs text-zinc-400">Platform V3</span>
          </div>
        </NavLink>

        {/* Navigation List */}
        <nav className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  `w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    isActive
                      ? "bg-[var(--emerald-soft)] text-emerald-400 border border-emerald-500/30 font-semibold"
                      : "text-zinc-400 hover:text-zinc-200 hover:bg-[var(--bg-elevated)] border border-transparent"
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon className={`w-4 h-4 ${isActive ? "text-emerald-400" : "text-zinc-400"}`} />
                    <span>{item.label}</span>
                  </>
                )}
              </NavLink>
            );
          })}
        </nav>
      </div>

      {/* Connection Status & Settings Link */}
      <div className="space-y-3 pt-4 border-t border-[var(--border-default)]">
        <div className="flex items-center justify-between px-3 py-2 rounded-lg bg-[var(--bg-surface-alt)] text-xs border border-[var(--border-subtle)]">
          <div className="flex items-center gap-2">
            {isConnected ? (
              <Wifi className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
            ) : (
              <WifiOff className="w-3.5 h-3.5 text-amber-400" />
            )}
            <span className="text-zinc-300 capitalize font-medium">
              {isConnected ? telemetryStatus : "Offline"}
            </span>
          </div>
          <span
            className={`w-2 h-2 rounded-full ${
              isConnected ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]" : "bg-amber-400"
            }`}
          />
        </div>

        <NavLink
          to="/settings"
          className={({ isActive }) =>
            `w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
              isActive
                ? "bg-[var(--emerald-soft)] text-emerald-400 border border-emerald-500/30"
                : "text-zinc-400 hover:text-zinc-200 hover:bg-[var(--bg-elevated)] border border-transparent"
            }`
          }
        >
          <Settings className="w-4 h-4" />
          <span>Gateway Settings</span>
        </NavLink>
      </div>
    </aside>
  );
};
