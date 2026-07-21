import { useState, useEffect } from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { AnimatePresence } from "framer-motion";
import { Sidebar } from "./components/Sidebar";
import { HeaderBar } from "./components/layout/HeaderBar";
import { PageTransition } from "./components/layout/PageTransition";
import { CommandPalette } from "./components/layout/CommandPalette";
import { SystemMetrics } from "./components/SystemMetrics";
import { IngestionPanel } from "./components/IngestionPanel";
import { WorkflowCanvas } from "./components/WorkflowCanvas";
import { AgentHub } from "./components/AgentHub";
import { EvalPanel } from "./components/EvalPanel";
import { SettingsPage } from "./components/SettingsPage";
import { NotFound } from "./components/NotFound";
import { ErrorBoundary, ToastProvider } from "./components/shared";

import { telemetryService } from "./services/telemetry";
import { api } from "./services/api";
import { useStore } from "./store/useStore";
import type { SystemHealthResponse, ModelRegistryResponse } from "./types/api";

const FALLBACK_SYSTEM_HEALTH: SystemHealthResponse = {
  status: "offline",
  platform_version: "v3.0.0",
  environment: "offline-mode",
  active_projects: ["syntraflow", "guardroute", "evalops"],
  services: {
    gateway: "offline",
    inference_server: "offline",
    database: "offline",
    redis: "offline",
    neo4j: "offline",
    qdrant: "offline",
    kafka: "offline",
  },
};

export default function App() {
  const location = useLocation();
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
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
      console.warn("Using offline fallback system data:", err);
      setSystemHealth((prev) => (prev?.status === "healthy" ? prev : FALLBACK_SYSTEM_HEALTH));
    }

    try {
      const models = await api.getModels();
      setModelRegistry(models);
    } catch (err) {
      console.warn("Offline model registry fallback:", err);
    }
  };

  // Global Ctrl+K / Cmd+K listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setIsCommandPaletteOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <ToastProvider>
      <div className="flex h-screen bg-[#080809] text-[var(--text-primary)] font-sans antialiased overflow-hidden">
        {/* Sidebar Navigation */}
        <Sidebar />

        {/* Main Application Container */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Top Header Bar with Breadcrumbs & Actions */}
          <HeaderBar onOpenCommandPalette={() => setIsCommandPaletteOpen(true)} />

          {/* Page Viewport */}
          <main className="flex-1 overflow-y-auto p-6 lg:p-10 pb-16 custom-scrollbar flex flex-col min-h-0">
            <ErrorBoundary>
              <AnimatePresence mode="wait">
                <Routes location={location} key={location.pathname}>
                  <Route path="/" element={<Navigate to="/system" replace />} />
                  <Route
                    path="/system"
                    element={
                      <PageTransition>
                        <SystemMetrics systemHealth={systemHealth} modelRegistry={modelRegistry} onRefresh={fetchSystemData} />
                      </PageTransition>
                    }
                  />
                  <Route
                    path="/ingestion"
                    element={
                      <PageTransition>
                        <IngestionPanel />
                      </PageTransition>
                    }
                  />
                  <Route
                    path="/workflow"
                    element={
                      <PageTransition>
                        <WorkflowCanvas />
                      </PageTransition>
                    }
                  />
                  <Route
                    path="/agents"
                    element={
                      <PageTransition>
                        <AgentHub />
                      </PageTransition>
                    }
                  />
                  <Route
                    path="/evalops"
                    element={
                      <PageTransition>
                        <EvalPanel />
                      </PageTransition>
                    }
                  />
                  <Route
                    path="/settings"
                    element={
                      <PageTransition>
                        <SettingsPage />
                      </PageTransition>
                    }
                  />
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
        />
      </div>
    </ToastProvider>
  );
}
