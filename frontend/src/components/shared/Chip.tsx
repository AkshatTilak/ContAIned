import React from "react";

export type ChipVariant = "status" | "hub" | "tag" | "count";

export interface ChipProps {
  label: React.ReactNode;
  variant?: ChipVariant;
  colorKey?: string; // e.g. "active", "pending", "ingestion", "cyan", etc.
  icon?: React.ReactNode;
  size?: "sm" | "md";
  className?: string;
}

export const Chip: React.FC<ChipProps> = ({
  label,
  variant = "status",
  colorKey = "active",
  icon,
  size = "md",
  className = "",
}) => {
  const sizeClasses = size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-medium border transition-all ${sizeClasses} ${className}`}
      style={{
        backgroundColor: `var(--status-${colorKey}-soft, var(--hub-${colorKey}-soft, rgba(99, 102, 241, 0.12)))`,
        color: `var(--status-${colorKey}-fg, var(--hub-${colorKey}, var(--accent-indigo)))`,
        borderColor: `var(--status-${colorKey}-soft, var(--hub-${colorKey}-glow, rgba(99, 102, 241, 0.25)))`,
      }}
    >
      {icon && <span className="w-3 h-3 flex items-center justify-center">{icon}</span>}
      <span className="capitalize">{label}</span>
    </span>
  );
};
