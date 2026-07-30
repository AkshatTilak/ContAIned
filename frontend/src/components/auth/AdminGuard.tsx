/**
 * AdminGuard — gates /admin/* routes to platform admins only.
 *
 * Non-admins see a read-only forbidden state rather than a silent unmount.
 * Admin status is read from the store; the guard never makes an API call.
 */
import React from "react";
import { useStore } from "../../store/useStore";

interface AdminGuardProps {
  children: React.ReactNode;
}

export function AdminGuard({ children }: AdminGuardProps) {
  const isPlatformAdmin = useStore(
    (s) => ((s as unknown) as Record<string, unknown>).isPlatformAdmin as boolean | undefined
  );

  if (!isPlatformAdmin) {
    return (
      <div className="admin-guard-forbidden" role="alert">
        <h2>Access Denied</h2>
        <p>This area is restricted to platform administrators.</p>
      </div>
    );
  }

  return <>{children}</>;
}
