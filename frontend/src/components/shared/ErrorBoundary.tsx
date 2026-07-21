import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { AlertOctagon, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught rendering error:', error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex flex-col items-center justify-center min-h-[300px] p-8 m-4 rounded-2xl border border-[rgba(239,68,68,0.3)] bg-[var(--bg-surface)] text-center shadow-xl">
          <div className="p-4 rounded-full bg-[var(--rose-soft)] text-[var(--accent-rose)] mb-4">
            <AlertOctagon className="w-10 h-10" />
          </div>
          <h2 className="text-lg font-bold font-display text-[var(--text-primary)]">
            Something went wrong
          </h2>
          <p className="text-xs text-[var(--text-secondary)] mt-1 max-w-md">
            {this.state.error?.message || 'An unexpected UI rendering exception occurred.'}
          </p>
          <button
            onClick={this.handleReset}
            className="mt-5 px-4 py-2 text-xs font-semibold rounded-lg bg-[var(--accent-indigo)] text-white hover:opacity-90 transition-all flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Reload Component
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
