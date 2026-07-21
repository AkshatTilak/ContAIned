import React from "react";
import { Link } from "react-router-dom";
import { Search, Settings, Wifi, WifiOff } from "lucide-react";
import { Breadcrumbs } from "./Breadcrumbs";
import { useStore } from "../../store/useStore";

interface HeaderBarProps {
  onOpenCommandPalette: () => void;
}

export const HeaderBar: React.FC<HeaderBarProps> = ({ onOpenCommandPalette }) => {
  const isConnected = useStore((state) => state.isConnected);
  const telemetryStatus = useStore((state) => state.telemetry.status);

  // Detect Mac vs Windows/Linux for keyboard shortcut hint
  const isMac = typeof window !== "undefined" && navigator.platform.toUpperCase().indexOf("MAC") >= 0;

  return (
    <header className="h-14 bg-[var(--bg-main)]/80 border-b border-[var(--border-subtle)] backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-30 select-none">
      {/* Dynamic Breadcrumbs */}
      <Breadcrumbs />

      {/* Header Actions */}
      <div className="flex items-center gap-3">
        {/* Command Palette Trigger */}
        <button
          onClick={onOpenCommandPalette}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[var(--bg-input)] hover:bg-[var(--bg-elevated)] border border-[var(--border-default)] text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-all group shadow-sm"
          title="Open Command Palette"
        >
          <Search className="w-3.5 h-3.5 text-[var(--text-muted)] group-hover:text-emerald-400 transition-colors" />
          <span className="hidden sm:inline">Search or command...</span>
          <kbd className="px-1.5 py-0.5 rounded bg-[var(--bg-surface-alt)] border border-[var(--border-subtle)] text-[10px] text-[var(--text-secondary)] font-mono font-semibold ml-1">
            {isMac ? "⌘K" : "Ctrl+K"}
          </kbd>
        </button>

        {/* Telemetry Status Indicator */}
        <div
          className={`flex items-center gap-2 px-2.5 py-1 rounded-lg border text-xs font-medium transition-colors ${
            isConnected
              ? "bg-[var(--emerald-soft)] border-emerald-500/30 text-emerald-400"
              : "bg-amber-500/10 border-amber-500/30 text-amber-400"
          }`}
        >
          {isConnected ? (
            <Wifi className="w-3.5 h-3.5 animate-pulse" />
          ) : (
            <WifiOff className="w-3.5 h-3.5" />
          )}
          <span className="capitalize hidden md:inline">
            {isConnected ? telemetryStatus : "Offline"}
          </span>
          <span
            className={`w-2 h-2 rounded-full ${
              isConnected ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]" : "bg-amber-400"
            }`}
          />
        </div>

        {/* Settings Quick Access Link */}
        <Link
          to="/settings"
          className="p-2 rounded-lg bg-[var(--bg-input)] hover:bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-all"
          title="Gateway & Environment Settings"
        >
          <Settings className="w-4 h-4" />
        </Link>
      </div>
    </header>
  );
};
