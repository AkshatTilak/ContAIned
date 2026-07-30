import { useState, useEffect, useMemo, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Search, History, Check, X, Shield, Archive } from "lucide-react";
import { useStore } from "../../store/useStore";
import { routes, type HubType } from "../../routes";
import type { Hub, HubRole } from "../../types/api";

export interface HubSwitcherProps {
  isOpen: boolean;
  onClose: () => void;
}

const RECENTS_KEY = "contained.hub.recents.v1";

interface RecentEntry {
  hubId: string;
  hubType: HubType;
  lastVisitedAt: number;
}

export function getHubRecents(): RecentEntry[] {
  try {
    const raw = localStorage.getItem(RECENTS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function addHubRecent(hubId: string, hubType: HubType) {
  try {
    const current = getHubRecents().filter((r) => r.hubId !== hubId);
    const updated = [{ hubId, hubType, lastVisitedAt: Date.now() }, ...current].slice(0, 8);
    localStorage.setItem(RECENTS_KEY, JSON.stringify(updated));
  } catch {
    // ignore storage errors
  }
}

export function HubSwitcher({ isOpen, onClose }: HubSwitcherProps) {
  const navigate = useNavigate();
  const hubsById = useStore((state) => state.hubsById);
  const hubsByType = useStore((state) => state.hubsByType);

  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [includeArchived, setIncludeArchived] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const allHubs = useMemo(() => {
    return Object.values(hubsById);
  }, [hubsById]);

  const recents = useMemo(() => {
    const rawRecents = getHubRecents();
    return rawRecents
      .map((r) => ({ recent: r, hub: hubsById[r.hubId] }))
      .filter((item): item is { recent: RecentEntry; hub: Hub } => Boolean(item.hub));
  }, [hubsById]);

  const filteredHubs = useMemo(() => {
    let result = allHubs;

    if (!includeArchived) {
      result = result.filter((h) => !h.is_archived);
    }

    if (!query.trim()) {
      return result;
    }

    const q = query.toLowerCase().trim();
    return result.filter(
      (h) =>
        h.name.toLowerCase().includes(q) ||
        h.slug.toLowerCase().includes(q) ||
        h.hub_type.toLowerCase().includes(q)
    );
  }, [allHubs, query, includeArchived]);

  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  const handleSelectHub = (hub: Hub) => {
    addHubRecent(hub.id, hub.hub_type);
    onClose();
    navigate(routes.hubs.shell(hub.hub_type, hub.id));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (filteredHubs.length > 0 ? (prev + 1) % filteredHubs.length : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) =>
        filteredHubs.length > 0 ? (prev - 1 + filteredHubs.length) % filteredHubs.length : 0
      );
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (filteredHubs[selectedIndex]) {
        handleSelectHub(filteredHubs[selectedIndex]);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 px-4 bg-black/60 backdrop-blur-sm">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          transition={{ duration: 0.15 }}
          className="w-full max-w-xl bg-[#0f1117] border border-slate-800 rounded-xl shadow-2xl overflow-hidden flex flex-col"
        >
          {/* Search Header */}
          <div className="p-4 border-b border-slate-800 flex items-center space-x-3 bg-slate-950/40">
            <Search className="w-5 h-5 text-slate-400 shrink-0" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search hubs by name, slug, or type… (Cmd+K)"
              className="flex-1 bg-transparent text-slate-100 placeholder-slate-500 text-sm focus:outline-none"
            />
            <button
              onClick={onClose}
              className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Recents Bar when Query is Empty */}
          {!query && recents.length > 0 && (
            <div className="p-3 border-b border-slate-800/60 bg-slate-900/30">
              <div className="flex items-center space-x-2 text-xs font-semibold text-slate-400 mb-2">
                <History className="w-3.5 h-3.5" />
                <span>Recent Hubs</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {recents.map(({ hub }) => (
                  <button
                    key={hub.id}
                    onClick={() => handleSelectHub(hub)}
                    className="flex items-center space-x-1.5 px-2.5 py-1 rounded-lg bg-slate-800/60 hover:bg-slate-800 text-xs font-medium text-slate-300 border border-slate-700/50 transition-colors"
                  >
                    <span
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: hub.accent || "#6366f1" }}
                    />
                    <span>{hub.name}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Results List */}
          <div className="max-h-80 overflow-y-auto p-2 space-y-1 custom-scrollbar">
            {filteredHubs.length === 0 ? (
              <div className="p-8 text-center text-slate-500 text-sm">
                {allHubs.length === 0
                  ? "You are not a member of any hub yet."
                  : `No hubs match "${query}"`}
              </div>
            ) : (
              filteredHubs.map((hub, idx) => {
                const isSelected = idx === selectedIndex;
                return (
                  <div
                    key={hub.id}
                    onClick={() => handleSelectHub(hub)}
                    onMouseEnter={() => setSelectedIndex(idx)}
                    className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors ${
                      isSelected
                        ? "bg-indigo-600/20 border border-indigo-500/40 text-slate-100"
                        : "hover:bg-slate-800/40 text-slate-300 border border-transparent"
                    }`}
                  >
                    <div className="flex items-center space-x-3">
                      <div
                        className="w-3 h-3 rounded-full shrink-0"
                        style={{ backgroundColor: hub.accent || "#6366f1" }}
                      />
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="font-semibold text-sm">{hub.name}</span>
                          <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                            {hub.hub_type}
                          </span>
                        </div>
                        <p className="text-xs text-slate-500 font-mono">{hub.slug}</p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2 text-xs">
                      {hub.is_archived && (
                        <span className="flex items-center space-x-1 text-amber-400 bg-amber-950/50 px-2 py-0.5 rounded border border-amber-800/40">
                          <Archive className="w-3 h-3" />
                          <span>Archived</span>
                        </span>
                      )}
                      <span className="text-slate-400 font-mono capitalize flex items-center space-x-1">
                        <Shield className="w-3 h-3 text-indigo-400" />
                        <span>{hub.my_role || "viewer"}</span>
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Footer Controls */}
          <div className="p-3 border-t border-slate-800 bg-slate-950/60 flex items-center justify-between text-xs text-slate-500">
            <label className="flex items-center space-x-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={includeArchived}
                onChange={(e) => setIncludeArchived(e.target.checked)}
                className="rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-0"
              />
              <span>Include archived hubs</span>
            </label>
            <div className="flex items-center space-x-3 font-mono">
              <span>↑↓ Navigate</span>
              <span>↵ Select</span>
              <span>ESC Close</span>
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
