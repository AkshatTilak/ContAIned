import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Server,
  Layers,
  Activity,
  Users,
  ShieldCheck,
  Settings,
  Wifi,
  WifiOff,
  ChevronLeft,
  ChevronRight,
  Plus,
  Upload,
} from "lucide-react";
import { useStore } from "../store/useStore";

interface SidebarProps {
  onOpenCommandPalette?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = () => {
  const navigate = useNavigate();
  const isConnected = useStore((state) => state.isConnected);
  const telemetryStatus = useStore((state) => state.telemetry.status);
  const sidebarCollapsed = useStore((state) => state.sidebarCollapsed);
  const setSidebarCollapsed = useStore((state) => state.setSidebarCollapsed);

  const navItems = [
    { path: "/system", label: "System Metrics", icon: Activity, shortcut: "⌘1" },
    { path: "/ingestion", label: "Ingestion Pipeline", icon: Layers, shortcut: "⌘2" },
    { path: "/workflow", label: "Workflow Builder", icon: Server, shortcut: "⌘3" },
    { path: "/agents", label: "Agent Hub", icon: Users, shortcut: "⌘4" },
    { path: "/evalops", label: "EvalOps Benchmark", icon: ShieldCheck, shortcut: "⌘5" },
  ] as const;

  return (
    <aside
      className={`bg-[var(--bg-input)] border-r border-[var(--border-default)] flex flex-col justify-between p-4 select-none shrink-0 transition-all duration-300 ${
        sidebarCollapsed ? "w-20" : "w-[280px]"
      }`}
    >
      <div className="flex-1 flex flex-col min-h-0 overflow-y-auto custom-scrollbar pr-0.5 space-y-6">
        {/* Brand Header & Toggle */}
        <div className="flex items-center justify-between px-1 py-1 mb-2 border-b border-[var(--border-subtle)] pb-4 shrink-0">
          <NavLink
            to="/system"
            className="flex items-center gap-3 min-w-0 group"
            title="ContAIned Platform V4"
          >
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-500 to-indigo-600 flex items-center justify-center shadow-xl shadow-emerald-500/25 group-hover:scale-105 transition-transform shrink-0">
              <Server className="w-5 h-5 text-white" />
            </div>
            {!sidebarCollapsed && (
              <div className="flex flex-col justify-center min-w-0">
                <h1 className="font-bold text-white tracking-wider text-lg leading-none font-display whitespace-nowrap">
                  Cont<span className="text-emerald-400">AI</span>ned
                </h1>
                <div className="mt-1.5">
                  <span className="text-[10px] uppercase tracking-widest font-bold text-emerald-400 bg-emerald-500/15 px-2 py-0.5 rounded-full border border-emerald-500/30 inline-block whitespace-nowrap">
                    Platform V4.1
                  </span>
                </div>
              </div>
            )}
          </NavLink>

          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="p-2 rounded-xl text-zinc-400 hover:text-zinc-200 hover:bg-[var(--bg-elevated)] border border-transparent hover:border-[var(--border-subtle)] transition-colors shrink-0 ml-1"
            title={sidebarCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
          >
            {sidebarCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </div>

        {/* Navigation List */}
        <nav className="space-y-2 relative shrink-0">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                title={sidebarCollapsed ? `${item.label} (${item.shortcut})` : undefined}
                className={({ isActive }) =>
                  `relative w-full flex items-center gap-3.5 px-4 py-3 rounded-xl text-sm font-semibold transition-all ${
                    isActive
                      ? "text-emerald-400 font-bold"
                      : "text-zinc-400 hover:text-zinc-200 hover:bg-[var(--bg-elevated)]"
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive && (
                      <motion.div
                        layoutId="sidebar-active-indicator"
                        className="absolute inset-0 bg-emerald-500/10 border border-emerald-500/30 rounded-xl shadow-inner"
                        transition={{ type: "spring", stiffness: 350, damping: 30 }}
                      />
                    )}
                    <Icon className={`w-4 h-4 shrink-0 relative z-10 ${isActive ? "text-emerald-400" : "text-zinc-400"}`} />
                    {!sidebarCollapsed && (
                      <div className="flex items-center justify-between w-full relative z-10 overflow-hidden">
                        <span className="whitespace-nowrap">{item.label}</span>
                        <span className="text-[10px] font-mono text-zinc-500 px-2 py-0.5 bg-[var(--bg-surface)] rounded-md border border-[var(--border-subtle)] ml-2 shrink-0">
                          {item.shortcut}
                        </span>
                      </div>
                    )}
                  </>
                )}
              </NavLink>
            );
          })}
        </nav>

        {/* Quick Actions (Expanded state only) */}
        {!sidebarCollapsed && (
          <div className="mt-6 pt-4 border-t border-[var(--border-subtle)] shrink-0">
            <div className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider px-3 mb-2">
              Quick Actions
            </div>
            <div className="space-y-1">
              <button
                onClick={() => navigate("/ingestion")}
                className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium text-zinc-400 hover:text-emerald-300 hover:bg-[var(--bg-elevated)] transition-colors group"
              >
                <Upload className="w-3.5 h-3.5 text-zinc-500 group-hover:text-emerald-400 transition-colors" />
                <span>Upload Document</span>
              </button>
              <button
                onClick={() => navigate("/agents")}
                className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium text-zinc-400 hover:text-indigo-300 hover:bg-[var(--bg-elevated)] transition-colors group"
              >
                <Plus className="w-3.5 h-3.5 text-zinc-500 group-hover:text-indigo-400 transition-colors" />
                <span>Create Agent</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Connection Status & Settings Link */}
      <div className="space-y-2 pt-3 border-t border-[var(--border-default)]">
        <div
          className={`flex items-center ${
            sidebarCollapsed ? "justify-center p-2" : "justify-between px-3 py-2"
          } rounded-lg bg-[var(--bg-surface-alt)] text-xs border border-[var(--border-subtle)]`}
          title={sidebarCollapsed ? `Status: ${isConnected ? telemetryStatus : "Offline"}` : undefined}
        >
          <div className="flex items-center gap-2">
            {isConnected ? (
              <Wifi className="w-3.5 h-3.5 text-emerald-400 animate-pulse shrink-0" />
            ) : (
              <WifiOff className="w-3.5 h-3.5 text-amber-400 shrink-0" />
            )}
            {!sidebarCollapsed && (
              <span className="text-zinc-300 capitalize font-medium truncate">
                {isConnected ? telemetryStatus : "Offline"}
              </span>
            )}
          </div>
          {!sidebarCollapsed && (
            <span
              className={`w-2 h-2 rounded-full shrink-0 ${
                isConnected ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]" : "bg-amber-400"
              }`}
            />
          )}
        </div>

        <NavLink
          to="/settings"
          title={sidebarCollapsed ? "Gateway Settings" : undefined}
          className={({ isActive }) =>
            `w-full flex items-center gap-3 ${
              sidebarCollapsed ? "justify-center px-0 py-2.5" : "px-3 py-2.5"
            } rounded-lg text-xs font-medium transition-all ${
              isActive
                ? "bg-[var(--emerald-soft)] text-emerald-400 border border-emerald-500/30"
                : "text-zinc-400 hover:text-zinc-200 hover:bg-[var(--bg-elevated)] border border-transparent"
            }`
          }
        >
          <Settings className="w-4 h-4 shrink-0" />
          {!sidebarCollapsed && <span>Gateway Settings</span>}
        </NavLink>
      </div>
    </aside>
  );
};

