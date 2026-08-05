import { useState, useEffect } from "react";
import { Routes, Route, Navigate, useLocation, useParams } from "react-router-dom";
import { AnimatePresence } from "framer-motion";

// Layout & chrome
import { Sidebar } from "./components/Sidebar";
import { HeaderBar } from "./components/layout/HeaderBar";
import { PageTransition } from "./components/layout/PageTransition";
import { CommandPalette } from "./components/layout/CommandPalette";
import { HubSwitcher } from "./components/layout/HubSwitcher";
import { ErrorBoundary, ToastProvider } from "./components/shared";

// Auth
import { LoginPage } from "./components/auth/LoginPage";
import { AuthCallback } from "./components/auth/AuthCallback";
import { AuthGuard } from "./components/auth/AuthGuard";
import { AdminGuard } from "./components/auth/AdminGuard";

// Platform surfaces (retained from V5)
import { SystemMetrics } from "./components/SystemMetrics";
import { PlaygroundPage } from "./components/PlaygroundPage";
import { MCPHubPage } from "./components/MCPHubPage";
import { InfrastructurePage } from "./components/InfrastructurePage";
import { SettingsPage } from "./components/SettingsPage";
import { NotFound } from "./components/NotFound";

// Hub shell & directory
import { HubShell } from "./components/hubs/HubShell";
import { HubDirectory } from "./components/hubs/HubDirectory";
import { HubCreate } from "./components/hubs/HubCreate";
import { HubNotFound } from "./components/hubs/HubNotFound";
import { MembersPanel } from "./components/hubs/MembersPanel";
import { HubLinksPanel } from "./components/hubs/HubLinksPanel";

// Ingestion Workspace
import { IngestionOverview } from "./components/hubs/ingestion/IngestionOverview";
import { CollectionsWorkspace } from "./components/hubs/ingestion/CollectionsWorkspace";
import { CollectionDetail } from "./components/hubs/ingestion/CollectionDetail";
import { DatastoresWorkspace } from "./components/hubs/ingestion/DatastoresWorkspace";
import { DocumentsWorkspace } from "./components/hubs/ingestion/DocumentsWorkspace";
import { JobsWorkspace } from "./components/hubs/ingestion/JobsWorkspace";

// Agent Workspace
import { AgentOverview } from "./components/hubs/agent/AgentOverview";
import { AgentLibrary } from "./components/hubs/agent/AgentLibrary";
import { AgentDetail } from "./components/hubs/agent/AgentDetail";

// Workflow Workspace
import { WorkflowHubOverview } from "./components/hubs/workflow/WorkflowHubOverview";
import { WorkflowLibrary } from "./components/hubs/workflow/WorkflowLibrary";
import { WorkflowEditor } from "./components/hubs/workflow/WorkflowEditor";
import { WorkflowRuns } from "./components/hubs/workflow/WorkflowRuns";

// Eval Workspace
import { EvalHubOverview } from "./components/hubs/eval/EvalHubOverview";
import { SuiteManager } from "./components/hubs/eval/SuiteManager";
import { EvalResultsDashboard } from "./components/hubs/eval/EvalResultsDashboard";

// Admin
import { AdminConsole } from "./components/admin/AdminConsole";

// Typed route patterns
import { ROUTE_PATTERNS, routes } from "./routes";

// Services & store
import { telemetryService } from "./services/telemetry";
import { api } from "./services/api";
import { useStore } from "./store/useStore";
import type { SystemHealthResponse, ModelRegistryResponse } from "./types/api";

