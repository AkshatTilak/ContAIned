import React, { type ReactNode } from "react";
import { useHubPermissions } from "../../hooks/useHubPermissions";
import type { HubAction } from "./HubContext";

export interface GatedProps {
  action: HubAction;
  children: ReactNode;
  fallback?: ReactNode;
  /** If true, renders a disabled wrapper with a tooltip when denied due to archiving. */
  showDisabledWhenArchived?: boolean;
}

export function Gated({
  action,
  children,
  fallback = null,
  showDisabledWhenArchived = true,
}: GatedProps) {
  const { can, denyReason } = useHubPermissions();

  if (can(action)) {
    return <>{children}</>;
  }

  const reason = denyReason(action);

  if (reason === "archived" && showDisabledWhenArchived) {
    return (
      <div
        className="gated-archived-wrapper inline-block cursor-not-allowed opacity-60"
        title="This hub is archived and is read-only"
        aria-disabled="true"
      >
        <div className="pointer-events-none">{children}</div>
      </div>
    );
  }

  // Denied due to role or unhandled -> don't render (or render fallback)
  return <>{fallback}</>;
}
