import { useState, useMemo, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Search,
  Plus,
  Filter,
  Building2,
  Layers,
  Bot,
  GitFork,
  CheckSquare,
  Users,
  Archive,
  MoreVertical,
  ArrowUpDown,
  RefreshCw,
  AlertCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useStore } from "../../store/useStore";
import { routes, type HubType } from "../../routes";
import { api } from "../../services/api";
import type { Hub } from "../../types/api";
import { EmptyState } from "../shared/EmptyState";

const HUB_SECTION_META: {
  type: HubType;
  title: string;
  description: string;
  icon: LucideIcon;
}[] = [
  {
    type: "ingestion",
    title: "Ingestion Hubs",
    description: "Vector collection bindings, document pipelines, and search indexes",
    icon: Layers,
  },
  {
    type: "agent",
    title: "Agent Hubs",
    description: "Autonomous AI agents, system prompts, and tool bindings",
    icon: Bot,
  },
  {
    type: "workflow",
    title: "Workflow Hubs",
    description: "Multi-workflow visual graphs, execution nodes, and published versions",
    icon: GitFork,
  },
  {
    type: "eval",
    title: "Eval Hubs",
    description: "Polymorphic test suites, RAGAS/DeepEval benchmarks, and flow trace assertions",
    icon: CheckSquare,
  },
];

