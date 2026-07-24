import React from "react";
import { useSearchParams } from "react-router-dom";
import { ShieldCheck } from "lucide-react";

export const LoginPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const error = searchParams.get("error");
  const detail = searchParams.get("detail");

  const gatewayUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";

  const handleLogin = (provider: "google" | "github") => {
    window.location.href = `${gatewayUrl}/auth/login/${provider}`;
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-100 p-6 relative overflow-hidden">
      {/* Background glow accents */}
      <div className="absolute -top-40 -left-40 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-cyan-600/20 rounded-full blur-3xl pointer-events-none" />

      <div className="w-full max-w-md bg-slate-900/80 border border-slate-800/80 backdrop-blur-xl rounded-2xl p-8 shadow-2xl z-10">
        <div className="flex flex-col items-center text-center mb-8">
          <div className="w-14 h-14 bg-indigo-600/20 border border-indigo-500/30 rounded-2xl flex items-center justify-center mb-4 text-indigo-400 shadow-inner">
            <ShieldCheck size={32} />
          </div>
          <h1 className="text-2xl font-bold tracking-tight bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
            ContAIned Platform
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Enterprise Autonomous Agent Orchestration Hub
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 rounded-xl bg-red-950/50 border border-red-800/50 text-red-300 text-xs flex flex-col gap-1">
            <span className="font-semibold text-red-200">
              Authentication Error
            </span>
            <span>
              {error === "account_deactivated"
                ? "Your account has been deactivated. Please contact an admin."
                : error === "google_failed" || error === "auth_failed"
                ? `Login attempt failed: ${detail || "Invalid credentials"}`
                : "Failed to complete authentication."}
            </span>
          </div>
        )}

        <div className="space-y-4">
          <button
            onClick={() => handleLogin("google")}
            className="w-full flex items-center justify-center gap-3 py-3 px-4 rounded-xl bg-slate-800/90 hover:bg-slate-800 border border-slate-700/80 font-medium text-sm transition-all duration-200 hover:border-slate-600 shadow-md group cursor-pointer"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
              />
            </svg>
            <span className="text-slate-200 group-hover:text-white">
              Sign in with Google
            </span>
          </button>

          <button
            onClick={() => handleLogin("github")}
            className="w-full flex items-center justify-center gap-3 py-3 px-4 rounded-xl bg-slate-800/90 hover:bg-slate-800 border border-slate-700/80 font-medium text-sm transition-all duration-200 hover:border-slate-600 shadow-md group cursor-pointer"
          >
            <svg className="w-5 h-5 fill-current text-slate-300 group-hover:text-white" viewBox="0 0 24 24">
              <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
            </svg>
            <span className="text-slate-200 group-hover:text-white">
              Sign in with GitHub
            </span>
          </button>
        </div>

        <div className="mt-8 pt-6 border-t border-slate-800/80 text-center">
          <p className="text-xs text-slate-500">
            Protected by ContAIned RBAC & JWT Session Security
          </p>
        </div>
      </div>
    </div>
  );
};
