import React, { useState } from "react";
import { Plus, MessageSquare, Trash2, Edit3, Search, ChevronLeft, ChevronRight, Check, X } from "lucide-react";
import type { PlaygroundSession } from "../../types/api";

interface SessionSidebarProps {
  sessions: PlaygroundSession[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onDeleteSession: (id: string) => void;
  onRenameSession: (id: string, newName: string) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

export const SessionSidebar: React.FC<SessionSidebarProps> = ({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  onRenameSession,
  isCollapsed,
  onToggleCollapse,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");

  const filteredSessions = sessions.filter((s) =>
    s.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const startRename = (s: PlaygroundSession, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(s.id);
    setEditName(s.name);
  };

  const confirmRename = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (editName.trim()) {
      onRenameSession(id, editName.trim());
    }
    setEditingId(null);
  };

  return (
    <div
      className={`bg-[var(--bg-input)] border-r border-[var(--border-default)] flex flex-col transition-all duration-300 select-none ${
        isCollapsed ? "w-16" : "w-64"
      }`}
    >
      {/* Sidebar Header */}
      <div className="p-3 border-b border-[var(--border-subtle)] flex items-center justify-between">
        {!isCollapsed && (
          <button
            onClick={onNewSession}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 font-semibold text-xs hover:bg-emerald-500/25 transition-colors shadow-sm"
          >
            <Plus className="w-4 h-4" />
            <span>New Chat Session</span>
          </button>
        )}
        {isCollapsed && (
          <button
            onClick={onNewSession}
            className="w-10 h-10 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 flex items-center justify-center hover:bg-emerald-500/25 transition-colors"
            title="New Chat Session"
          >
            <Plus className="w-4 h-4" />
          </button>
        )}
        <button
          onClick={onToggleCollapse}
          className="p-2 text-zinc-400 hover:text-zinc-200 hover:bg-[var(--bg-elevated)] rounded-xl transition-colors ml-1"
          title={isCollapsed ? "Expand Sessions Sidebar" : "Collapse Sessions Sidebar"}
        >
          {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Search Filter */}
      {!isCollapsed && (
        <div className="p-3 border-b border-[var(--border-subtle)]">
          <div className="relative flex items-center">
            <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-3 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search sessions..."
              className="w-full pl-8 pr-3 py-1.5 bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-lg text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-emerald-500/50"
            />
          </div>
        </div>
      )}

      {/* Sessions List */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-1">
        {filteredSessions.length === 0 ? (
          !isCollapsed && (
            <div className="p-4 text-center text-xs text-zinc-500 italic">
              No saved sessions found
            </div>
          )
        ) : (
          filteredSessions.map((session) => {
            const isActive = session.id === activeSessionId;
            const isEditing = editingId === session.id;

            return (
              <div
                key={session.id}
                onClick={() => onSelectSession(session.id)}
                className={`group relative flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs font-medium cursor-pointer transition-all ${
                  isActive
                    ? "bg-emerald-500/15 border border-emerald-500/30 text-emerald-400"
                    : "text-zinc-300 hover:bg-[var(--bg-elevated)] hover:text-white border border-transparent"
                }`}
                title={isCollapsed ? session.name : undefined}
              >
                <MessageSquare className={`w-4 h-4 shrink-0 ${isActive ? "text-emerald-400" : "text-zinc-500"}`} />

                {!isCollapsed && (
                  <div className="flex-1 min-w-0 pr-1">
                    {isEditing ? (
                      <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="text"
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          className="w-full bg-[#080809] border border-emerald-500/50 rounded px-1.5 py-0.5 text-xs text-zinc-100 focus:outline-none"
                          autoFocus
                        />
                        <button
                          onClick={(e) => confirmRename(session.id, e)}
                          className="p-1 text-emerald-400 hover:text-emerald-300"
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditingId(null);
                          }}
                          className="p-1 text-zinc-400 hover:text-zinc-200"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : (
                      <>
                        <div className="font-semibold truncate leading-tight">{session.name}</div>
                        <div className="text-[10px] text-zinc-500 flex items-center justify-between mt-0.5">
                          <span className="truncate">{session.model_id?.split("/").pop() || "Gemini"}</span>
                          <span>{session.messages?.length || 0} msgs</span>
                        </div>
                      </>
                    )}
                  </div>
                )}

                {!isCollapsed && !isEditing && (
                  <div className="opacity-0 group-hover:opacity-100 flex items-center gap-1 transition-opacity">
                    <button
                      onClick={(e) => startRename(session, e)}
                      className="p-1 text-zinc-400 hover:text-emerald-400 transition-colors"
                      title="Rename"
                    >
                      <Edit3 className="w-3 h-3" />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteSession(session.id);
                      }}
                      className="p-1 text-zinc-400 hover:text-rose-400 transition-colors"
                      title="Delete Session"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
