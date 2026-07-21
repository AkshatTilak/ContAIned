import React from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, Home } from "lucide-react";

export const NotFound: React.FC = () => {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-4 my-auto">
      <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-amber-400">
        <AlertTriangle className="w-10 h-10" />
      </div>
      <h2 className="text-2xl font-bold font-display text-[var(--text-primary)]">
        404 - Page Not Found
      </h2>
      <p className="text-xs text-[var(--text-muted)] max-w-md">
        The requested path does not exist or has been moved within the ContAIned platform.
      </p>
      <Link
        to="/system"
        className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-xs font-semibold text-white shadow-lg shadow-emerald-600/20 transition-all"
      >
        <Home className="w-4 h-4" />
        <span>Return to System Metrics</span>
      </Link>
    </div>
  );
};
