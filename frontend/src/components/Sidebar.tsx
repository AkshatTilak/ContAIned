import React from "react";
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
  activeTab: "system" | "syntraflow" | "guardroute" | "agent_hub" | "evalops";
  setActiveTab: (tab: "system" | "syntraflow" | "guardroute" | "agent_hub" | "evalops") => void;
  onOpenConfig: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  setActiveTab,
  onOpenConfig,
}) => {
  const isConnected = useStore((state) => state.isConnected);
  const telemetryStatus = useStore((state) => state.telemetry.status);

  const navItems = [
    { id: "system", label: "System Metrics", icon: Activity },
    { id: "syntraflow", label: "Ingestion Pipeline", icon: Layers },
    { id: "guardroute", label: "Workflow Builder", icon: Server },
    { id: "agent_hub", label: "Agent Hub", icon: Users },
    { id: "evalops", label: "EvalOps Benchmark", icon: ShieldCheck },
  ] as const;

  return (
    <aside className="w-64 bg-[#121316] border-r border-[#26282d] flex flex-col justify-between p-4 select-none">
      <div>
        {/* Brand Header */}
        <div className="flex items-center gap-3 px-2 py-3 mb-6">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-emerald-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-emerald-500/20">
            <Server className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-white tracking-wide text-base leading-tight">
              Cont<span className="text-emerald-400">AI</span>ned
            </h1>
            <span className="text-xs text-zinc-400">Platform V2</span>
          </div>
        </div>

        {/* Navigation List */}
        <nav className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  isActive
                    ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                    : "text-zinc-400 hover:text-zinc-200 hover:bg-[#1c1e24]"
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? "text-emerald-400" : "text-zinc-400"}`} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Connection Status & Settings */}
      <div className="space-y-3 pt-4 border-t border-[#26282d]">
        <div className="flex items-center justify-between px-3 py-2 rounded-lg bg-[#181a20] text-xs">
          <div className="flex items-center gap-2">
            {isConnected ? (
              <Wifi className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
            ) : (
              <WifiOff className="w-3.5 h-3.5 text-amber-400" />
            )}
            <span className="text-zinc-300 capitalize">
              {isConnected ? telemetryStatus : "Offline"}
            </span>
          </div>
          <span className={`w-2 h-2 rounded-full ${isConnected ? "bg-emerald-400" : "bg-amber-400"}`} />
        </div>

        <button
          onClick={onOpenConfig}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium text-zinc-400 hover:text-zinc-200 hover:bg-[#1c1e24] transition-colors"
        >
          <Settings className="w-4 h-4 text-zinc-400" />
          <span>Gateway Settings</span>
        </button>
      </div>
    </aside>
  );
};
