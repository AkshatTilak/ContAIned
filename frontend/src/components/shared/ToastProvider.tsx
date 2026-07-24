import React, { createContext, useContext, useState, useCallback } from 'react';
import { CheckCircle2, AlertTriangle, AlertCircle, Info, X } from 'lucide-react';

export type ToastType = 'success' | 'warning' | 'error' | 'info';

export interface ToastMessage {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
  duration?: number;
}

interface ToastContextType {
  toast: (msg: Omit<ToastMessage, 'id'>) => void;
  addToast: (message: string, type?: ToastType) => void;
  success: (title: string, message?: string) => void;
  error: (title: string, message?: string) => void;
  warning: (title: string, message?: string) => void;
  info: (title: string, message?: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const useToast = (): ToastContextType => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    ({ type, title, message, duration = 4000 }: Omit<ToastMessage, 'id'>) => {
      const id = Math.random().toString(36).substring(2, 9);
      const newToast: ToastMessage = { id, type, title, message, duration };

      setToasts((prev) => [...prev, newToast]);

      if (duration > 0) {
        setTimeout(() => {
          removeToast(id);
        }, duration);
      }
    },
    [removeToast]
  );

  const addToast = useCallback(
    (message: string, type: ToastType = 'info') => {
      toast({ type, title: message });
    },
    [toast]
  );

  const success = useCallback((title: string, message?: string) => toast({ type: 'success', title, message }), [toast]);
  const error = useCallback((title: string, message?: string) => toast({ type: 'error', title, message }), [toast]);
  const warning = useCallback((title: string, message?: string) => toast({ type: 'warning', title, message }), [toast]);
  const info = useCallback((title: string, message?: string) => toast({ type: 'info', title, message }), [toast]);

  return (
    <ToastContext.Provider value={{ toast, addToast, success, error, warning, info }}>
      {children}
      {/* Toast Render Stack */}
      <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2.5 max-w-sm w-full pointer-events-none">
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onClose={() => removeToast(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
};

const iconMap: Record<ToastType, React.ReactNode> = {
  success: <CheckCircle2 className="w-5 h-5 text-[var(--accent-emerald)] shrink-0" />,
  warning: <AlertTriangle className="w-5 h-5 text-[var(--accent-amber)] shrink-0" />,
  error: <AlertCircle className="w-5 h-5 text-[var(--accent-rose)] shrink-0" />,
  info: <Info className="w-5 h-5 text-[var(--accent-cyan)] shrink-0" />,
};

const borderMap: Record<ToastType, string> = {
  success: 'rgba(16, 185, 129, 0.3)',
  warning: 'rgba(245, 158, 11, 0.3)',
  error: 'rgba(239, 68, 68, 0.3)',
  info: 'rgba(6, 182, 212, 0.3)',
};

const ToastItem: React.FC<{ toast: ToastMessage; onClose: () => void }> = ({ toast, onClose }) => {
  return (
    <div
      className="pointer-events-auto flex items-start gap-3 p-4 rounded-xl shadow-xl border backdrop-blur-md transition-all duration-300 transform translate-y-0"
      style={{
        backgroundColor: 'rgba(20, 21, 26, 0.92)',
        borderColor: borderMap[toast.type],
      }}
    >
      {iconMap[toast.type]}
      <div className="flex-1 min-w-0">
        <h4 className="text-xs font-semibold text-[var(--text-primary)]">{toast.title}</h4>
        {toast.message && (
          <p className="text-xs text-[var(--text-secondary)] mt-0.5 leading-snug break-words">
            {toast.message}
          </p>
        )}
      </div>
      <button
        onClick={onClose}
        className="text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors p-0.5"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
};

export default ToastProvider;
