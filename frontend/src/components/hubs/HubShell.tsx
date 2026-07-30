/**
 * HubShell — persistent layout route wrapping every hub workspace.
 *
 * Provides:
 *  - Single hub metadata fetch & store integration
 *  - HubContext & HubProvider
 *  - Hub header (name, type badge, accent, slug, icon)
 *  - Archived amber banner with Unarchive CTA
 *  - Workspace & Shared Tabs navigation
 *  - Animated outlet for child sub-routes
 */

import { useEffect, useState, useMemo } from "react";
import {
  Outlet,
  useParams,
  useNavigate,
  useLocation,
  NavLink,
} from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import {
  FolderKanban,
  Bot,
  GitFork,
  CheckSquare,
  Users,
  Link2,
  Settings,
  LayoutDashboard,
  Database,
  FileText,
  Activity,
  Search,
  Play,
  BarChart3,
  Archive,
  AlertTriangle,
} from "lucide-react";

import { HubNotFound } from "./HubNotFound";
import { HubProvider, type HubContextValue, type HubAction } from "./HubContext";
import { WORKSPACE_TABS, SHARED_TABS, type HubTabConfig } from "./hubTabs";
import { evaluate } from "../../hooks/useHubPermissions";
import { routes, type HubType } from "../../routes";
import { api, HubApiError } from "../../services/api";
import { useStore } from "../../store/useStore";
import type { Hub, HubRole } from "../../types/api";

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  LayoutDashboard,
  FolderKanban,
  Database,
  FileText,
  Activity,
  Search,
  Bot,
  GitFork,
  CheckSquare,
  Play,
  BarChart3,
  Users,
  Link2,
  Settings,
};

function HubShellSkeleton() {
  return (
    <div className="hub-shell-skeleton p-6 lg:p-10 space-y-6" aria-busy="true" aria-label="Loading hub…">
      <div className="flex items-center space-x-4">
        <div className="h-10 w-10 bg-slate-800 rounded-lg animate-pulse" />
        <div className="space-y-2">
          <div className="h-6 w-48 bg-slate-800 rounded animate-pulse" />
          <div className="h-4 w-24 bg-slate-800 rounded animate-pulse" />
        </div>
      </div>
      <div className="flex space-x-2 border-b border-slate-800 pb-2">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-8 w-24 bg-slate-800 rounded animate-pulse" />
        ))}
      </div>
      <div className="h-64 bg-slate-900/50 rounded-xl border border-slate-800/80 animate-pulse" />
    </div>
  );
}

function HubShellError({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center space-y-4">
      <AlertTriangle className="w-12 h-12 text-amber-500" />
      <h3 className="text-lg font-semibold text-slate-200">Failed to load hub</h3>
      <p className="text-sm text-slate-400 max-w-md">
        An error occurred while fetching hub details. Please check your network connection and retry.
      </p>
      <button
        id="hub-shell-retry-btn"
        className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm rounded-lg transition-colors"
        onClick={onRetry}
      >
        Retry
      </button>
    </div>
  );
}

type FetchStatus = "idle" | "loading" | "success" | "not_found" | "error";

