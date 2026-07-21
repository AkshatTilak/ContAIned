import { useState, useEffect } from "react";
import { Sidebar } from "./components/Sidebar";
import { SystemMetrics } from "./components/SystemMetrics";
import { IngestionPanel } from "./components/IngestionPanel";
import { WorkflowCanvas } from "./components/WorkflowCanvas";
import { AgentHub } from "./components/AgentHub";
import { EvalPanel } from "./components/EvalPanel";
import { ErrorBoundary, ToastProvider } from "./components/shared";

import { telemetryService } from "./services/telemetry";
import { api } from "./services/api";
import { useStore } from "./store/useStore";
import type { SystemHealthResponse, ModelRegistryResponse } from "./types/api";

export default function App() {
  const [activeTab, setActiveTab] = useState<"system" | "syntraflow" | "guardroute" | "agent_hub" | "evalops">("system");
  const [showConfig, setShowConfig] = useState(false);
  const [systemHealth, setSystemHealth] = useState<SystemHealthResponse | null>(null);
  const [modelRegistry, setModelRegistry] = useState<ModelRegistryResponse | null>(null);

  // Settings from Zustand store
  const gatewayUrl = useStore((state) => state.gatewayUrl);
  const apiKey = useStore((state) => state.apiKey);
  const updateSettings = useStore((state) => state.updateSettings);
  const resetSettings = useStore((state) => state.resetSettings);

  // Controlled modal inputs
  const [inputGatewayUrl, setInputGatewayUrl] = useState(gatewayUrl);
  const [inputApiKey, setInputApiKey] = useState(apiKey);

  useEffect(() => {
    setInputGatewayUrl(gatewayUrl);
    setInputApiKey(apiKey);
  }, [gatewayUrl, apiKey]);

  useEffect(() => {
    telemetryService.connect();
    fetchSystemData();
    return () => {
      telemetryService.disconnect();
    };
  }, [gatewayUrl]);

  const fetchSystemData = async () => {
    try {
      const health = await api.getSystemHealth();
      setSystemHealth(health);
      const models = await api.getModels();
      setModelRegistry(models);
    } catch (err) {
      console.warn("Using offline fallback system data:", err);
    }
  };

  const handleSaveConfig = () => {
    updateSettings({ gatewayUrl: inputGatewayUrl, apiKey: inputApiKey });
    setShowConfig(false);
    telemetryService.disconnect();
    telemetryService.connect();
    fetchSystemData();
  };

  const handleResetDefaults = () => {
    resetSettings();
    const defaults = useStore.getState();
    setInputGatewayUrl(defaults.gatewayUrl);
    setInputApiKey(defaults.apiKey);
  };

  return (
    <ToastProvider>
      <div className="flex h-screen bg-[#080809] text-[var(--text-primary)] font-sans antialiased overflow-hidden">
        {/* Sidebar Navigation */}
        <Sidebar
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          onOpenConfig={() => setShowConfig(true)}
        />

        {/* Main Content Area */}
        <main className="flex-1 flex flex-col overflow-y-auto p-6">
          <ErrorBoundary>
            {activeTab === "system" && (
              <SystemMetrics systemHealth={systemHealth} modelRegistry={modelRegistry} />
            )}

            {activeTab === "syntraflow" && <IngestionPanel />}

            {activeTab === "guardroute" && <WorkflowCanvas />}

            {activeTab === "agent_hub" && <AgentHub />}

            {activeTab === "evalops" && <EvalPanel />}
          </ErrorBoundary>
        </main>

        {/* Config Modal */}
        {showConfig && (
          <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-md flex items-center justify-center p-4">
            <div className="w-full max-w-md bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-xl p-6 shadow-2xl space-y-4">
              <h3 className="text-sm font-bold text-[var(--text-primary)] font-display">
                Gateway & Environment Settings
              </h3>
              <div className="space-y-3 text-xs">
                <div>
                  <label className="text-[var(--text-secondary)] block mb-1">Gateway API Base URL</label>
                  <input
                    type="text"
                    value={inputGatewayUrl}
                    onChange={(e) => setInputGatewayUrl(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-[var(--bg-input)] border border-[var(--border-default)] text-[var(--text-primary)] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-[var(--text-secondary)] block mb-1">X-API-Key Authorization</label>
                  <input
                    type="text"
                    value={inputApiKey}
                    onChange={(e) => setInputApiKey(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-[var(--bg-input)] border border-[var(--border-default)] text-[var(--text-primary)] focus:outline-none"
                  />
                </div>
              </div>
              <div className="flex justify-between items-center pt-2">
                <button
                  type="button"
                  onClick={handleResetDefaults}
                  className="px-3 py-1.5 rounded-lg bg-[var(--bg-elevated)] hover:bg-[var(--bg-surface-alt)] text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                >
                  Reset to Defaults
                </button>
                <div className="flex space-x-2">
                  <button
                    type="button"
                    onClick={() => setShowConfig(false)}
                    className="px-3 py-1.5 rounded-lg bg-[var(--bg-elevated)] hover:bg-[var(--bg-surface-alt)] text-xs text-[var(--text-secondary)]"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleSaveConfig}
                    className="px-4 py-1.5 rounded-lg bg-[var(--accent-indigo)] hover:opacity-90 text-xs font-medium text-white shadow-md"
                  >
                    Save & Close
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </ToastProvider>
  );
}
