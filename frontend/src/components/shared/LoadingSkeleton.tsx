import React from 'react';

interface LoadingSkeletonProps {
  variant?: 'card' | 'row' | 'text' | 'gauge' | 'chart';
  count?: number;
  height?: string;
  className?: string;
}

export const LoadingSkeleton: React.FC<LoadingSkeletonProps> = ({
  variant = 'card',
  count = 1,
  height,
  className = '',
}) => {
  const items = Array.from({ length: count });

  const renderSkeleton = (index: number) => {
    switch (variant) {
      case 'row':
        return (
          <div
            key={index}
            className={`w-full h-12 rounded-lg bg-[var(--bg-surface-alt)] border border-[var(--border-subtle)] animate-pulse p-3 flex items-center justify-between ${className}`}
          >
            <div className="h-4 bg-[var(--bg-elevated)] rounded w-1/4" />
            <div className="h-4 bg-[var(--bg-elevated)] rounded w-1/3" />
            <div className="h-4 bg-[var(--bg-elevated)] rounded w-1/6" />
          </div>
        );

      case 'gauge':
        return (
          <div
            key={index}
            className={`p-5 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-default)] animate-pulse flex flex-col items-center justify-center min-h-[160px] ${className}`}
          >
            <div className="w-20 h-20 rounded-full border-4 border-[var(--bg-elevated)] border-t-[var(--accent-indigo)] animate-spin" />
            <div className="h-3 bg-[var(--bg-elevated)] rounded w-20 mt-3" />
          </div>
        );

      case 'chart':
        return (
          <div
            key={index}
            className={`p-5 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-default)] animate-pulse flex flex-col gap-3 min-h-[220px] ${className}`}
          >
            <div className="h-4 bg-[var(--bg-elevated)] rounded w-1/3" />
            <div className="flex-1 w-full bg-[var(--bg-elevated)] rounded-lg flex items-end p-3 gap-2">
              <div className="w-1/6 bg-[var(--bg-surface-alt)] rounded-t h-1/2" />
              <div className="w-1/6 bg-[var(--bg-surface-alt)] rounded-t h-3/4" />
              <div className="w-1/6 bg-[var(--bg-surface-alt)] rounded-t h-2/3" />
              <div className="w-1/6 bg-[var(--bg-surface-alt)] rounded-t h-5/6" />
              <div className="w-1/6 bg-[var(--bg-surface-alt)] rounded-t h-1/3" />
              <div className="w-1/6 bg-[var(--bg-surface-alt)] rounded-t h-4/5" />
            </div>
          </div>
        );

      case 'text':
        return (
          <div
            key={index}
            className={`h-4 bg-[var(--bg-elevated)] rounded animate-pulse ${className}`}
            style={{ height: height || '1rem' }}
          />
        );

      case 'card':
      default:
        return (
          <div
            key={index}
            className={`p-5 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-default)] animate-pulse space-y-3 ${className}`}
            style={{ height: height || 'auto' }}
          >
            <div className="flex justify-between items-center">
              <div className="h-4 bg-[var(--bg-elevated)] rounded w-1/3" />
              <div className="h-6 w-16 bg-[var(--bg-elevated)] rounded-full" />
            </div>
            <div className="h-8 bg-[var(--bg-elevated)] rounded w-1/2" />
            <div className="h-3 bg-[var(--bg-elevated)] rounded w-3/4" />
          </div>
        );
    }
  };

  return <div className="space-y-3 w-full">{items.map((_, i) => renderSkeleton(i))}</div>;
};

export default LoadingSkeleton;
