import React, { useEffect, useState } from 'react';
import { AlertTriangle, X } from 'lucide-react';

export interface ConfirmModalProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  isDanger?: boolean;
  confirmText?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export const ConfirmModal: React.FC<ConfirmModalProps> = ({
  isOpen,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  isDanger = false,
  confirmText,
  onConfirm,
  onCancel,
}) => {
  const [inputVal, setInputVal] = useState("");

  useEffect(() => {
    if (!isOpen) {
      setInputVal("");
    }
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;
      if (e.key === 'Escape') {
        onCancel();
      } else if (e.key === 'Enter') {
        if (!confirmText || inputVal === confirmText) {
          onConfirm();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onConfirm, onCancel, confirmText, inputVal]);

  if (!isOpen) return null;

  const isConfirmedDisabled = confirmText ? inputVal !== confirmText : false;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-fadeIn">
      <div
        className="relative w-full max-w-md rounded-2xl p-6 shadow-2xl border transition-all duration-200"
        style={{
          backgroundColor: 'var(--bg-surface)',
          borderColor: isDanger ? 'rgba(239, 68, 68, 0.3)' : 'var(--border-default)',
        }}
      >
        <button
          onClick={onCancel}
          className="absolute top-4 right-4 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
          aria-label="Close modal"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-start gap-4">
          <div
            className="p-3 rounded-xl flex items-center justify-center shrink-0"
            style={{
              backgroundColor: isDanger ? 'var(--rose-soft)' : 'var(--indigo-soft)',
              color: isDanger ? 'var(--accent-rose)' : 'var(--accent-indigo)',
            }}
          >
            <AlertTriangle className="w-6 h-6" />
          </div>

          <div className="flex-1 space-y-2">
            <h3 className="text-lg font-semibold text-[var(--text-primary)] font-display">
              {title}
            </h3>
            <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
              {message}
            </p>
            {confirmText && (
              <div className="pt-2">
                <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">
                  Type <span className="font-mono text-rose-400 font-bold">{confirmText}</span> to confirm:
                </label>
                <input
                  type="text"
                  value={inputVal}
                  onChange={(e) => setInputVal(e.target.value)}
                  placeholder={confirmText}
                  className="w-full px-3 py-2 rounded-lg bg-[var(--bg-input)] border border-[var(--border-default)] text-xs text-[var(--text-primary)] font-mono focus:outline-none focus:border-rose-500"
                />
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 mt-6">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm font-medium rounded-lg border border-[var(--border-default)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] transition-all"
          >
            {cancelLabel}
          </button>
          <button
            disabled={isConfirmedDisabled}
            onClick={onConfirm}
            className="px-4 py-2 text-sm font-semibold rounded-lg shadow-md transition-all flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
            style={{
              backgroundColor: isDanger ? 'var(--accent-rose)' : 'var(--accent-indigo)',
              color: '#FFFFFF',
            }}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConfirmModal;
