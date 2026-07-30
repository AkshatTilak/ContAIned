import React, { useState, useEffect } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Server,
  Layers,
  Activity,
  Users,
  ShieldCheck,
  Bot,
  Plug,
  Settings,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Plus,
  Database,
  GitFork,
  CheckSquare,
  Building2,
  Lock,
  UserCheck,
  FileSpreadsheet,
} from "lucide-react";
import { useStore } from "../store/useStore";
import { routes, type HubType } from "../routes";
import type { Hub } from "../types/api";

interface SidebarProps {
  onOpenCommandPalette?: () => void;
  onOpenHubSwitcher?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ onOpenHubSwitcher }) => {
  const navigate = useNavigate();
  const sidebarCollapsed = useStore((state) => state.sidebarCollapsed);
  const setSidebarCollapsed = useStore((state) => state.setSidebarCollapsed);
  const hubsByType = useStore((state) => state.hubsByType);
  const hubsById = useStore((state) => state.hubsById);
  const activeHubId = useStore((state) => state.activeHubId);
  const isPlatformAdmin = useStore(
    (s) => ((s as unknown) as Record<string, unknown>).isPlatformAdmin as boolean | undefined
  ) || false;

  const [expandedTypes, setExpandedTypes] = useState<Record<HubType, boolean>>({
    ingestion: true,
    agent: true,
    workflow: true,
    eval: true,
  });

  const [pendingApprovalsCount, setPendingApprovalsCount] = useState<number>(0);

  const activeHub = activeHubId ? hubsById[activeHubId] : null;

  // Auto expand active hub's type group
  useEffect(() => {
    if (activeHub) {
      setExpandedTypes((prev) => ({ ...prev, [activeHub.hub_type]: true }));
    }
  }, [activeHub]);

  const toggleTypeGroup = (type: HubType) => {
    setExpandedTypes((prev) => ({ ...prev, [type]: !prev[type] }));
  };

  const hubTypeMeta: { type: HubType; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
    { type: "ingestion", label: "Ingestion Hubs", icon: Layers },
    { type: "agent", label: "Agent Hubs", icon: Bot },
    { type: "workflow", label: "Workflow Hubs", icon: GitFork },
    { type: "eval", label: "Eval Hubs", icon: CheckSquare },
  ];

  return (
    <aside
      className={`bg-[#0c0d12] border-r border-slate-800 flex flex-col justify-between p-4 select-none shrink-0 transition-all duration-300 ${
        sidebarCollapsed ? "w-20" : "w-[280px]"
      }`}
    >
      <div className="flex-1 flex flex-col min-h-0 overflow-y-auto custom-scrollbar pr-0.5 space-y-6">
        {/* Brand Header & Toggle */}
        <div className="flex items-center justify-between px-1 py-1 border-b border-slate-800/80 pb-4 shrink-0">
          <NavLink
            to={routes.hubs.directory()}
            className="flex items-center gap-3 min-w-0 group"
            title="ContAIned Platform V6"
          >
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/20 group-hover:scale-105 transition-transform shrink-0">
              <Building2 className="w-5 h-5 text-white" />
            </div>
            {!sidebarCollapsed && (
              <div className="flex flex-col justify-center min-w-0">
                <h1 className="font-bold text-white tracking-wider text-lg leading-none font-display whitespace-nowrap">
                  Cont<span className="text-indigo-400">AI</span>ned
                </h1>
                <div className="mt-1.5">
                  <span className="text-[10px] uppercase tracking-widest font-bold text-indigo-400 bg-indigo-500/15 px-2 py-0.5 rounded-full border border-indigo-500/30 inline-block whitespace-nowrap">
                    Hub Platform V6
                  </span>
                </div>
              </div>
            )}
          </NavLink>

          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="p-2 rounded-xl text-slate-400 hover:text-slate-200 hover:bg-slate-800 border border-transparent hover:border-slate-700 transition-colors shrink-0 ml-1"
            title={sidebarCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
          >
            {sidebarCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </div>

        {/* Hub Switcher Quick CTA */}
        {onOpenHubSwitcher && !sidebarCollapsed && (
          <button
            onClick={onOpenHubSwitcher}
            className="w-full flex items-center justify-between px-3 py-2 bg-slate-900/60 hover:bg-slate-800/80 text-slate-300 border border-slate-800 rounded-lg text-xs font-medium transition-colors"
          >
            <span className="flex items-center space-x-2 truncate">
              <span
                className="w-2.5 h-2.5 rounded-full shrink-0"
                style={{ backgroundColor: activeHub?.accent || "#6366f1" }}
              />
              <span className="truncate">{activeHub ? activeHub.name : "Switch Hub…"}</span>
            </span>
            <kbd className="px-1.5 py-0.5 bg-slate-800 text-[10px] font-mono text-slate-400 rounded">⌘K</kbd>
          </button>
        )}

        {/* --- HUBS GROUP --- */}
        <div className="space-y-3">
          {!sidebarCollapsed && (
            <div className="flex items-center justify-between px-2 text-xs font-bold uppercase tracking-wider text-slate-500">
              <span>Hub Workspaces</span>
              <button
                onClick={() => navigate(routes.hubs.create())}
                className="hover:text-indigo-400 transition-colors"
                title="Create New Hub"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>
          )}

          {hubTypeMeta.map(({ type, label, icon: TypeIcon }) => {
            const hubs = hubsByType[type] || [];
            const isExpanded = expandedTypes[type];

            return (
              <div key={type} className="space-y-1">
                {!sidebarCollapsed ? (
                  <>
                    <button
                      onClick={() => toggleTypeGroup(type)}
                      className="w-full flex items-center justify-between px-2 py-1.5 text-xs font-semibold text-slate-400 hover:text-slate-200 transition-colors"
                    >
                      <span className="flex items-center space-x-2">
                        <TypeIcon className="w-3.5 h-3.5 text-indigo-400" />
                        <span>{label}</span>
                      </span>
                      <ChevronDown
                        className={`w-3.5 h-3.5 transition-transform ${isExpanded ? "" : "-rotate-90"}`}
                      />
                    </button>

                    {isExpanded && (
                      <div className="pl-4 space-y-1">
                        {hubs.length === 0 ? (
                          <span className="block px-3 py-1 text-xs italic text-slate-600">
                            No {type} hubs
                          </span>
                        ) : (
                          hubs.map((hub) => {
                            const isSelected = activeHubId === hub.id;
                            return (
                              <NavLink
                                key={hub.id}
                                to={routes.hubs.shell(type, hub.id)}
                                className={`flex items-center space-x-2.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                                  isSelected
                                    ? "bg-indigo-600/20 text-indigo-300 font-semibold border border-indigo-500/30"
                                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/40"
                                }`}
                              >
                                <span
                                  className="w-2 h-2 rounded-full shrink-0"
                                  style={{ backgroundColor: hub.accent || "#6366f1" }}
                                />
                                <span className="truncate">{hub.name}</span>
                              </NavLink>
                            );
                          })
                        )}
                      </div>
                    )}
                  </>
                ) : (
                  <NavLink
                    to={routes.hubs.directory()}
                    title={label}
                    className="flex justify-center p-2.5 rounded-xl text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
                  >
                    <TypeIcon className="w-5 h-5 text-indigo-400" />
                  </NavLink>
                )}
              </div>
            );
          })}
        </div>

        {/* --- PLATFORM GROUP --- */}
        <div className="space-y-1 border-t border-slate-800/80 pt-4">
          {!sidebarCollapsed && (
            <div className="px-2 text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
              Platform
            </div>
          )}

          {[
            { to: routes.platform.system(), label: "System Metrics", icon: Activity },
            { to: routes.platform.playground(), label: "Model Playground", icon: Bot },
            { to: routes.platform.mcp(), label: "MCP Registry", icon: Plug },
            { to: routes.platform.infrastructure(), label: "Infrastructure", icon: Database },
            { to: routes.platform.settings(), label: "Settings", icon: Settings },
          ].map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                title={sidebarCollapsed ? item.label : undefined}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                    isActive
                      ? "bg-indigo-600/20 text-indigo-400 font-semibold"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/40"
                  }`
                }
              >
                <Icon className="w-4 h-4 shrink-0" />
                {!sidebarCollapsed && <span>{item.label}</span>}
              </NavLink>
            );
          })}
        </div>

        {/* --- ADMIN GROUP (Platform Admins Only) --- */}
        {isPlatformAdmin && (
          <div className="space-y-1 border-t border-slate-800/80 pt-4">
            {!sidebarCollapsed && (
              <div className="flex items-center justify-between px-2 text-xs font-bold uppercase tracking-wider text-amber-500 mb-2">
                <span>Admin Console</span>
                {pendingApprovalsCount > 0 && (
                  <span className="px-1.5 py-0.5 text-[10px] font-bold rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30">
                    {pendingApprovalsCount}
                  </span>
                )}
              </div>
            )}

            {[
              { to: routes.admin.users(), label: "User Directory", icon: Users },
              { to: routes.admin.invites(), label: "Invites", icon: Lock },
              { to: routes.admin.approvals(), label: "Approvals", icon: UserCheck },
              { to: routes.admin.audit(), label: "Audit Log", icon: FileSpreadsheet },
            ].map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  title={sidebarCollapsed ? item.label : undefined}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                      isActive
                        ? "bg-amber-500/20 text-amber-300 font-semibold"
                        : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/40"
                    }`
                  }
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  {!sidebarCollapsed && <span>{item.label}</span>}
                </NavLink>
              );
            })}
          </div>
        )}
      </div>
    </aside>
  );
};
