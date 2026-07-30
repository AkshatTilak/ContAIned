import React, { useState, useEffect, useRef, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  Layers,
  Bot,
  Plug,
  Settings,
  Search,
  PlusCircle,
  X,
  CornerDownLeft,
  Building2,
  GitFork,
  CheckSquare,
  Users,
  Link2,
} from "lucide-react";
import { routes } from "../../routes";
import { useStore } from "../../store/useStore";
import { evaluate } from "../../hooks/useHubPermissions";

interface CommandItem {
  id: string;
  category: "Hub" | "Navigation" | "Actions";
  label: string;
  description: string;
  icon: React.ElementType;
  shortcut?: string;
  perform: (navigate: ReturnType<typeof useNavigate>, onClose: () => void) => void;
}

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenHubSwitcher?: () => void;
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  onOpenHubSwitcher,
}) => {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);

  const activeHubId = useStore((state) => state.activeHubId);
  const hubsById = useStore((state) => state.hubsById);
  const activeHub = activeHubId ? hubsById[activeHubId] : null;

  const commands: CommandItem[] = useMemo(() => {
    const list: CommandItem[] = [
      {
        id: "nav-hubs",
        category: "Navigation",
        label: "Go to Hub Directory",
        description: "Browse and filter all Ingestion, Agent, Workflow, and Eval hubs",
        icon: Building2,
        shortcut: "G H",
        perform: (nav, close) => {
          nav(routes.hubs.directory());
          close();
        },
      },
      {
        id: "nav-create-hub",
        category: "Actions",
        label: "Create New Hub",
        description: "Wizard to initialize a new hub workspace",
        icon: PlusCircle,
        shortcut: "C H",
        perform: (nav, close) => {
          nav(routes.hubs.create());
          close();
        },
      },
      {
        id: "action-switch-hub",
        category: "Actions",
        label: "Switch Active Hub...",
        description: "Fuzzy search and jump to any hub workspace",
        icon: Building2,
        shortcut: "⌘K",
        perform: (_, close) => {
          close();
          if (onOpenHubSwitcher) {
            onOpenHubSwitcher();
          }
        },
      },
      {
        id: "nav-system",
        category: "Navigation",
        label: "Go to System Metrics",
        description: "View real-time telemetry, RAM, VRAM, and microservice status",
        icon: Activity,
        shortcut: "G S",
        perform: (nav, close) => {
          nav(routes.platform.system());
          close();
        },
      },
      {
        id: "nav-playground",
        category: "Navigation",
        label: "Go to Model Playground",
        description: "Interactive LLM prompt arena & test environment",
        icon: Bot,
        shortcut: "G P",
        perform: (nav, close) => {
          nav(routes.platform.playground());
          close();
        },
      },
      {
        id: "nav-mcp",
        category: "Navigation",
        label: "Go to MCP Registry",
        description: "Model Context Protocol tools and servers",
        icon: Plug,
        shortcut: "G M",
        perform: (nav, close) => {
          nav(routes.platform.mcp());
          close();
        },
      },
      {
        id: "nav-settings",
        category: "Navigation",
        label: "Go to Settings",
        description: "Configure system gateway, API keys, and preferences",
        icon: Settings,
        shortcut: "G ,",
        perform: (nav, close) => {
          nav(routes.platform.settings());
          close();
        },
      },
    ];

    if (activeHub) {
      const isArchived = activeHub.is_archived;
      const canCreate = evaluate(activeHub.my_role, "create_resource", isArchived).allowed;

      if (activeHub.hub_type === "ingestion" && canCreate) {
        list.unshift({
          id: "hub-new-collection",
          category: "Hub",
          label: `New Collection in ${activeHub.name}`,
          description: "Create vector collection binding in active hub",
          icon: Layers,
          perform: (nav, close) => {
            nav(routes.ingestionHub.collections(activeHub.id));
            close();
          },
        });
      }

      if (activeHub.hub_type === "agent" && canCreate) {
        list.unshift({
          id: "hub-new-agent",
          category: "Hub",
          label: `New Agent in ${activeHub.name}`,
          description: "Create agent definition in active hub",
          icon: Bot,
          perform: (nav, close) => {
            nav(routes.agentHub.agents(activeHub.id));
            close();
          },
        });
      }

      if (activeHub.hub_type === "workflow" && canCreate) {
        list.unshift({
          id: "hub-new-workflow",
          category: "Hub",
          label: `New Workflow in ${activeHub.name}`,
          description: "Author new multi-workflow graph in active hub",
          icon: GitFork,
          perform: (nav, close) => {
            nav(routes.workflowHub.workflows(activeHub.id));
            close();
          },
        });
      }

      if (activeHub.hub_type === "eval" && canCreate) {
        list.unshift({
          id: "hub-new-suite",
          category: "Hub",
          label: `New Suite in ${activeHub.name}`,
          description: "Create evaluation test suite in active hub",
          icon: CheckSquare,
          perform: (nav, close) => {
            nav(routes.evalHub.suites(activeHub.id));
            close();
          },
        });
      }

      list.push(
        {
          id: "hub-members",
          category: "Hub",
          label: `Manage Members of ${activeHub.name}`,
          description: "View and edit member roles in active hub",
          icon: Users,
          perform: (nav, close) => {
            nav(routes.hubs.members(activeHub.hub_type, activeHub.id));
            close();
          },
        },
        {
          id: "hub-links",
          category: "Hub",
          label: `Manage Links for ${activeHub.name}`,
          description: "Configure hub-to-hub access grants",
          icon: Link2,
          perform: (nav, close) => {
            nav(routes.hubs.links(activeHub.hub_type, activeHub.id));
            close();
          },
        }
      );
    }

    return list;
  }, [activeHub, onOpenHubSwitcher]);

  const filteredCommands = useMemo(() => {
    if (!query.trim()) return commands;
    const q = query.toLowerCase();
    return commands.filter(
      (cmd) =>
        cmd.label.toLowerCase().includes(q) ||
        cmd.description.toLowerCase().includes(q) ||
        cmd.category.toLowerCase().includes(q)
    );
  }, [commands, query]);

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

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (filteredCommands.length > 0 ? (prev + 1) % filteredCommands.length : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) =>
        filteredCommands.length > 0 ? (prev - 1 + filteredCommands.length) % filteredCommands.length : 0
      );
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (filteredCommands[selectedIndex]) {
        filteredCommands[selectedIndex].perform(navigate, onClose);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 px-4 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-xl bg-[#0f1117] border border-slate-800 rounded-xl shadow-2xl overflow-hidden flex flex-col">
        <div className="p-4 border-b border-slate-800 flex items-center space-x-3 bg-slate-950/40">
          <Search className="w-5 h-5 text-slate-400 shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a command or search platform features..."
            className="flex-1 bg-transparent text-slate-100 placeholder-slate-500 text-sm focus:outline-none"
          />
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="max-h-80 overflow-y-auto p-2 space-y-1 custom-scrollbar">
          {filteredCommands.length === 0 ? (
            <div className="p-8 text-center text-slate-500 text-sm">
              No commands found matching "{query}"
            </div>
          ) : (
            filteredCommands.map((cmd, idx) => {
              const Icon = cmd.icon;
              const isSelected = idx === selectedIndex;
              return (
                <div
                  key={cmd.id}
                  onClick={() => cmd.perform(navigate, onClose)}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors ${
                    isSelected
                      ? "bg-indigo-600/20 border border-indigo-500/40 text-slate-100"
                      : "hover:bg-slate-800/40 text-slate-300 border border-transparent"
                  }`}
                >
                  <div className="flex items-center space-x-3">
                    <Icon className="w-5 h-5 text-indigo-400 shrink-0" />
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="font-semibold text-sm">{cmd.label}</span>
                        {cmd.category === "Hub" && (
                          <span className="px-1.5 py-0.5 text-[10px] uppercase font-mono font-bold bg-indigo-500/20 text-indigo-300 rounded border border-indigo-500/30">
                            Hub Context
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-slate-500">{cmd.description}</p>
                    </div>
                  </div>
                  {cmd.shortcut && (
                    <kbd className="px-2 py-0.5 bg-slate-800 text-xs font-mono text-slate-400 rounded">
                      {cmd.shortcut}
                    </kbd>
                  )}
                </div>
              );
            })
          )}
        </div>

        <div className="p-3 border-t border-slate-800 bg-slate-950/60 flex items-center justify-between text-xs text-slate-500 font-mono">
          <span>Navigation & Actions</span>
          <div className="flex items-center space-x-2">
            <CornerDownLeft className="w-3.5 h-3.5" />
            <span>Select</span>
          </div>
        </div>
      </div>
    </div>
  );
};
