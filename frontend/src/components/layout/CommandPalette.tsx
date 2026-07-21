import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  Layers,
  Server,
  Users,
  ShieldCheck,
  Settings,
  Search,
  PlusCircle,
  Upload,
  Play,
  X,
  CornerDownLeft
} from "lucide-react";

interface CommandItem {
  id: string;
  category: "Navigation" | "Actions";
  label: string;
  description: string;
  icon: React.ElementType;
  shortcut?: string;
  perform: (navigate: ReturnType<typeof useNavigate>, onClose: () => void) => void;
}

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({ isOpen, onClose }) => {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);

  const commands: CommandItem[] = [
    {
      id: "nav-system",
      category: "Navigation",
      label: "Go to System Metrics",
      description: "View real-time telemetry, RAM, VRAM, and microservice status",
      icon: Activity,
      shortcut: "G S",
      perform: (nav, close) => {
        nav("/system");
        close();
      },
    },
    {
      id: "nav-ingestion",
      category: "Navigation",
      label: "Go to Ingestion Pipeline",
      description: "SyntraFlow document upload, parsing, and vector indexing",
      icon: Layers,
      shortcut: "G I",
      perform: (nav, close) => {
        nav("/ingestion");
        close();
      },
    },
    {
      id: "nav-workflow",
      category: "Navigation",
      label: "Go to Workflow Builder",
      description: "GuardRoute visual AI node canvas and orchestration",
      icon: Server,
      shortcut: "G W",
      perform: (nav, close) => {
        nav("/workflow");
        close();
      },
    },
    {
      id: "nav-agents",
      category: "Navigation",
      label: "Go to Agent Hub",
      description: "Manage, create, and configure autonomous AI agents",
      icon: Users,
      shortcut: "G A",
      perform: (nav, close) => {
        nav("/agents");
        close();
      },
    },
    {
      id: "nav-evalops",
      category: "Navigation",
      label: "Go to EvalOps Benchmark",
      description: "Run evaluation test suites, safety benchmarks, and accuracy metrics",
      icon: ShieldCheck,
      shortcut: "G E",
      perform: (nav, close) => {
        nav("/evalops");
        close();
      },
    },
    {
      id: "nav-settings",
      category: "Navigation",
      label: "Go to System Settings",
      description: "Configure Gateway Base URL, API keys, and platform parameters",
      icon: Settings,
      shortcut: "G ,",
      perform: (nav, close) => {
        nav("/settings");
        close();
      },
    },
    {
      id: "act-create-agent",
      category: "Actions",
      label: "Create New Agent",
      description: "Open agent creation wizard in Agent Hub",
      icon: PlusCircle,
      perform: (nav, close) => {
        nav("/agents");
        close();
      },
    },
    {
      id: "act-upload-doc",
      category: "Actions",
      label: "Upload Knowledge Document",
      description: "Ingest PDF, TXT, or Markdown into vector database",
      icon: Upload,
      perform: (nav, close) => {
        nav("/ingestion");
        close();
      },
    },
    {
      id: "act-run-eval",
      category: "Actions",
      label: "Run Evaluation Benchmark",
      description: "Trigger new benchmark evaluation run",
      icon: Play,
      perform: (nav, close) => {
        nav("/evalops");
        close();
      },
    },
  ];

  const filteredCommands = commands.filter((cmd) => {
    const searchStr = `${cmd.label} ${cmd.description} ${cmd.category}`.toLowerCase();
    return searchStr.includes(query.toLowerCase());
  });

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setQuery("");
    }
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % (filteredCommands.length || 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev - 1 + (filteredCommands.length || 1)) % (filteredCommands.length || 1));
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

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, filteredCommands, selectedIndex, navigate, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-md flex items-start justify-center pt-20 p-4">
      {/* Backdrop click listener */}
      <div className="fixed inset-0" onClick={onClose} />

      {/* Modal Dialog */}
      <div className="relative w-full max-w-xl bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-xl shadow-2xl overflow-hidden z-10 flex flex-col max-h-[70vh]">
        {/* Search Input Bar */}
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-[var(--border-subtle)] bg-[var(--bg-input)]">
          <Search className="w-4 h-4 text-emerald-400 shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type a command or search path..."
            className="w-full bg-transparent text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none"
          />
          {query ? (
            <button
              onClick={() => setQuery("")}
              className="p-1 rounded text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          ) : (
            <kbd className="px-1.5 py-0.5 rounded bg-[var(--bg-surface-alt)] border border-[var(--border-subtle)] text-[10px] text-[var(--text-muted)] font-mono">
              ESC
            </kbd>
          )}
        </div>

        {/* Command List */}
        <div className="overflow-y-auto p-2 space-y-1 divide-y divide-[var(--border-subtle)]">
          {filteredCommands.length === 0 ? (
            <div className="py-8 text-center text-xs text-[var(--text-muted)]">
              No matching commands or navigation paths found for "{query}".
            </div>
          ) : (
            filteredCommands.map((cmd, idx) => {
              const Icon = cmd.icon;
              const isSelected = idx === selectedIndex;
              return (
                <button
                  key={cmd.id}
                  onClick={() => cmd.perform(navigate, onClose)}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-left transition-all text-xs ${
                    isSelected
                      ? "bg-[var(--emerald-soft)] text-emerald-400 border border-emerald-500/30"
                      : "text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]"
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div
                      className={`p-1.5 rounded-md ${
                        isSelected ? "bg-emerald-500/20 text-emerald-400" : "bg-[var(--bg-input)] text-[var(--text-muted)]"
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                    </div>
                    <div className="truncate">
                      <div className="font-medium text-[var(--text-primary)] flex items-center gap-2">
                        <span>{cmd.label}</span>
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-[var(--bg-surface-alt)] text-[var(--text-muted)]">
                          {cmd.category}
                        </span>
                      </div>
                      <div className="text-[11px] text-[var(--text-muted)] truncate">
                        {cmd.description}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {cmd.shortcut && (
                      <kbd className="px-1.5 py-0.5 rounded bg-[var(--bg-surface-alt)] border border-[var(--border-subtle)] text-[10px] text-[var(--text-muted)] font-mono">
                        {cmd.shortcut}
                      </kbd>
                    )}
                    {isSelected && <CornerDownLeft className="w-3.5 h-3.5 text-emerald-400" />}
                  </div>
                </button>
              );
            })
          )}
        </div>

        {/* Modal Footer Hints */}
        <div className="px-4 py-2 bg-[var(--bg-surface-alt)] border-t border-[var(--border-subtle)] flex items-center justify-between text-[11px] text-[var(--text-muted)]">
          <div className="flex items-center gap-3">
            <span>
              <kbd className="font-mono bg-[var(--bg-input)] px-1 rounded border border-[var(--border-subtle)]">↑↓</kbd> navigate
            </span>
            <span>
              <kbd className="font-mono bg-[var(--bg-input)] px-1 rounded border border-[var(--border-subtle)]">↵</kbd> select
            </span>
          </div>
          <div className="flex items-center gap-1 text-emerald-400 font-medium">
            <span>ContAI ned Command Bar</span>
          </div>
        </div>
      </div>
    </div>
  );
};
