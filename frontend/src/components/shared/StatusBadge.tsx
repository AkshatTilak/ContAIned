import React from 'react';

export type StatusVariant = 'success' | 'warning' | 'error' | 'info' | 'neutral';

interface StatusBadgeProps {
  variant?: StatusVariant;
  label: string;
  dot?: boolean;
  size?: 'sm' | 'md';
  className?: string;
}

const variantStyles: Record<StatusVariant, { bg: string; color: string; border: string; dotColor: string }> = {
  success: {
    bg: 'var(--emerald-soft)',
    color: 'var(--accent-emerald)',
    border: 'rgba(16, 185, 129, 0.2)',
    dotColor: 'var(--accent-emerald)',
  },
  warning: {
    bg: 'var(--amber-soft)',
    color: 'var(--accent-amber)',
    border: 'rgba(245, 158, 11, 0.2)',
    dotColor: 'var(--accent-amber)',
  },
  error: {
    bg: 'var(--rose-soft)',
    color: 'var(--accent-rose)',
    border: 'rgba(239, 68, 68, 0.2)',
    dotColor: 'var(--accent-rose)',
  },
  info: {
    bg: 'var(--cyan-soft)',
    color: 'var(--accent-cyan)',
    border: 'rgba(6, 182, 212, 0.2)',
    dotColor: 'var(--accent-cyan)',
  },
  neutral: {
    bg: 'var(--indigo-soft)',
    color: 'var(--text-secondary)',
    border: 'var(--border-default)',
    dotColor: 'var(--text-muted)',
  },
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  variant = 'neutral',
  label,
  dot = true,
  size = 'md',
  className = '',
}) => {
  const style = variantStyles[variant] || variantStyles.neutral;
  const isSm = size === 'sm';

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium rounded-full whitespace-nowrap ${
        isSm ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs'
      } ${className}`}
      style={{
        backgroundColor: style.bg,
        color: style.color,
        border: `1px solid ${style.border}`,
      }}
    >
      {dot && (
        <span
          className="w-1.5 h-1.5 rounded-full inline-block animate-pulse"
          style={{ backgroundColor: style.dotColor }}
        />
      )}
      {label}
    </span>
  );
};

export default StatusBadge;
