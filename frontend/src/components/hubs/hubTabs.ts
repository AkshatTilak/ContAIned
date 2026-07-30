import type { HubType } from "../../routes";

export interface HubTabConfig {
  id: string;
  label: string;
  pathSuffix: string; // relative to /hubs/:hubType/:hubId/
  iconName: string;
}

export const WORKSPACE_TABS: Record<HubType, HubTabConfig[]> = {
  ingestion: [
    { id: "overview", label: "Overview", pathSuffix: "", iconName: "LayoutDashboard" },
    { id: "collections", label: "Collections", pathSuffix: "collections", iconName: "FolderKanban" },
    { id: "datastores", label: "Datastores", pathSuffix: "datastores", iconName: "Database" },
    { id: "documents", label: "Documents", pathSuffix: "documents", iconName: "FileText" },
    { id: "jobs", label: "Jobs", pathSuffix: "jobs", iconName: "Activity" },
    { id: "search", label: "Search", pathSuffix: "search", iconName: "Search" },
  ],
  agent: [
    { id: "overview", label: "Overview", pathSuffix: "", iconName: "LayoutDashboard" },
    { id: "agents", label: "Agents", pathSuffix: "agents", iconName: "Bot" },
  ],
  workflow: [
    { id: "overview", label: "Overview", pathSuffix: "", iconName: "LayoutDashboard" },
    { id: "workflows", label: "Workflows", pathSuffix: "workflows", iconName: "GitFork" },
  ],
  eval: [
    { id: "overview", label: "Overview", pathSuffix: "", iconName: "LayoutDashboard" },
    { id: "suites", label: "Suites", pathSuffix: "suites", iconName: "CheckSquare" },
    { id: "runs", label: "Runs", pathSuffix: "runs", iconName: "Play" },
    { id: "dashboard", label: "Dashboard", pathSuffix: "dashboard", iconName: "BarChart3" },
  ],
};

export const SHARED_TABS: HubTabConfig[] = [
  { id: "members", label: "Members", pathSuffix: "members", iconName: "Users" },
  { id: "links", label: "Links", pathSuffix: "links", iconName: "Link2" },
  { id: "settings", label: "Settings", pathSuffix: "settings", iconName: "Settings" },
];
