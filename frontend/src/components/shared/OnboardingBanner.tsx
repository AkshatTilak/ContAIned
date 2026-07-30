import React, { useState } from "react";
import { Sparkles, X, ArrowRight } from "lucide-react";

export interface OnboardingBannerProps {
  id: string;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}

export const OnboardingBanner: React.FC<OnboardingBannerProps> = ({
  id,
  title,
  description,
  actionLabel,
  onAction,
}) => {
  const storageKey = `contained-onboarding-dismissed-${id}`;
  const [dismissed, setDismissed] = useState(() => {
    return localStorage.getItem(storageKey) === "true";
  });

  if (dismissed) return null;

  const handleDismiss = () => {
    setDismissed(true);
    localStorage.setItem(storageKey, "true");
  };

  return (
    <div className="relative flex items-start justify-between gap-4 p-4 rounded-xl bg-gradient-to-r from-indigo-950/60 via-purple-950/40 to-slate-900/60 border border-indigo-500/30 text-xs shadow-md animate-fadeIn">
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-lg bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 shrink-0">
          <Sparkles className="w-4 h-4" />
        </div>
        <div className="space-y-1">
          <h4 className="font-bold text-[var(--text-primary)] font-display">{title}</h4>
          <p className="text-[var(--text-muted)] leading-relaxed">{description}</p>
          {actionLabel && onAction && (
            <button
              onClick={onAction}
              className="inline-flex items-center gap-1 mt-2 text-indigo-400 hover:text-indigo-300 font-semibold text-[11px]"
            >
              <span>{actionLabel}</span>
              <ArrowRight className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>
      <button
        onClick={handleDismiss}
        className="p-1 rounded text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-white/10 shrink-0 transition-colors"
        title="Dismiss guidance"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
};
