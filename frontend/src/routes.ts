/**
 * Canonical V6 route builders — single source of path truth.
 *
 * Rules:
 *  - No component or service may hard-code a path string.
 *  - Import `routes` for programmatic navigation and link building.
 *  - Import `ROUTE_PATTERNS` for <Route path=...> declarations.
 *  - Import `parseHubRoute` for breadcrumb / hub-switcher logic.
 */

export type HubType = "ingestion" | "agent" | "workflow" | "eval";

// ---------------------------------------------------------------------------
// Builder functions
// ---------------------------------------------------------------------------

export const routes = {
  root: "/",
  login: "/login",
  authCallback: "/auth/callback",

  hubs: {
    directory: () => "/hubs" as const,
    create: () => "/hubs/new" as const,
    notFound: () => "/hubs/not-found" as const,
    shell: (t: HubType, id: string) => `/hubs/${t}/${id}` as const,
    members: (t: HubType, id: string) => `/hubs/${t}/${id}/members` as const,
    links: (t: HubType, id: string) => `/hubs/${t}/${id}/links` as const,
    settings: (t: HubType, id: string) => `/hubs/${t}/${id}/settings` as const,
  },

  ingestionHub: {
    overview: (id: string) => `/hubs/ingestion/${id}` as const,
    collections: (id: string) => `/hubs/ingestion/${id}/collections` as const,
    collection: (id: string, cid: string) =>
      `/hubs/ingestion/${id}/collections/${cid}` as const,
    datastores: (id: string) => `/hubs/ingestion/${id}/datastores` as const,
    documents: (id: string) => `/hubs/ingestion/${id}/documents` as const,
    jobs: (id: string) => `/hubs/ingestion/${id}/jobs` as const,
    search: (id: string) => `/hubs/ingestion/${id}/search` as const,
  },

  agentHub: {
    overview: (id: string) => `/hubs/agent/${id}` as const,
    agents: (id: string) => `/hubs/agent/${id}/agents` as const,
    agent: (id: string, aid: string) =>
      `/hubs/agent/${id}/agents/${aid}` as const,
    playground: (id: string, aid: string) =>
      `/hubs/agent/${id}/agents/${aid}/playground` as const,
  },

  workflowHub: {
    overview: (id: string) => `/hubs/workflow/${id}` as const,
    workflows: (id: string) => `/hubs/workflow/${id}/workflows` as const,
    editor: (id: string, wid: string) =>
      `/hubs/workflow/${id}/workflows/${wid}/editor` as const,
    runs: (id: string, wid: string) =>
      `/hubs/workflow/${id}/workflows/${wid}/runs` as const,
  },

  evalHub: {
    overview: (id: string) => `/hubs/eval/${id}` as const,
    suites: (id: string) => `/hubs/eval/${id}/suites` as const,
    suite: (id: string, sid: string) =>
      `/hubs/eval/${id}/suites/${sid}` as const,
    runs: (id: string) => `/hubs/eval/${id}/runs` as const,
    traces: (id: string, runId: string) =>
      `/hubs/eval/${id}/runs/${runId}/traces` as const,
    dashboard: (id: string) => `/hubs/eval/${id}/dashboard` as const,
  },

  admin: {
    users: () => "/admin/users" as const,
    invites: () => "/admin/invites" as const,
    approvals: () => "/admin/approvals" as const,
    audit: () => "/admin/audit" as const,
  },

  platform: {
    playground: () => "/playground" as const,
    mcp: () => "/mcp" as const,
    models: () => "/models" as const,
    infrastructure: () => "/infrastructure" as const,
    system: () => "/system" as const,
    settings: () => "/settings" as const,
  },
} as const;

// ---------------------------------------------------------------------------
// React Router pattern strings (used in <Route path=...>)
// ---------------------------------------------------------------------------

export const ROUTE_PATTERNS = {
  // Root redirects
  root: "/",
  login: "/login",
  authCallback: "/auth/callback",

  // Hub directory
  hubDirectory: "/hubs",
  hubCreate: "/hubs/new",
  hubNotFound: "/hubs/not-found",

  // Hub shell layout route — matches /hubs/:hubType/:hubId and all descendants
  hubShell: "/hubs/:hubType/:hubId",

  // Cross-hub shared panels (resolved inside HubShell)
  hubMembers: "members",
  hubLinks: "links",
  hubSettings: "settings",

  // Ingestion hub child paths (relative, nested under hubShell)
  ingestionOverview: "",
  ingestionCollections: "collections",
  ingestionCollection: "collections/:collectionId",
  ingestionDatastores: "datastores",
  ingestionDocuments: "documents",
  ingestionJobs: "jobs",
  ingestionSearch: "search",

  // Agent hub child paths
  agentOverview: "",
  agentAgents: "agents",
  agentDetail: "agents/:agentId",
  agentPlayground: "agents/:agentId/playground",

  // Workflow hub child paths
  workflowOverview: "",
  workflowWorkflows: "workflows",
  workflowEditor: "workflows/:workflowId/editor",
  workflowRuns: "workflows/:workflowId/runs",

  // Eval hub child paths
  evalOverview: "",
  evalSuites: "suites",
  evalSuite: "suites/:suiteId",
  evalRuns: "runs",
  evalTraces: "runs/:runId/traces",
  evalDashboard: "dashboard",

  // Admin routes
  admin: "/admin/*",
  adminUsers: "/admin/users",
  adminInvites: "/admin/invites",
  adminApprovals: "/admin/approvals",
  adminAudit: "/admin/audit",

  // Platform routes
  system: "/system",
  playground: "/playground",
  mcp: "/mcp",
  models: "/models",
  infrastructure: "/infrastructure",
  settings: "/settings",
} as const;

// ---------------------------------------------------------------------------
// Hub route parser — used by breadcrumbs and hub-switcher "recents" logic
// ---------------------------------------------------------------------------

export interface ParsedHubRoute {
  hubType: HubType;
  hubId: string;
  /** The remainder of the path after /:hubId, e.g. "collections/abc" */
  subPath: string;
}

const HUB_TYPES: ReadonlySet<string> = new Set([
  "ingestion",
  "agent",
  "workflow",
  "eval",
]);

/**
 * Parses a pathname and returns hub routing metadata, or null when the path
 * does not match the hub shell pattern.
 *
 * @example
 * parseHubRoute("/hubs/ingestion/hub-123/collections/col-456")
 * // → { hubType: "ingestion", hubId: "hub-123", subPath: "collections/col-456" }
 */
export function parseHubRoute(pathname: string): ParsedHubRoute | null {
  // Strip trailing slash for consistency
  const clean = pathname.replace(/\/$/, "");
  const parts = clean.split("/");
  // Expected: ["", "hubs", hubType, hubId, ...rest]
  if (parts.length < 4 || parts[1] !== "hubs") return null;
  const hubType = parts[2];
  const hubId = parts[3];
  if (!hubType || !hubId || !HUB_TYPES.has(hubType)) return null;
  const subPath = parts.slice(4).join("/");
  return { hubType: hubType as HubType, hubId, subPath };
}
