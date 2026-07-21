import React from "react";
import { useLocation, Link } from "react-router-dom";
import { ChevronRight, Home } from "lucide-react";

interface RouteInfo {
  category: string;
  title: string;
}

const routeMap: Record<string, RouteInfo> = {
  "/system": { category: "Dashboard", title: "System Metrics & Health" },
  "/ingestion": { category: "Data Layer", title: "SyntraFlow Ingestion Pipeline" },
  "/workflow": { category: "Orchestration", title: "GuardRoute Visual Canvas" },
  "/agents": { category: "Agents", title: "Agent Hub Management" },
  "/evalops": { category: "Evaluation", title: "EvalOps Benchmarking" },
  "/settings": { category: "System", title: "Gateway & Environment Settings" },
};

export const Breadcrumbs: React.FC = () => {
  const location = useLocation();
  const currentRoute = routeMap[location.pathname] || {
    category: "Navigation",
    title: "Page Not Found",
  };

  return (
    <nav aria-label="Breadcrumbs" className="flex items-center gap-2 text-xs font-medium">
      <Link
        to="/system"
        className="flex items-center gap-1.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
      >
        <Home className="w-3.5 h-3.5" />
        <span>ContAI ned</span>
      </Link>
      <ChevronRight className="w-3.5 h-3.5 text-[var(--text-muted)] opacity-60" />
      <span className="text-[var(--text-muted)]">{currentRoute.category}</span>
      <ChevronRight className="w-3.5 h-3.5 text-[var(--text-muted)] opacity-60" />
      <span className="text-[var(--text-primary)] font-semibold font-display">
        {currentRoute.title}
      </span>
    </nav>
  );
};