export function HubDirectory() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const hubsByType = useStore((state) => state.hubsByType);
  const hubListStatus = useStore((state) => state.hubListStatus);
  const hubListError = useStore((state) => state.hubListError);
  const setHubs = useStore((state) => state.setHubs);
  const setHubListStatus = useStore((state) => state.setHubListStatus);

  const [searchQuery, setSearchQuery] = useState(searchParams.get("q") || "");
  const [selectedTypes, setSelectedTypes] = useState<Set<HubType>>(() => {
    const rawTypes = searchParams.get("type");
    if (rawTypes) {
      return new Set(rawTypes.split(",") as HubType[]);
    }
    return new Set<HubType>(["ingestion", "agent", "workflow", "eval"]);
  });
  const [showArchived, setShowArchived] = useState(searchParams.get("archived") === "true");
  const [sortBy, setSortBy] = useState<"activity" | "name" | "created">(
    (searchParams.get("sort") as "activity" | "name" | "created") || "activity"
  );

  const fetchAllHubs = async () => {
    setHubListStatus("loading");
    try {
      const hubsList = await api.hubs.list({ includeArchived: true });
      setHubs(hubsList);
    } catch (err: any) {
      setHubListStatus("error", err?.message || "Failed to load hubs");
    }
  };

  useEffect(() => {
    fetchAllHubs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Synchronize URL query params
  useEffect(() => {
    const params: Record<string, string> = {};
    if (searchQuery.trim()) params.q = searchQuery.trim();
    if (selectedTypes.size < 4) params.type = Array.from(selectedTypes).join(",");
    if (showArchived) params.archived = "true";
    if (sortBy !== "activity") params.sort = sortBy;
    setSearchParams(params, { replace: true });
  }, [searchQuery, selectedTypes, showArchived, sortBy, setSearchParams]);

  const toggleTypeFilter = (type: HubType) => {
    setSelectedTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) {
        if (next.size > 1) next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  };

  const processHubList = (hubsList: Hub[]) => {
    let filtered = hubsList;

    if (!showArchived) {
      filtered = filtered.filter((h) => !h.is_archived);
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      filtered = filtered.filter(
        (h) =>
          h.name.toLowerCase().includes(q) ||
          h.slug.toLowerCase().includes(q) ||
          (h.description && h.description.toLowerCase().includes(q))
      );
    }

    return filtered.sort((a, b) => {
      if (sortBy === "name") return a.name.localeCompare(b.name);
      if (sortBy === "created") return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      const timeA = a.last_activity_at ? new Date(a.last_activity_at).getTime() : 0;
      const timeB = b.last_activity_at ? new Date(b.last_activity_at).getTime() : 0;
      return timeB - timeA;
    });
  };

  if (hubListStatus === "loading") {
    return (
      <div className="space-y-8 animate-pulse p-2">
        <div className="h-10 bg-slate-800 rounded-lg w-1/3" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-48 bg-slate-900/60 border border-slate-800 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  if (hubListStatus === "error") {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-center space-y-4">
        <AlertCircle className="w-12 h-12 text-red-500" />
        <h3 className="text-lg font-semibold text-slate-200">Failed to load Hub Directory</h3>
        <p className="text-sm text-slate-400 max-w-md">{hubListError || "Network request failed"}</p>
        <button
          onClick={fetchAllHubs}
          className="flex items-center space-x-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm rounded-lg transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          <span>Retry</span>
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-12">
      {/* Header & Main Create Action */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold font-display text-slate-100 flex items-center space-x-3">
            <Building2 className="w-7 h-7 text-indigo-400" />
            <span>Hub Directory</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Central directory of all hub workspaces across Ingestion, Agent, Workflow, and Eval domains.
          </p>
        </div>
        <button
          id="hub-directory-create-btn"
          onClick={() => navigate(routes.hubs.create())}
          className="flex items-center justify-center space-x-2 px-4 py-2.5 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-semibold text-sm rounded-xl shadow-lg shadow-indigo-500/20 transition-all shrink-0"
        >
          <Plus className="w-4 h-4" />
          <span>Create Hub</span>
        </button>
      </div>

      {/* Sticky Toolbar: Search, Filters, Sort */}
      <div className="sticky top-0 z-20 bg-[#080809]/90 backdrop-blur-md py-3 border-b border-slate-800/80 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex flex-1 items-center space-x-3 max-w-md">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search hubs by name, slug, or description..."
              className="w-full bg-slate-900/80 border border-slate-800 rounded-xl pl-9 pr-4 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Type Filter Chips */}
          <div className="flex items-center space-x-1 bg-slate-900/60 p-1 border border-slate-800 rounded-lg">
            {HUB_SECTION_META.map(({ type, title }) => {
              const active = selectedTypes.has(type);
              return (
                <button
                  key={type}
                  onClick={() => toggleTypeFilter(type)}
                  className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors capitalize ${
                    active
                      ? "bg-indigo-600/30 text-indigo-300 border border-indigo-500/40"
                      : "text-slate-500 hover:text-slate-300"
                  }`}
                >
                  {type}
                </button>
              );
            })}
          </div>

          {/* Show Archived Toggle */}
          <label className="flex items-center space-x-2 text-xs font-medium text-slate-400 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showArchived}
              onChange={(e) => setShowArchived(e.target.checked)}
              className="rounded border-slate-800 bg-slate-900 text-indigo-600 focus:ring-0"
            />
            <span>Show archived</span>
          </label>

          {/* Sort Selector */}
          <div className="flex items-center space-x-1.5 bg-slate-900/60 px-3 py-1.5 border border-slate-800 rounded-lg text-xs text-slate-400">
            <ArrowUpDown className="w-3.5 h-3.5" />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="bg-transparent text-slate-200 focus:outline-none cursor-pointer"
            >
              <option value="activity" className="bg-slate-900 text-slate-200">Last Activity</option>
              <option value="name" className="bg-slate-900 text-slate-200">Name</option>
              <option value="created" className="bg-slate-900 text-slate-200">Created Date</option>
            </select>
          </div>
        </div>
      </div>

      {/* Hub Sections */}
      {HUB_SECTION_META.filter(({ type }) => selectedTypes.has(type)).map(
        ({ type, title, description, icon: SectionIcon }) => {
          const typeHubs = processHubList(hubsByType[type] || []);

          return (
            <section key={type} className="space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800/60 pb-2">
                <div className="flex items-center space-x-2.5">
                  <SectionIcon className="w-5 h-5 text-indigo-400" />
                  <h2 className="text-lg font-bold text-slate-100 font-display">{title}</h2>
                  <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-slate-800 text-slate-400 border border-slate-700">
                    {typeHubs.length}
                  </span>
                </div>
                <button
                  onClick={() => navigate(`/hubs/new?type=${type}`)}
                  className="text-xs text-indigo-400 hover:text-indigo-300 font-medium flex items-center space-x-1 transition-colors"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>New {type} hub</span>
                </button>
              </div>

              {typeHubs.length === 0 ? (
                <EmptyState
                  icon={SectionIcon}
                  title={`No ${title} Found`}
                  description={`Create your first ${type} hub workspace to configure resources, manage members, and build features.`}
                  actionLabel={`Create ${type} Hub`}
                  onAction={() => navigate(`/hubs/new?type=${type}`)}
                />
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {typeHubs.map((hub) => (
                    <motion.div
                      key={hub.id}
                      onClick={() => navigate(routes.hubs.shell(hub.hub_type, hub.id))}
                      whileHover={{ y: -2 }}
                      className={`p-5 bg-slate-900/50 hover:bg-slate-900/80 border rounded-xl cursor-pointer transition-all flex flex-col justify-between space-y-4 shadow-lg ${
                        hub.is_archived
                          ? "border-amber-900/40 opacity-75"
                          : "border-slate-800/80 hover:border-indigo-500/40"
                      }`}
                    >
                      <div className="space-y-3">
                        <div className="flex items-start justify-between">
                          <div className="flex items-center space-x-3">
                            <div
                              className="w-9 h-9 rounded-xl flex items-center justify-center font-bold text-white shadow-md text-sm shrink-0"
                              style={{ backgroundColor: hub.accent || "#6366f1" }}
                            >
                              {hub.name.charAt(0).toUpperCase()}
                            </div>
                            <div>
                              <h3 className="font-bold text-slate-100 text-base font-display truncate max-w-[180px]">
                                {hub.name}
                              </h3>
                              <p className="text-xs font-mono text-slate-500 truncate">{hub.slug}</p>
                            </div>
                          </div>
                          {hub.is_archived && (
                            <span className="flex items-center space-x-1 text-[10px] uppercase font-bold text-amber-400 bg-amber-950/60 px-2 py-0.5 rounded border border-amber-800/40">
                              <Archive className="w-3 h-3" />
                              <span>Archived</span>
                            </span>
                          )}
                        </div>

                        {hub.description && (
                          <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
                            {hub.description}
                          </p>
                        )}
                      </div>

                      {/* Card Footer Info */}
                      <div className="pt-3 border-t border-slate-800/60 flex items-center justify-between text-xs text-slate-500 font-mono">
                        <div className="flex items-center space-x-2">
                          <Users className="w-3.5 h-3.5 text-slate-400" />
                          <span>{hub.member_count || 1} members</span>
                        </div>
                        <span className="capitalize text-indigo-400 font-semibold px-2 py-0.5 rounded bg-indigo-950/40 border border-indigo-800/40">
                          {hub.my_role || "viewer"}
                        </span>
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}
            </section>
          );
        }
      )}
    </div>
  );
}