export function HubShell() {
  const { hubType, hubId } = useParams<{ hubType: string; hubId: string }>();
  const location = useLocation();
  const navigate = useNavigate();

  const [hub, setHub] = useState<Hub | null>(null);
  const [hubRole, setHubRole] = useState<HubRole | null>(null);
  const [status, setStatus] = useState<FetchStatus>("idle");

  const user = useStore((state) => state.user);
  const setActiveHub = useStore((state) => state.setActiveHub);
  const isPlatformAdminStore = useStore((state) => state.isPlatformAdmin);
  const isPlatformAdmin = isPlatformAdminStore || user?.platform_role === "admin" || user?.role === "admin";

  const fetchHub = async () => {
    if (!hubType || !hubId) {
      setStatus("not_found");
      return;
    }
    setStatus("loading");
    try {
      const data = await api.hubs.get(hubType, hubId);
      const hubObj = data?.hub || (data as unknown as Hub);
      const role = data?.membership?.hub_role ?? (data as any)?.my_role ?? null;
      setHub(hubObj);
      setHubRole(role);
      if (hubObj?.id) {
        setActiveHub(hubObj.id);
      }
      setStatus("success");
    } catch (err: any) {
      if (err instanceof HubApiError && err.status === 404) {
        setStatus("not_found");
      } else if (err?.message?.includes("404")) {
        setStatus("not_found");
      } else {
        setStatus("error");
      }
    }
  };

  useEffect(() => {
    fetchHub();
    return () => {
      setActiveHub(null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hubId, hubType]);

  const handleUnarchive = async () => {
    if (!hub) return;
    try {
      const updated = await api.hubs.unarchive(hub.id);
      setHub(updated);
    } catch (err) {
      console.error("Failed to unarchive hub:", err);
    }
  };

  const contextValue = useMemo<HubContextValue>(() => {
    const isArchived = hub?.is_archived || false;
    return {
      hub,
      hubRole,
      isPlatformAdmin,
      isArchived,
      isLoading: status === "loading",
      can: (action: HubAction) => evaluate(hubRole, action, isArchived, isPlatformAdmin).allowed,
      denyReason: (action: HubAction) => evaluate(hubRole, action, isArchived, isPlatformAdmin).reason,
    };
  }, [hub, hubRole, isPlatformAdmin, status]);

  const validHubType = (hubType && hubType in WORKSPACE_TABS ? hubType : "ingestion") as HubType;
  const workspaceTabs = WORKSPACE_TABS[validHubType] || [];

  const subPathKey = location.pathname
    .replace(`/hubs/${hubType}/${hubId}`, "")
    .replace(/^\//, "")
    .split("/")[0] || "overview";

  if (status === "loading" || status === "idle") {
    return <HubShellSkeleton />;
  }

  if (status === "not_found") {
    return <HubNotFound />;
  }

  if (status === "error") {
    return <HubShellError onRetry={fetchHub} />;
  }

  const renderTabLink = (tab: HubTabConfig) => {
    const IconComp = ICON_MAP[tab.iconName] || LayoutDashboard;
    const targetUrl = tab.pathSuffix
      ? `/hubs/${hubType}/${hubId}/${tab.pathSuffix}`
      : `/hubs/${hubType}/${hubId}`;

    const isActive =
      tab.pathSuffix === ""
        ? location.pathname === `/hubs/${hubType}/${hubId}` || location.pathname === `/hubs/${hubType}/${hubId}/`
        : location.pathname.includes(`/hubs/${hubType}/${hubId}/${tab.pathSuffix}`);

    return (
      <NavLink
        key={tab.id}
        to={targetUrl}
        className={`flex items-center space-x-2 px-3 py-2 text-sm font-medium rounded-md transition-colors ${
          isActive
            ? "bg-indigo-500/10 text-indigo-400 border-b-2 border-indigo-500"
            : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
        }`}
      >
        <IconComp className="w-4 h-4" />
        <span>{tab.label}</span>
      </NavLink>
    );
  };

  return (
    <HubProvider value={contextValue}>
      <div className="flex-1 flex flex-col min-h-0 bg-[#080809]" data-testid="hub-shell">
        {/* Archived Banner */}
        {hub?.is_archived && (
          <div className="bg-amber-950/40 border-b border-amber-800/40 px-6 py-2.5 flex items-center justify-between" role="alert">
            <div className="flex items-center space-x-2 text-amber-300 text-sm font-medium">
              <Archive className="w-4 h-4 text-amber-400" />
              <span>This hub is archived and read-only.</span>
            </div>
            {contextValue.can("archive_hub") && (
              <button
                onClick={handleUnarchive}
                className="px-3 py-1 bg-amber-600/20 hover:bg-amber-600/30 text-amber-300 text-xs font-semibold rounded border border-amber-500/30 transition-colors"
              >
                Unarchive Hub
              </button>
            )}
          </div>
        )}

        {/* Hub Header */}
        <header className="px-6 lg:px-10 pt-6 pb-4 border-b border-slate-800/80 bg-slate-950/40 flex flex-col space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div
                className="w-10 h-10 rounded-xl flex items-center justify-center font-bold text-white shadow-lg"
                style={{ backgroundColor: hub?.accent || "var(--accent-color, #4f46e5)" }}
              >
                {hub?.name?.charAt(0).toUpperCase() || "H"}
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <h1 className="text-xl font-bold font-display text-slate-100">{hub?.name}</h1>
                  <span className="px-2 py-0.5 text-xs font-semibold uppercase tracking-wider rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                    {hubType}
                  </span>
                </div>
                <p className="text-xs font-mono text-slate-500">
                  {hubType}/{hub?.slug || hubId}
                </p>
              </div>
            </div>
          </div>

          {/* Navigation Tabs Bar */}
          <nav className="flex items-center justify-between border-t border-slate-800/50 pt-3">
            <div className="flex items-center space-x-1">
              {workspaceTabs.map(renderTabLink)}
            </div>
            <div className="flex items-center space-x-1 border-l border-slate-800/60 pl-3">
              {SHARED_TABS.map(renderTabLink)}
            </div>
          </nav>
        </header>

        {/* Workspace Body / Outlet */}
        <div className="flex-1 overflow-y-auto p-6 lg:p-10">
          <AnimatePresence mode="wait">
            <motion.div
              key={subPathKey}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2 }}
              className="h-full"
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </HubProvider>
  );
}
