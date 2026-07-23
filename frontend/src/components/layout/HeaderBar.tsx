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
    <header className="h-16 bg-[var(--bg-main)]/80 border-b border-[var(--border-subtle)] backdrop-blur-md px-8 flex items-center justify-between sticky top-0 z-30 select-none">
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

        {/* User Identity & Role Badge */}
        <UserBadge />

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

const UserBadge: React.FC = () => {
  const [isOpen, setIsOpen] = React.useState(false);
  const user = useStore((state) => state.user);
  const isAuthEnabled = useStore((state) => state.isAuthEnabled);
  const logout = useStore((state) => state.logout);

  if (!isAuthEnabled) {
    return (
      <div className="flex items-center gap-2 px-2.5 py-1 rounded-lg bg-purple-950/30 border border-purple-800/40 text-purple-300 text-xs font-medium">
        <span className="w-2 h-2 rounded-full bg-purple-400 shadow-[0_0_8px_rgba(192,132,252,0.6)]" />
        <span>Local Admin</span>
      </div>
    );
  }

  const role = user?.role || "viewer";
  const roleBadgeStyle =
    role === "admin"
      ? "bg-purple-950/60 border-purple-800/60 text-purple-300"
      : role === "editor"
      ? "bg-blue-950/60 border-blue-800/60 text-blue-300"
      : "bg-slate-800/60 border-slate-700/60 text-slate-400";

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex items-center gap-2 p-1.5 rounded-lg bg-[var(--bg-input)] hover:bg-[var(--bg-elevated)] border border-[var(--border-default)] transition-all cursor-pointer"
      >
        {user?.avatar_url ? (
          <img
            src={user.avatar_url}
            alt={user.display_name || "User Avatar"}
            className="w-6 h-6 rounded-full object-cover"
          />
        ) : (
          <div className="w-6 h-6 rounded-full bg-indigo-600/40 border border-indigo-500/50 flex items-center justify-center text-[10px] font-bold text-indigo-200">
            {(user?.display_name || user?.email || "U").charAt(0).toUpperCase()}
          </div>
        )}
        <span className="text-xs font-medium text-slate-200 max-w-[100px] truncate hidden lg:inline">
          {user?.display_name || user?.email}
        </span>
        <span
          className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-bold border ${roleBadgeStyle}`}
        >
          {role}
        </span>
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-48 bg-slate-900 border border-slate-800 rounded-xl shadow-xl p-2 z-50 flex flex-col gap-1 text-xs">
          <div className="px-3 py-2 border-b border-slate-800/80">
            <p className="font-semibold text-slate-200 truncate">
              {user?.display_name || "User"}
            </p>
            <p className="text-[10px] text-slate-400 truncate">{user?.email}</p>
          </div>
          <button
            onClick={() => {
              setIsOpen(false);
              logout();
            }}
            className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-red-950/40 text-red-400 hover:text-red-300 text-left transition-colors cursor-pointer"
          >
            Sign Out
          </button>
        </div>
      )}
    </div>
  );
};
