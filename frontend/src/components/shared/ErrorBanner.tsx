import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface ErrorBannerProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  className?: string;
}

export const ErrorBanner: React.FC<ErrorBannerProps> = ({
  title = 'Service Error',
  message,
  onRetry,
  className = '',
}) => {
  return (
    <div
      className={`p-4 rounded-xl border flex items-start justify-between gap-3 backdrop-blur-md bg-[var(--rose-soft)] border-[rgba(239,68,68,0.3)] text-[var(--accent-rose)] ${className}`}
    >
      <div className="flex items-start gap-3">
        <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
        <div>
          <h4 className="text-xs font-semibold">{title}</h4>
          <p className="text-xs opacity-90 mt-0.5 leading-snug">{message}</p>
        </div>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-md border border-[rgba(239,68,68,0.4)] hover:bg-[rgba(239,68,68,0.2)] transition-colors shrink-0"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Retry
        </button>
      )}
    </div>
  );
};

export default ErrorBanner;
