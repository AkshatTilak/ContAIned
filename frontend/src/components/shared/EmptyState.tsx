import React from 'react';
import { Inbox } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon: Icon = Inbox,
  title,
  description,
  actionLabel,
  onAction,
  className = '',
}) => {
  return (
    <div
      className={`flex flex-col items-center justify-center p-8 text-center rounded-2xl border border-dashed border-[var(--border-default)] bg-[var(--bg-card)] ${className}`}
    >
      <div className="p-4 rounded-2xl bg-[var(--indigo-soft)] text-[var(--accent-indigo)] mb-4">
        <Icon className="w-8 h-8" />
      </div>
      <h3 className="text-base font-semibold text-[var(--text-primary)] font-display">
        {title}
      </h3>
      <p className="text-xs text-[var(--text-secondary)] mt-1 max-w-sm leading-relaxed">
        {description}
      </p>
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          className="mt-5 px-4 py-2 text-xs font-semibold rounded-lg bg-[var(--accent-indigo)] text-white hover:opacity-90 transition-all shadow-md"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
};

export default EmptyState;
