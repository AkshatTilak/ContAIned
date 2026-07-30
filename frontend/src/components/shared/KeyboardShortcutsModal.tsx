import React, { useEffect } from "react";
import { Keyboard, X } from "lucide-react";

export interface KeyboardShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const KeyboardShortcutsModal: React.FC<KeyboardShortcutsModalProps> = ({ isOpen, onClose }) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "?" && !isOpen) {
        // Only trigger if not in an input/textarea
        const tag = (e.target as HTMLElement)?.tagName;
        if (tag !== "INPUT" && tag !== "TEXTAREA") {
          e.preventDefault();
          // toggle or open
        }
      } else if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const shortcuts = [
    { key: "?", description: "Open Keyboard Shortcuts overlay" },
    { key: "Esc", description: "Close Modal / Drawer / Overlay" },
    { key: "↑ / ↓", description: "Navigate rows in DataTable" },
    { key: "Enter", description: "Activate selected row / Confirm action" },
    { key: "Space", description: "Toggle row selection" },
    { key: "← / →", description: "Switch active tab in Tab bar" },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-fadeIn">
      <div className="relative w-full max-w-lg rounded-2xl p-6 bg-[var(--bg-surface)] border border-[var(--border-default)] shadow-2xl space-y-4">
        <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-3">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
              <Keyboard className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold font-display text-[var(--text-primary)]">
                Keyboard Shortcuts
              </h3>
              <p className="text-xs text-[var(--text-muted)]">
                Global hotkeys and accessibility navigation
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)]"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="divide-y divide-[var(--border-subtle)]">
          {shortcuts.map((sc, i) => (
            <div key={i} className="flex items-center justify-between py-2.5 text-xs">
              <span className="text-[var(--text-secondary)]">{sc.description}</span>
              <kbd className="px-2.5 py-1 rounded bg-[var(--bg-input)] border border-[var(--border-default)] text-[11px] font-mono text-indigo-400 font-semibold shadow-inner">
                {sc.key}
              </kbd>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
