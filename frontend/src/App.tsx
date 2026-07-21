import { useState, useEffect } from "react";
import { Sidebar } from "./components/Sidebar";
import { SystemMetrics } from "./components/SystemMetrics";
import { IngestionPanel } from "./components/IngestionPanel";
import { WorkflowCanvas } from "./components/WorkflowCanvas";
import { AgentHub } from "./components/AgentHub";
import { EvalPanel } from "./components/EvalPanel";

import { telemetryService } from "./services/telemetry";
import { api } from "./services/api";

export default function App() {
  const [activeTab, setActiveTab] = useState<"system" | "syntraflow" | "guardroute" | "agent_hub" | "evalops">("system");
  const [showConfig, setShowConfig] = useState(false);
  const [systemHealth, setSystemHealth] = useState<any>(null);
  const [modelRegistry, setModelRegistry] = useState<any>(null);

  useEffect(() => {
    telemetryService.connect();
    fetchSystemData();
    return () => {
      telemetryService.disconnect();
    };
  }, []);

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

  return (
    <div className="flex h-screen bg-[#0d0e12] text-zinc-100 font-sans antialiased overflow-hidden">
      {/* Sidebar Navigation */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onOpenConfig={() => setShowConfig(true)}
      />

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col overflow-y-auto p-6">
        {activeTab === "system" && (
          <SystemMetrics systemHealth={systemHealth} modelRegistry={modelRegistry} />
        )}

        {activeTab === "syntraflow" && <IngestionPanel />}

        {activeTab === "guardroute" && <WorkflowCanvas />}

        {activeTab === "agent_hub" && <AgentHub />}

        {activeTab === "evalops" && <EvalPanel />}
      </main>

      {/* Config Modal */}
      {showConfig && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-[#15171e] border border-[#26282d] rounded-xl p-6 shadow-2xl space-y-4">
            <h3 className="text-sm font-bold text-white">Gateway & Environment Settings</h3>
            <div className="space-y-3 text-xs">
              <div>
                <label className="text-zinc-400 block mb-1">Gateway API Base URL</label>
                <input
                  type="text"
                  defaultValue="http://localhost:8000"
                  className="w-full px-3 py-2 rounded bg-[#121316] border border-[#2d3039] text-white"
                />
              </div>
              <div>
                <label className="text-zinc-400 block mb-1">X-API-Key Authorization</label>
                <input
                  type="text"
                  defaultValue="sk_live_default_key"
                  className="w-full px-3 py-2 rounded bg-[#121316] border border-[#2d3039] text-white"
                />
              </div>
            </div>
            <div className="flex justify-end pt-2">
              <button
                onClick={() => setShowConfig(false)}
                className="px-4 py-2 rounded bg-emerald-500 hover:bg-emerald-600 text-xs font-medium text-white"
              >
                Save & Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
