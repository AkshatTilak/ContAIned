import React from "react";
import { useLocation, Link } from "react-router-dom";
import { ChevronRight, Home } from "lucide-react";
import { parseHubRoute, routes } from "../../routes";
import { useStore } from "../../store/useStore";

interface RouteInfo {
  category: string;
  title: string;
}

const platformRouteMap: Record<string, RouteInfo> = {
  "/system": { category: "Dashboard", title: "System Metrics & Health" },
  "/playground": { category: "Playground", title: "Model Playground" },
  "/mcp": { category: "Integrations", title: "MCP Registry" },
  "/infrastructure": { category: "Infrastructure", title: "Infrastructure & Telemetry" },
  "/settings": { category: "System", title: "Gateway & Settings" },
  "/hubs": { category: "Hubs", title: "Hub Directory" },
  "/hubs/new": { category: "Hubs", title: "Create Hub" },
};

export const Breadcrumbs: React.FC = () => {
  const location = useLocation();
  const parsedHub = parseHubRoute(location.pathname);
  const hubsById = useStore((state) => state.hubsById);

  if (parsedHub) {
    const hub = hubsById[parsedHub.hubId];
    const hubTypeName = parsedHub.hubType.charAt(0).toUpperCase() + parsedHub.hubType.slice(1) + " Hub";
    const hubName = hub?.name || parsedHub.hubId;

    const subPathSegment = parsedHub.subPath
      ? parsedHub.subPath.split("/")[0].replace(/-/g, " ")
      : "Overview";
    const formattedTab = subPathSegment.charAt(0).toUpperCase() + subPathSegment.slice(1);

    return (
      <nav aria-label="Breadcrumbs" className="flex items-center gap-2 text-xs font-medium">
        <Link
          to={routes.hubs.directory()}
          className="flex items-center gap-1.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
        >
          <Home className="w-3.5 h-3.5" />
          <span>Hubs</span>
        </Link>
        <ChevronRight className="w-3.5 h-3.5 text-[var(--text-muted)] opacity-60" />
        <span className="text-[var(--text-muted)]">{hubTypeName}</span>
        <ChevronRight className="w-3.5 h-3.5 text-[var(--text-muted)] opacity-60" />
        <Link
          to={`/hubs/${parsedHub.hubType}/${parsedHub.hubId}`}
          className="text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors font-medium"
        >
          {hubName}
        </Link>
        <ChevronRight className="w-3.5 h-3.5 text-[var(--text-muted)] opacity-60" />
        <span className="text-[var(--text-primary)] font-semibold font-display">
          {formattedTab}
        </span>
      </nav>
    );
  }

  const currentRoute = platformRouteMap[location.pathname] || {
    category: "Navigation",
    title: "Platform",
  };

  return (
    <nav aria-label="Breadcrumbs" className="flex items-center gap-2 text-xs font-medium">
      <Link
        to={routes.hubs.directory()}
        className="flex items-center gap-1.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
      >
        <Home className="w-3.5 h-3.5" />
        <span>ContAIned</span>
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
