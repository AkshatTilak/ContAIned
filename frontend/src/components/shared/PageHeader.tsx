import React from "react";

export interface PageHeaderProps {
  title: string;
  description?: string | React.ReactNode;
  icon?: React.ReactNode;
  breadcrumbs?: React.ReactNode;
  badges?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  description,
  icon,
  breadcrumbs,
  badges,
  actions,
  className = "",
}) => {
  return (
    <div className={`flex flex-col gap-4 bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-xl p-6 shadow-sm ${className}`}>
      {breadcrumbs && <div className="text-xs text-[var(--text-muted)]">{breadcrumbs}</div>}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          {icon && (
            <div className="p-3 rounded-xl bg-gradient-to-tr from-indigo-500/20 to-emerald-500/20 border border-indigo-500/30 text-indigo-400">
              {icon}
            </div>
          )}
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-bold font-display text-[var(--text-primary)] tracking-tight">
                {title}
              </h1>
              {badges && <div className="flex items-center gap-2">{badges}</div>}
            </div>
            {description && (
              <p className="text-xs text-[var(--text-muted)] max-w-3xl leading-relaxed">
                {description}
              </p>
            )}
          </div>
        </div>
        {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
      </div>
    </div>
  );
};