export default function App() {
  const location = useLocation();
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [isHubSwitcherOpen, setIsHubSwitcherOpen] = useState(false);
  const [systemHealth, setSystemHealth] = useState<SystemHealthResponse | null>(null);
  const [modelRegistry, setModelRegistry] = useState<ModelRegistryResponse | null>(null);

  const gatewayUrl = useStore((state) => state.gatewayUrl);

  useEffect(() => {
    telemetryService.connect();
    fetchSystemData();
    const interval = setInterval(fetchSystemData, 5000);
    return () => {
      telemetryService.disconnect();
      clearInterval(interval);
    };
  }, [gatewayUrl]);

  const fetchSystemData = async () => {
    try {
      const health = await api.getSystemHealth();
      setSystemHealth(health);
    } catch (err) {
      console.warn("System health is currently unavailable:", err);
    }

    try {
      const models = await api.getModels();
      setModelRegistry(models);
    } catch (err) {
      console.warn("Offline model registry fallback:", err);
    }
  };

  // Global Keyboard Shortcuts (Cmd+K for Hub Switcher, Cmd+Shift+P for Command Palette)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const isCmdOrCtrl = e.metaKey || e.ctrlKey;
      if (isCmdOrCtrl && e.shiftKey && (e.key === "p" || e.key === "P")) {
        e.preventDefault();
        setIsHubSwitcherOpen(false);
        setIsCommandPaletteOpen((prev) => !prev);
      } else if (isCmdOrCtrl && e.key === "k") {
        e.preventDefault();
        setIsCommandPaletteOpen(false);
        setIsHubSwitcherOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Auth-only routes rendered outside the main app shell
  if (location.pathname === routes.login) {
    return <LoginPage />;
  }
  if (location.pathname === routes.authCallback) {
    return <AuthCallback />;
  }

  return (
    <ToastProvider>
      <AuthGuard>
        <div className="flex h-screen bg-[#080809] text-[var(--text-primary)] font-sans antialiased overflow-hidden">
          {/* Sidebar Navigation */}
          <Sidebar
            onOpenCommandPalette={() => setIsCommandPaletteOpen(true)}
            onOpenHubSwitcher={() => setIsHubSwitcherOpen(true)}
          />

          {/* Main Application Container */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Top Header Bar with Breadcrumbs & Actions */}
            <HeaderBar
              onOpenCommandPalette={() => setIsCommandPaletteOpen(true)}
              onOpenHubSwitcher={() => setIsHubSwitcherOpen(true)}
            />

            {/* Page Viewport */}
            <main className="flex-1 overflow-y-auto p-6 lg:p-10 pb-16 custom-scrollbar flex flex-col min-h-0">
              <ErrorBoundary>
                {/*
                 * AnimatePresence key = top-level segment so platform↔hub
                 * transitions animate. Within a hub the HubShell manages its
                 * own AnimatePresence keyed to the sub-path (tab switches).
                 */}
                <AnimatePresence mode="wait">
                  <Routes location={location} key={location.pathname.split("/").slice(0, 3).join("/")}>

                    {/* ── Root redirect ─────────────────────────────────── */}
                    <Route
                      path={ROUTE_PATTERNS.root}
                      element={<Navigate to={routes.hubs.directory()} replace />}
                    />

                    {/* ── Hub Directory & Creation ───────────────────────── */}
                    <Route
                      path={ROUTE_PATTERNS.hubDirectory}
                      element={
                        <PageTransition>
                          <HubDirectory />
                        </PageTransition>
                      }
                    />
                    <Route
                      path={ROUTE_PATTERNS.hubCreate}
                      element={
                        <PageTransition>
                          <HubCreate />
                        </PageTransition>
                      }
                    />
                    <Route
                      path={ROUTE_PATTERNS.hubNotFound}
                      element={
                        <PageTransition>
                          <HubNotFound />
                        </PageTransition>
                      }
                    />

                    {/* ── Hub Shell (layout route) ───────────────────────── */}
                    {/*
                     * HubShell fetches the hub once and injects HubContext.
                     * Child routes are relative — they resolve under /hubs/:hubType/:hubId/.
                     * HubShell renders its own AnimatePresence keyed to the sub-path.
                     */}
                    <Route
                      path={ROUTE_PATTERNS.hubShell}
                      element={<HubShell />}
                    >
                      {/* Ingestion hub child routes */}
                      <Route
                        path="collections"
                        element={<CollectionsWorkspace />}
                      />
                      <Route
                        path="collections/:collectionId"
                        element={<CollectionDetail />}
                      />
                      <Route
                        path="datastores"
                        element={<DatastoresWorkspace />}
                      />
                      <Route
                        path="documents"
                        element={<DocumentsWorkspace />}
                      />
                      <Route
                        path="jobs"
                        element={<JobsWorkspace />}
                      />
                      <Route
                        path="search"
                        element={<CollectionsWorkspace />}
                      />

                      {/* Agent hub child routes */}
                      <Route
                        path="agents"
                        element={<AgentLibrary />}
                      />
                      <Route
                        path="agents/:agentId"
                        element={<AgentDetail />}
                      />
                      <Route
                        path="agents/:agentId/playground"
                        element={<AgentDetail />}
                      />

                      {/* Workflow hub child routes */}
                      <Route
                        path="workflows"
                        element={<WorkflowLibrary />}
                      />
                      <Route
                        path="workflows/:workflowId/editor"
                        element={<WorkflowEditor />}
                      />
                      <Route
                        path="workflows/:workflowId/runs"
                        element={<WorkflowRuns />}
                      />

                      {/* Eval hub child routes */}
                      <Route
                        path="suites"
                        element={<SuiteManager />}
                      />
                      <Route
                        path="suites/:suiteId"
                        element={<EvalResultsDashboard />}
                      />
                      <Route
                        path="runs"
                        element={<EvalResultsDashboard />}
                      />
                      <Route
                        path="runs/:runId/traces"
                        element={<EvalResultsDashboard />}
                      />
                      <Route
                        path="dashboard"
                        element={<EvalResultsDashboard />}
                      />

                      {/* Cross-hub shared panels (all hub types) */}
                      <Route path="members" element={<MembersPanel />} />
                      <Route path="links" element={<HubLinksPanel />} />
                      <Route path="settings" element={<HubNotFound />} />

                      {/* Hub-level index: renders overview component for each type */}
                      <Route
                        index
                        element={<HubOverviewDispatcher />}
                      />

                      {/* Unknown segments inside a valid hub → in-shell not-found */}
                      <Route path="*" element={<HubNotFound />} />
                    </Route>

                    {/* ── Admin routes (platform-admin only) ───────────────── */}
                    <Route
                      path={ROUTE_PATTERNS.admin}
                      element={
                        <AdminGuard>
                          <AdminConsole />
                        </AdminGuard>
                      }
                    />

                    {/* ── Platform surfaces ─────────────────────────────── */}
                    <Route
                      path={ROUTE_PATTERNS.system}
                      element={
                        <PageTransition>
                          <SystemMetrics
                            systemHealth={systemHealth}
                            modelRegistry={modelRegistry}
                            onRefresh={fetchSystemData}
                          />
                        </PageTransition>
                      }
                    />
                    <Route
                      path={ROUTE_PATTERNS.playground}
                      element={
                        <PageTransition>
                          <PlaygroundPage />
                        </PageTransition>
                      }
                    />
                    <Route
                      path={ROUTE_PATTERNS.mcp}
                      element={
                        <PageTransition>
                          <MCPHubPage />
                        </PageTransition>
                      }
                    />
                    <Route
                      path={ROUTE_PATTERNS.infrastructure}
                      element={
                        <PageTransition>
                          <InfrastructurePage
                            systemHealth={systemHealth}
                            modelRegistry={modelRegistry}
                            onRefresh={fetchSystemData}
                          />
                        </PageTransition>
                      }
                    />
                    <Route
                      path={ROUTE_PATTERNS.settings}
                      element={
                        <PageTransition>
                          <SettingsPage />
                        </PageTransition>
                      }
                    />

                    {/* ── Global fallback ───────────────────────────────── */}
                    <Route
                      path="*"
                      element={
                        <PageTransition>
                          <NotFound />
                        </PageTransition>
                      }
                    />
                  </Routes>
                </AnimatePresence>
              </ErrorBoundary>
            </main>
          </div>

          {/* Global Command Palette Dialog */}
          <CommandPalette
            isOpen={isCommandPaletteOpen}
            onClose={() => setIsCommandPaletteOpen(false)}
            onOpenHubSwitcher={() => setIsHubSwitcherOpen(true)}
          />

          {/* Global Hub Switcher Dialog */}
          <HubSwitcher
            isOpen={isHubSwitcherOpen}
            onClose={() => setIsHubSwitcherOpen(false)}
          />
        </div>
      </AuthGuard>
    </ToastProvider>
  );
}

/**
 * Hub shell index dispatcher — renders the overview component for each hub type.
 */
function HubOverviewDispatcher() {
  const { hubType, hubId } = useParams<{ hubType: string; hubId: string }>();

  if (!hubType || !hubId) {
    return <Navigate to={routes.hubs.directory()} replace />;
  }

  if (hubType === "ingestion") return <IngestionOverview />;
  if (hubType === "agent") return <AgentOverview />;
  if (hubType === "workflow") return <WorkflowHubOverview />;
  if (hubType === "eval") return <EvalHubOverview />;
  
  return <Navigate to={routes.hubs.directory()} replace />;
}
