import React from "react";
import { useStore } from "../../store/useStore";
import { ShieldAlert } from "lucide-react";

interface RoleGuardProps {
  roles: string[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export const RoleGuard: React.FC<RoleGuardProps> = ({
  roles,
  children,
  fallback,
}) => {
  const isAuthEnabled = useStore((state) => state.isAuthEnabled);
  const user = useStore((state) => state.user);

  if (!isAuthEnabled) {
    return <>{children}</>;
  }

  const userRole = user?.role || "viewer";

  const hasAccess =
    userRole === "admin" || roles.includes(userRole);

  if (!hasAccess) {
    if (fallback) return <>{fallback}</>;
    return (
      <div className="p-8 my-6 bg-slate-900/60 border border-amber-900/40 rounded-xl text-center flex flex-col items-center">
        <ShieldAlert className="w-12 h-12 text-amber-500 mb-3" />
        <h3 className="text-lg font-semibold text-slate-200">
          Access Restricted
        </h3>
        <p className="text-sm text-slate-400 max-w-md mt-1">
          Your role (<span className="text-amber-400 font-mono">{userRole}</span>)
          does not have permission to view or execute this action. Required role:{" "}
          <span className="font-mono text-slate-300">{roles.join(" or ")}</span>.
        </p>
      </div>
    );
  }

  return <>{children}</>;
};
