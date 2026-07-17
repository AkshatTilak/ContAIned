import React, { useState, useEffect, useRef } from "react";
import {
  Server,
  Activity,
  Cpu,
  Layers,
  Database,
  MessageSquare,
  Search,
  Settings,
  UploadCloud,
  Video,
  Play,
  AlertTriangle,
  RefreshCw,
  ExternalLink,
  TrendingUp,
  ShieldCheck,
  Zap,
  Terminal,
  Info,
} from "lucide-react";
import {
  ReactFlow,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

// Default Gateway API Base URL
const DEFAULT_API_URL = "http://localhost:8000";

export default function App() {
  // Navigation & Configuration States
  const [activeTab, setActiveTab] = useState<"system" | "syntraflow" | "guardroute" | "evalops">("system");
  const [demoMode, setDemoMode] = useState<boolean>(true);
  const [apiKey, setApiKey] = useState<string>("sk_live_default_key");
  const [apiUrl, setApiUrl] = useState<string>(DEFAULT_API_URL);
  const [showConfig, setShowConfig] = useState<boolean>(false);

  // System status and Model registry data
  const [systemHealth, setSystemHealth] = useState<any>({
    status: "healthy",
    environment: "development",
    active_projects: ["syntraflow", "guardroute", "evalops"],
    services: {
      gateway: "connected",
      inference_server: "connected",
      database: "connected",
      redis: "connected",
      neo4j: "connected",
      qdrant: "connected",
      kafka: "connected",
    },
    inference_details: {
      loaded_models: ["FunAudioLLM/SenseVoiceSmall", "Arch-Router-1.5B"],
      vram_used_mb: 2250,
      vram_budget_mb: 16000,
      device: "cuda",
    },
  });

  const [modelRegistry, setModelRegistry] = useState<any>({
    ocr: {
      active: { model_id: "THUDM/GLM-OCR", display_name: "GLM-OCR", mode: "local", provider: "huggingface", vram_mb: 2000 },
      available: [
        { model_id: "THUDM/GLM-OCR", display_name: "GLM-OCR (0.9B)", mode: "local", provider: "huggingface", vram_mb: 2000 },
        { model_id: "surya-ocr", display_name: "Surya OCR 2", mode: "local", provider: "pip", vram_mb: 4000 },
        { model_id: "paddleocr", display_name: "PaddleOCR-VL", mode: "local", provider: "paddleocr", vram_mb: 3000 },
        { model_id: "gemini/gemini-3.5-flash", display_name: "Gemini 3.5 Flash (Vision)", mode: "cloud", provider: "gemini" },
      ],
    },
    asr: {
      active: { model_id: "FunAudioLLM/SenseVoiceSmall", display_name: "SenseVoice-Small", mode: "local", provider: "funasr", vram_mb: 250 },
      available: [
        { model_id: "FunAudioLLM/SenseVoiceSmall", display_name: "SenseVoice-Small", mode: "local", provider: "funasr", vram_mb: 250 },
        { model_id: "openai/whisper-large-v3-turbo", display_name: "Whisper V3 Turbo", mode: "local", provider: "faster-whisper", vram_mb: 4000 },
        { model_id: "gemini/gemini-3.5-flash", display_name: "Gemini 3.5 Flash (Audio)", mode: "cloud", provider: "gemini" },
      ],
    },
    embedding: {
      active: { model_id: "jinaai/jina-clip-v2", display_name: "Jina Clip v2", mode: "local", provider: "huggingface", vector_dim: 1024, vram_mb: 1000 },
      available: [
        { model_id: "jinaai/jina-clip-v2", display_name: "Jina Clip v2 (1024d)", mode: "local", provider: "huggingface", vector_dim: 1024, vram_mb: 1000 },
        { model_id: "nomic-embed-vision-v2", display_name: "Nomic Embed Vision v2", mode: "local", provider: "huggingface", vector_dim: 768, vram_mb: 1000 },
        { model_id: "gemini/text-embedding-004", display_name: "Gemini Embedding 2", mode: "cloud", provider: "gemini", vector_dim: 3072 },
      ],
    },
    classifier: {
      active: { model_id: "Arch-Router-1.5B", display_name: "Arch-Router-1.5B GGUF", mode: "local", provider: "llama-cpp", vram_mb: 2000 },
      available: [
        { model_id: "Arch-Router-1.5B", display_name: "Arch-Router-1.5B", mode: "local", provider: "llama-cpp", vram_mb: 2000 },
        { model_id: "semantic", display_name: "Semantic Router", mode: "local", provider: "embedding", vram_mb: 0 },
        { model_id: "gemini/gemini-3.5-flash", display_name: "Gemini 3.5 Flash", mode: "cloud", provider: "gemini" },
      ],
    },
    completion: {
      active: { model_id: "gemini/gemma-4-31b-it", display_name: "Gemma 4 31B IT", mode: "cloud", provider: "gemini" },
      available: [
        { model_id: "gemini/gemma-4-31b-it", display_name: "Gemma 4 31B IT", mode: "cloud", provider: "gemini" },
        { model_id: "gemini/gemini-3.5-flash", display_name: "Gemini 3.5 Flash", mode: "cloud", provider: "gemini" },
        { model_id: "groq/llama-3.3-70b-versatile", display_name: "Groq Llama 3.3 70B", mode: "cloud", provider: "groq" },
        { model_id: "openrouter/google/gemini-3.5-flash:free", display_name: "OpenRouter Gemini 3.5 Flash Free", mode: "cloud", provider: "openrouter" },
      ],
    },
  });

  const [loadingHealth, setLoadingHealth] = useState(false);
  const [notification, setNotification] = useState<{ type: "success" | "error" | "info"; msg: string } | null>(null);

  // Fetch real system health if demo mode is off
  const refreshHealth = async () => {
    if (demoMode) {
      setNotification({ type: "info", msg: "Simulated health data refreshed." });
      return;
    }
    setLoadingHealth(true);
    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (apiKey) headers["X-API-Key"] = apiKey;

      const healthRes = await fetch(`${apiUrl}/health`, { headers });
      const healthData = await healthRes.json();
      setSystemHealth(healthData);

      const registryRes = await fetch(`${apiUrl}/api/models/registry`, { headers });
      const registryData = await registryRes.json();
      if (registryData && !registryData.detail) {
        setModelRegistry(registryData);
      }
      setNotification({ type: "success", msg: "System connections verified." });
    } catch (e: any) {
      setNotification({ type: "error", msg: `Failed to fetch live API data: ${e.message}` });
    } finally {
      setLoadingHealth(false);
    }
  };

  useEffect(() => {
    refreshHealth();
  }, [demoMode, apiUrl, apiKey]);

  // Handle Model default selection
  const selectModel = async (role: string, modelId: string) => {
    if (demoMode) {
      setModelRegistry((prev: any) => {
        const updatedRole = { ...prev[role] };
        const selected = updatedRole.available.find((m: any) => m.model_id === modelId);
        updatedRole.active = selected;
        return { ...prev, [role]: updatedRole };
      });
      // Simulate VRAM adaptation
      const selectedModel = modelRegistry[role].available.find((m: any) => m.model_id === modelId);
      if (selectedModel && selectedModel.vram_mb !== undefined) {
        setSystemHealth((prev: any) => {
          const details = { ...prev.inference_details };
          details.vram_used_mb = Math.min(details.vram_budget_mb - 2000, 1500 + selectedModel.vram_mb);
          if (!details.loaded_models.includes(modelId) && selectedModel.vram_mb > 0) {
            details.loaded_models = [...details.loaded_models.filter((m: string) => !m.includes(role)), modelId];
          }
          return { ...prev, inference_details: details };
        });
      }
      setNotification({ type: "success", msg: `Model updated: Active ${role} set to ${modelId}` });
      return;
    }

    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (apiKey) headers["X-API-Key"] = apiKey;

      const res = await fetch(`${apiUrl}/api/models/select`, {
        method: "POST",
        headers,
        body: JSON.stringify({ role, model_id: modelId }),
      });
      const data = await res.json();
      if (res.ok && data.status === "success") {
        setNotification({ type: "success", msg: data.message });
        refreshHealth();
      } else {
        setNotification({ type: "error", msg: data.detail || "Failed to update model selector." });
      }
    } catch (e: any) {
      setNotification({ type: "error", msg: `Network error: ${e.message}` });
    }
  };

  return (
    <div className="app-container">
      <div className="app-bg-glow" />

      {/* Sidebar Navigation */}
      <aside className="sidebar">
        <div className="logo-container">
          <div className="logo-icon">
            <Cpu size={18} className="text-white" />
          </div>
          <span className="logo-text">ContAIned AI</span>
        </div>

        <ul className="nav-links">
          <li
            className={`nav-item ${activeTab === "system" ? "nav-item-active" : ""}`}
            onClick={() => setActiveTab("system")}
          >
            <Server size={18} />
            <span>System Control</span>
            <span className="nav-status-badge badge-active">Live</span>
          </li>
          <li
            className={`nav-item ${activeTab === "syntraflow" ? "nav-item-active" : ""} ${
              !systemHealth.active_projects.includes("syntraflow") ? "nav-item-disabled" : ""
            }`}
            onClick={() => systemHealth.active_projects.includes("syntraflow") && setActiveTab("syntraflow")}
          >
            <Layers size={18} />
            <span>SyntraFlow Ingest</span>
            <span
              className={`nav-status-badge ${
                systemHealth.active_projects.includes("syntraflow") ? "badge-active" : "badge-inactive"
              }`}
            >
              {systemHealth.active_projects.includes("syntraflow") ? "Active" : "OFF"}
            </span>
          </li>
          <li
            className={`nav-item ${activeTab === "guardroute" ? "nav-item-active" : ""} ${
              !systemHealth.active_projects.includes("guardroute") ? "nav-item-disabled" : ""
            }`}
            onClick={() => systemHealth.active_projects.includes("guardroute") && setActiveTab("guardroute")}
          >
            <MessageSquare size={18} />
            <span>GuardRoute Chat</span>
            <span
              className={`nav-status-badge ${
                systemHealth.active_projects.includes("guardroute") ? "badge-active" : "badge-inactive"
              }`}
            >
              {systemHealth.active_projects.includes("guardroute") ? "Active" : "OFF"}
            </span>
          </li>
          <li
            className={`nav-item ${activeTab === "evalops" ? "nav-item-active" : ""} ${
              !systemHealth.active_projects.includes("evalops") ? "nav-item-disabled" : ""
            }`}
            onClick={() => systemHealth.active_projects.includes("evalops") && setActiveTab("evalops")}
          >
            <Activity size={18} />
            <span>EvalOps QA QA</span>
            <span
              className={`nav-status-badge ${
                systemHealth.active_projects.includes("evalops") ? "badge-active" : "badge-inactive"
              }`}
            >
              {systemHealth.active_projects.includes("evalops") ? "Active" : "OFF"}
            </span>
          </li>
        </ul>

        {/* Global Connection status summary in footer */}
        <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          <div className="connection-card" style={{ padding: "0.5rem 0.75rem", background: "rgba(255,255,255,0.01)" }}>
            <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>Inference VRAM</span>
            <span style={{ fontSize: "0.8rem", fontWeight: "600" }}>
              {systemHealth.inference_details.vram_used_mb} / {systemHealth.inference_details.vram_budget_mb} MB
            </span>
          </div>

          <div
            className="nav-item"
            style={{ padding: "0.5rem 0.75rem", fontSize: "0.85rem" }}
            onClick={() => setShowConfig(!showConfig)}
          >
            <Settings size={16} />
            <span>API Connections</span>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="content-area">
        {/* Header Bar */}
        <header className="header-bar">
          <div>
            <h1 style={{ fontFamily: "var(--font-display)", fontSize: "1.5rem", fontWeight: "600" }}>
              {activeTab === "system" && "Platform Control Center"}
              {activeTab === "syntraflow" && "SyntraFlow Ingestion & Hybrid RAG"}
              {activeTab === "guardroute" && "GuardRoute Scatter-Gather Orchestrator"}
              {activeTab === "evalops" && "EvalOps Safety & Quality benchmarks"}
            </h1>
            <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
              {activeTab === "system" && "Monitor backing services, manage model registry role specifications, VRAM eviction metrics"}
              {activeTab === "syntraflow" && "Multi-modal drag-drop document uploader, OCR split view, video segment timeline, and Graph/Vector RAG Sandbox"}
              {activeTab === "guardroute" && "Scatter-gather subagent orchestration map, codegen RestrictedPython sandbox execution, and SSE streaming client"}
              {activeTab === "evalops" && "DeepEval safety metrics, OpenTelemetry bottleneck visual tracing, RAGAS historical charts, model diagnostic benchmark logs"}
            </p>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
            {/* Demo/Sim Mode Switch */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                backgroundColor: "rgba(255,255,255,0.03)",
                padding: "0.5rem 0.75rem",
                borderRadius: "8px",
                border: "1px solid var(--border-color)",
              }}
            >
              <Zap size={14} className={demoMode ? "text-amber-500" : "text-emerald-500"} style={{ color: demoMode ? "#F59E0B" : "#10B981" }} />
              <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Simulation Mode</span>
              <input
                type="checkbox"
                checked={demoMode}
                onChange={(e) => setDemoMode(e.target.checked)}
                style={{ cursor: "pointer" }}
              />
            </div>

            <button className="button-neon button-ghost" onClick={refreshHealth} disabled={loadingHealth}>
              <RefreshCw size={14} className={loadingHealth ? "animate-spin" : ""} />
              <span>Verify Gateway</span>
            </button>
          </div>
        </header>

        {/* Global Notification Banner */}
        {notification && (
          <div
            style={{
              padding: "0.75rem 2rem",
              fontSize: "0.85rem",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              backgroundColor:
                notification.type === "success"
                  ? "rgba(16, 185, 129, 0.15)"
                  : notification.type === "error"
                  ? "rgba(239, 68, 68, 0.15)"
                  : "rgba(6, 182, 212, 0.15)",
              borderBottom: `1px solid ${
                notification.type === "success"
                  ? "rgba(16, 185, 129, 0.25)"
                  : notification.type === "error"
                  ? "rgba(239, 68, 68, 0.25)"
                  : "rgba(6, 182, 212, 0.25)"
              }`,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <Info size={16} />
              <span>{notification.msg}</span>
            </div>
            <button
              onClick={() => setNotification(null)}
              style={{ background: "none", border: "none", color: "white", cursor: "pointer", fontSize: "0.8rem" }}
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Config / Keys Drawer */}
        {showConfig && (
          <div
            className="glass-card"
            style={{
              margin: "1rem 2rem",
              backgroundColor: "rgba(13, 14, 18, 0.95)",
              borderColor: "var(--accent-indigo)",
            }}
          >
            <h3 style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1rem" }}>
              <Settings size={16} /> Platform Connection Settings
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1rem" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                <label style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>API Gateway Endpoint URL</label>
                <input
                  type="text"
                  className="input-field"
                  value={apiUrl}
                  onChange={(e) => setApiUrl(e.target.value)}
                />
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                <label style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>X-API-Key Header Value</label>
                <input
                  type="text"
                  className="input-field"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                />
              </div>
            </div>
            <button className="button-neon button-indigo" onClick={() => setShowConfig(false)}>
              Save Configuration
            </button>
          </div>
        )}

        {/* Dashboard Tabs Rendering */}
        <div className="dashboard-view">
          {activeTab === "system" && (
            <SystemView
              systemHealth={systemHealth}
              modelRegistry={modelRegistry}
              selectModel={selectModel}
            />
          )}
          {activeTab === "syntraflow" && <SyntraFlowView demoMode={demoMode} apiUrl={apiUrl} apiKey={apiKey} />}
          {activeTab === "guardroute" && <GuardRouteView demoMode={demoMode} apiUrl={apiUrl} apiKey={apiKey} />}
          {activeTab === "evalops" && <EvalOpsView demoMode={demoMode} apiUrl={apiUrl} apiKey={apiKey} />}
        </div>
      </main>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────
// Tab 1: System Control View
// ──────────────────────────────────────────────────────────────────────
function SystemView({ systemHealth, modelRegistry, selectModel }: any) {
  const vramPercent = (systemHealth.inference_details.vram_used_mb / systemHealth.inference_details.vram_budget_mb) * 100;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
      {/* Upper Status Grid: service connection status and VRAM load gauge */}
      <div className="status-grid">
        {/* Connection status card */}
        <div className="glass-card">
          <h3 style={{ fontSize: "1.1rem", marginBottom: "1.25rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <Server size={18} className="text-cyan-400" style={{ color: "var(--accent-cyan)" }} /> Connection Health Grid
          </h3>
          <div className="connection-grid">
            {Object.keys(systemHealth.services).map((service) => {
              const status = systemHealth.services[service];
              return (
                <div key={service} className="connection-card">
                  <span style={{ fontSize: "0.85rem", textTransform: "capitalize" }}>{service.replace("_", " ")}</span>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <span
                      className={`connection-dot ${
                        status === "connected"
                          ? "dot-connected"
                          : status === "degraded"
                          ? "dot-degraded"
                          : "dot-unreachable"
                      }`}
                    />
                    <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)", textTransform: "uppercase" }}>
                      {status}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* VRAM Gauge */}
        <div className="glass-card" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <h3 style={{ fontSize: "1.1rem", marginBottom: "0.5rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <Cpu size={18} className="text-amber-500" style={{ color: "var(--accent-amber)" }} /> Inference VRAM Budget
          </h3>

          <div style={{ display: "flex", alignItems: "center", gap: "1.5rem" }}>
            {/* Visual Gauge representation */}
            <div
              style={{
                width: "80px",
                height: "80px",
                borderRadius: "50%",
                background: `conic-gradient(var(--accent-amber) 0% ${vramPercent}%, rgba(255,255,255,0.05) ${vramPercent}% 100%)`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow: "0 0 15px rgba(245, 158, 11, 0.1)",
              }}
            >
              <div
                style={{
                  width: "66px",
                  height: "66px",
                  borderRadius: "50%",
                  backgroundColor: "var(--bg-main)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "0.85rem",
                  fontWeight: "600",
                }}
              >
                {vramPercent.toFixed(0)}%
              </div>
            </div>

            <div>
              <p style={{ fontSize: "1.1rem", fontWeight: "600" }}>
                {systemHealth.inference_details.vram_used_mb} MB <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>used</span>
              </p>
              <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                of {systemHealth.inference_details.vram_budget_mb} MB allocated
              </p>
              <p style={{ fontSize: "0.75rem", color: "var(--accent-cyan)", marginTop: "0.25rem", display: "flex", alignItems: "center", gap: "0.25rem" }}>
                <Zap size={10} /> Active Device: {systemHealth.inference_details.device.toUpperCase()}
              </p>
            </div>
          </div>

          <div style={{ fontSize: "0.75rem", borderTop: "1px solid var(--border-color)", paddingTop: "0.5rem", marginTop: "0.5rem" }}>
            <span style={{ color: "var(--text-secondary)" }}>Loaded model slots: </span>
            <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>
              {systemHealth.inference_details.loaded_models.length > 0
                ? systemHealth.inference_details.loaded_models.join(", ")
                : "None"}
            </span>
          </div>
        </div>
      </div>

      {/* Model Registry Selector */}
      <div className="glass-card">
        <h3 style={{ fontSize: "1.1rem", marginBottom: "1.5rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <Layers size={18} style={{ color: "var(--accent-indigo)" }} /> Model Role Specification Selector
        </h3>

        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {Object.keys(modelRegistry).map((role) => {
            const roleData = modelRegistry[role];
            if (!roleData.active) return null;
            return (
              <div
                key={role}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "1rem",
                  borderRadius: "8px",
                  backgroundColor: "rgba(255,255,255,0.01)",
                  border: "1px solid var(--border-color)",
                }}
              >
                <div>
                  <h4 style={{ textTransform: "uppercase", fontSize: "0.8rem", color: "var(--text-secondary)", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <span>{role} role</span>
                    <span
                      style={{
                        fontSize: "0.7rem",
                        padding: "0.05rem 0.35rem",
                        borderRadius: "4px",
                        backgroundColor: roleData.active.mode === "local" ? "var(--accent-indigo-glow)" : "var(--accent-cyan-glow)",
                        color: roleData.active.mode === "local" ? "var(--accent-indigo)" : "var(--accent-cyan)",
                      }}
                    >
                      {roleData.active.mode === "local" ? "Local GPU" : "Cloud API"}
                    </span>
                  </h4>
                  <p style={{ fontSize: "1rem", fontWeight: "600", marginTop: "0.25rem" }}>
                    {roleData.active.display_name}
                  </p>
                  <p style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                    ID: {roleData.active.model_id} | Provider: {roleData.active.provider}
                    {roleData.active.vram_mb !== undefined && ` | Load Weight: ${roleData.active.vram_mb} MB`}
                  </p>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                  <select
                    className="input-field"
                    style={{ fontSize: "0.85rem", padding: "0.5rem 2rem 0.5rem 1rem", minWidth: "220px" }}
                    value={roleData.active.model_id}
                    onChange={(e) => selectModel(role, e.target.value)}
                  >
                    {roleData.available.map((m: any) => (
                      <option key={m.model_id} value={m.model_id}>
                        {m.display_name} ({m.mode})
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Admin Quick Console links */}
      <div className="glass-card">
        <h3 style={{ fontSize: "1.1rem", marginBottom: "1rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <ExternalLink size={18} style={{ color: "var(--accent-cyan)" }} /> Admin Quick-Console Panel Links
        </h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem" }}>
          <a href="http://localhost:6333/dashboard" target="_blank" rel="noreferrer" className="button-neon button-ghost" style={{ justifyContent: "center" }}>
            <span>Qdrant Vector Dashboard</span> <ExternalLink size={12} />
          </a>
          <a href="http://localhost:7474" target="_blank" rel="noreferrer" className="button-neon button-ghost" style={{ justifyContent: "center" }}>
            <span>Neo4j Graph Console</span> <ExternalLink size={12} />
          </a>
          <a href="http://localhost:5050" target="_blank" rel="noreferrer" className="button-neon button-ghost" style={{ justifyContent: "center" }}>
            <span>pgAdmin PostgreSQL UI</span> <ExternalLink size={12} />
          </a>
          <a href="http://localhost:8080" target="_blank" rel="noreferrer" className="button-neon button-ghost" style={{ justifyContent: "center" }}>
            <span>Kafka UI Broker View</span> <ExternalLink size={12} />
          </a>
          <a href="http://localhost:16686" target="_blank" rel="noreferrer" className="button-neon button-ghost" style={{ justifyContent: "center" }}>
            <span>Jaeger OpenTelemetry Trace</span> <ExternalLink size={12} />
          </a>
        </div>
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────
// Tab 2: SyntraFlow Ingest View
// ──────────────────────────────────────────────────────────────────────
function SyntraFlowView({ demoMode, apiUrl, apiKey }: any) {
  const [dragActive, setDragActive] = useState(false);
  const [jobs, setJobs] = useState<any[]>([
    { job_id: "job_941a2f3b", filename: "financial_report_q3.pdf", type: "Document", status: "completed", progress: 100, timestamp: "2026-07-17 12:45" },
    { job_id: "job_82b311fc", filename: "system_maintenance_meeting.mp4", type: "Video", status: "completed", progress: 100, timestamp: "2026-07-17 11:30" },
    { job_id: "job_01fe9a6c", filename: "sensor_raw_telemetry.csv", type: "Document", status: "failed", progress: 45, error: "Duplicate document content detected (SHA-256 collision)", timestamp: "2026-07-17 10:15" },
  ]);

  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  // Video and timeline states
  const [selectedVideoSegment, setSelectedVideoSegment] = useState<number>(0);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const videoSegments = [
    { start: 0, end: 15, text: "Okay, starting the developer review of the ContAIned architecture meeting. We've got postgres and kafka active.", events: "Laughter", keyframe: "Developer team sitting around table with architecture flowchart on screen." },
    { start: 15, end: 32, text: "Now we need to address the model registry. The classifier model is Arch-Router-1.5B loading locally.", events: "Applause", keyframe: "Slight zoom into whiteboard layout showing Classifier role pointing to arch." },
    { start: 32, end: 55, text: "Lastly, we will verify the code sandbox. We need to implement RestrictedPython with OTel trace logs.", events: null, keyframe: "Laptop screen close-up displaying visual otel tracer waterfalls." },
  ];

  // RAG Search states
  const [ragQuery, setRagQuery] = useState("");
  const [ragStrategy, setRagStrategy] = useState("hybrid");
  const [ragResults, setRagResults] = useState<any>(null);
  const [ragLoading, setRagLoading] = useState(false);

  // File Upload Handlers
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const triggerUpload = (files: FileList) => {
    if (files.length === 0) return;
    const file = files[0];
    setUploading(true);
    setUploadProgress(10);
    
    // Simulate upload progress
    const timer = setInterval(() => {
      setUploadProgress((prev) => {
        if (prev >= 100) {
          clearInterval(timer);
          setTimeout(() => {
            const newJob = {
              job_id: "job_" + Math.random().toString(36).substring(2, 10),
              filename: file.name,
              type: file.type.includes("video") ? "Video" : "Document",
              status: "completed",
              progress: 100,
              timestamp: new Date().toISOString().replace("T", " ").substring(0, 16),
            };
            setJobs((prevJobs) => [newJob, ...prevJobs]);
            setUploading(false);
          }, 500);
          return 100;
        }
        return prev + 15;
      });
    }, 150);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      triggerUpload(e.dataTransfer.files);
    }
  };

  // Perform RAG sandbox query
  const performSearch = async () => {
    if (!ragQuery.trim()) return;
    setRagLoading(true);

    if (demoMode) {
      setTimeout(() => {
        setRagResults({
          query: ragQuery,
          strategy: ragStrategy,
          vector_results: [
            { id: "chunk_9011", text: "The model registry maps specific execution roles to exact local model IDs (e.g. THUDM/GLM-OCR for the ocr role) or cloud providers.", score: 0.89 },
            { id: "chunk_2411", text: "VRAM budget defaults to 20000 MB on local dev environments to avoid sudden out of memory context crashes.", score: 0.81 }
          ],
          graph_results: [
            { source: "Model Registry", relation: "RESOLVES", target: "OCR Role", notes: "Default is local GLM-OCR" },
            { source: "VRAM Manager", relation: "ALLOCATES", target: "VRAM Budget", notes: "Triggered on loader execution" }
          ],
          hybrid_response: "The model registry resolves task roles dynamically to designated weights. The VRAM manager allocates memory slots on-demand, handling auto-download of gated Hugging Face weights."
        });
        setRagLoading(false);
      }, 1000);
      return;
    }

    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (apiKey) headers["X-API-Key"] = apiKey;

      const res = await fetch(`${apiUrl}/api/syntraflow/search`, {
        method: "POST",
        headers,
        body: JSON.stringify({ query: ragQuery, strategy: ragStrategy }),
      });
      const data = await res.json();
      setRagResults(data);
    } catch (e: any) {
      console.error(e);
    } finally {
      setRagLoading(false);
    }
  };

  const seekVideo = (time: number, index: number) => {
    setSelectedVideoSegment(index);
    if (videoRef.current) {
      videoRef.current.currentTime = time;
      videoRef.current.play();
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
      {/* File Ingest Panel */}
      <div className="status-grid">
        {/* Dropzone area */}
        <div className="glass-card">
          <h3 style={{ fontSize: "1.1rem", marginBottom: "1rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <UploadCloud size={18} style={{ color: "var(--accent-emerald)" }} /> Drag & Drop File Ingest
          </h3>

          <div
            className={`upload-dropzone ${dragActive ? "upload-dropzone-active" : ""}`}
            onDragEnter={handleDrag}
            onDragOver={handleDrag}
            onDragLeave={handleDrag}
            onDrop={handleDrop}
            onClick={() => document.getElementById("file-input")?.click()}
          >
            <input
              id="file-input"
              type="file"
              style={{ display: "none" }}
              onChange={(e) => e.target.files && triggerUpload(e.target.files)}
            />
            <UploadCloud size={44} style={{ color: "var(--text-secondary)", marginBottom: "1rem" }} />
            {uploading ? (
              <div>
                <p style={{ fontWeight: "600" }}>Uploading: {uploadProgress}%</p>
                <div style={{ width: "100%", height: "4px", backgroundColor: "rgba(255,255,255,0.05)", borderRadius: "2px", marginTop: "0.5rem" }}>
                  <div style={{ width: `${uploadProgress}%`, height: "100%", backgroundColor: "var(--accent-emerald)", borderRadius: "2px", transition: "width 0.1s" }} />
                </div>
              </div>
            ) : (
              <div>
                <p style={{ fontWeight: "600", fontSize: "0.95rem" }}>Drag files here or click to browse</p>
                <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
                  PDF, DOCX, PNG, JPG, MP4, MOV, WAV, MP3 (Max sizes: Docs 100MB, Videos 500MB)
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Job Ingestion tracker list */}
        <div className="glass-card" style={{ display: "flex", flexDirection: "column", height: "300px" }}>
          <h3 style={{ fontSize: "1.1rem", marginBottom: "1rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <Activity size={18} style={{ color: "var(--accent-emerald)" }} /> Active Ingestion Job Tracker
          </h3>
          <div style={{ flexGrow: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            {jobs.map((job) => (
              <div
                key={job.job_id}
                style={{
                  padding: "0.75rem",
                  borderRadius: "8px",
                  backgroundColor: "rgba(255,255,255,0.01)",
                  border: "1px solid var(--border-color)",
                  fontSize: "0.85rem",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.25rem" }}>
                  <span style={{ fontWeight: "600", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "200px" }}>
                    {job.filename}
                  </span>
                  <span
                    style={{
                      fontSize: "0.7rem",
                      padding: "0.05rem 0.35rem",
                      borderRadius: "4px",
                      backgroundColor:
                        job.status === "completed"
                          ? "rgba(16, 185, 129, 0.1)"
                          : job.status === "failed"
                          ? "rgba(239, 68, 68, 0.1)"
                          : "rgba(245, 158, 11, 0.1)",
                      color:
                        job.status === "completed"
                          ? "var(--accent-emerald)"
                          : job.status === "failed"
                          ? "var(--accent-rose)"
                          : "var(--accent-amber)",
                    }}
                  >
                    {job.status}
                  </span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                  <span>{job.type} • ID: {job.job_id}</span>
                  <span>{job.timestamp}</span>
                </div>
                {job.error && (
                  <div style={{ color: "var(--accent-rose)", fontSize: "0.75rem", marginTop: "0.25rem", display: "flex", alignItems: "center", gap: "0.25rem" }}>
                    <AlertTriangle size={12} /> {job.error}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Video Segment timeline & player */}
      <div className="glass-card">
        <h3 style={{ fontSize: "1.1rem", marginBottom: "1.5rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <Video size={18} style={{ color: "var(--accent-emerald)" }} /> Video Segment Temporal Timeline
        </h3>

        <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "1.5rem" }}>
          {/* Mock Video player */}
          <div>
            <video
              ref={videoRef}
              src="https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4"
              controls
              style={{ width: "100%", borderRadius: "8px", border: "1px solid var(--border-color)" }}
            />
            <div style={{ marginTop: "0.5rem", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
              <span>ASR Engine model: </span>
              <span className="text-white" style={{ fontFamily: "var(--font-mono)", color: "white" }}>SenseVoice-Small</span>
            </div>
          </div>

          {/* Chronological Timeline segments */}
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", height: "260px", overflowY: "auto" }}>
            {videoSegments.map((seg, idx) => (
              <div
                key={idx}
                onClick={() => seekVideo(seg.start, idx)}
                style={{
                  padding: "0.75rem 1rem",
                  borderRadius: "8px",
                  cursor: "pointer",
                  border: `1px solid ${selectedVideoSegment === idx ? "var(--accent-emerald)" : "var(--border-color)"}`,
                  backgroundColor: selectedVideoSegment === idx ? "var(--accent-emerald-glow)" : "rgba(255,255,255,0.01)",
                  transition: "var(--transition-normal)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.25rem", fontSize: "0.8rem" }}>
                  <span style={{ display: "flex", alignItems: "center", gap: "0.25rem", color: "var(--accent-emerald)", fontWeight: "600" }}>
                    <Play size={10} /> {seg.start}s - {seg.end}s
                  </span>
                  {seg.events && (
                    <span style={{ fontSize: "0.7rem", backgroundColor: "rgba(255,255,255,0.05)", padding: "0.05rem 0.3rem", borderRadius: "4px" }}>
                      🎙️ Event: {seg.events}
                    </span>
                  )}
                </div>
                <p style={{ fontSize: "0.85rem", color: "var(--text-primary)" }}>{seg.text}</p>
                <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.25rem", fontStyle: "italic" }}>
                  Frame: {seg.keyframe}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* RAG Sandbox Comparison block */}
      <div className="glass-card">
        <h3 style={{ fontSize: "1.1rem", marginBottom: "1.25rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <Search size={18} style={{ color: "var(--accent-emerald)" }} /> Multi-Strategy RAG Sandbox
        </h3>

        <div style={{ display: "flex", gap: "0.75rem", marginBottom: "1.5rem" }}>
          <input
            type="text"
            className="input-field"
            style={{ flexGrow: 1 }}
            placeholder="Type query to retrieve search contents from Vector + Knowledge Graph store..."
            value={ragQuery}
            onChange={(e) => setRagQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && performSearch()}
          />

          <select
            className="input-field"
            style={{ minWidth: "160px" }}
            value={ragStrategy}
            onChange={(e) => setRagStrategy(e.target.value)}
          >
            <option value="vector">Vector Only</option>
            <option value="graph">Graph Only</option>
            <option value="hybrid">Hybrid Search</option>
          </select>

          <button className="button-neon button-indigo" onClick={performSearch} disabled={ragLoading}>
            <Search size={14} />
            <span>Search</span>
          </button>
        </div>

        {ragLoading && (
          <div style={{ textAlign: "center", padding: "2rem" }}>
            <RefreshCw size={24} className="animate-spin" style={{ color: "var(--accent-emerald)", margin: "0 auto 0.5rem" }} />
            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>Searching DB clusters...</p>
          </div>
        )}

        {ragResults && (
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {/* Generated Hybrid RAG synthesized summary */}
            <div style={{ padding: "1rem", borderRadius: "8px", border: "1px solid rgba(16, 185, 129, 0.2)", backgroundColor: "var(--accent-emerald-glow)" }}>
              <h4 style={{ fontSize: "0.8rem", textTransform: "uppercase", color: "var(--accent-emerald)", fontWeight: "600", marginBottom: "0.25rem" }}>
                Synthesized RAG Response
              </h4>
              <p style={{ fontSize: "0.9rem" }}>{ragResults.hybrid_response}</p>
            </div>

            {/* Side-by-side retrieved vectors and graph edges */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
              {/* Qdrant Vectors */}
              <div>
                <h4 style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem", display: "flex", alignItems: "center", gap: "0.25rem" }}>
                  <Database size={14} /> Qdrant Vectors (Cosine scores)
                </h4>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                  {ragResults.vector_results.map((vec: any, idx: number) => (
                    <div key={idx} style={{ padding: "0.75rem", borderRadius: "6px", border: "1px solid var(--border-color)", backgroundColor: "rgba(255,255,255,0.01)" }}>
                      <p style={{ fontSize: "0.8rem" }}>{vec.text}</p>
                      <span style={{ fontSize: "0.7rem", color: "var(--accent-cyan)", fontWeight: "600" }}>
                        Score: {vec.score} | Chunk: {vec.id}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Neo4j Cypher edges */}
              <div>
                <h4 style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem", display: "flex", alignItems: "center", gap: "0.25rem" }}>
                  <Layers size={14} /> Neo4j Entities & Relationships
                </h4>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                  {ragResults.graph_results.map((edge: any, idx: number) => (
                    <div key={idx} style={{ padding: "0.75rem", borderRadius: "6px", border: "1px solid var(--border-color)", backgroundColor: "rgba(255,255,255,0.01)", fontSize: "0.8rem" }}>
                      <div>
                        <span style={{ color: "var(--accent-indigo)", fontWeight: "600" }}>({edge.source})</span>
                        <span style={{ color: "var(--text-muted)", margin: "0 0.5rem" }}>-[{edge.relation}]-&gt;</span>
                        <span style={{ color: "var(--accent-indigo)", fontWeight: "600" }}>({edge.target})</span>
                      </div>
                      <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>{edge.notes}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────
// Tab 3: GuardRoute Chat View
// ──────────────────────────────────────────────────────────────────────
function GuardRouteView({ demoMode, apiUrl, apiKey }: any) {
  // Chat state
  const [messages, setMessages] = useState<any[]>([
    { role: "bot", text: "Hello! I am GuardRoute Orchestration node. Send a prompt to run scatter-gather subagents or evaluate sandbox scripts." }
  ]);
  const [chatInput, setChatInput] = useState("");
  const [loadingChat, setLoadingChat] = useState(false);
  const [chatMeta, setChatMeta] = useState<any>(null);

  // Subagent Logs side-drawer
  const [drawerNode, setDrawerNode] = useState<any>(null);

  // Flowchart Nodes and Edges state
  const initialNodes = [
    { id: "start", type: "input", data: { label: "1. Query input" }, position: { x: 250, y: 10 }, className: "react-flow-node-custom" },
    { id: "classifier", data: { label: "2. Intent Classifier (Arch)" }, position: { x: 250, y: 80 }, className: "react-flow-node-custom" },
    { id: "rag", data: { label: "3. RAG Retrieval Agent" }, position: { x: 50, y: 170 }, className: "react-flow-node-custom" },
    { id: "sandbox", data: { label: "4. Code Sandbox (Restricted)" }, position: { x: 250, y: 170 }, className: "react-flow-node-custom" },
    { id: "search", data: { label: "5. Web Search Agent" }, position: { x: 450, y: 170 }, className: "react-flow-node-custom" },
    { id: "synth", data: { label: "6. Response Synthesis" }, position: { x: 250, y: 260 }, className: "react-flow-node-custom" },
    { id: "end", type: "output", data: { label: "7. Response Stream" }, position: { x: 250, y: 340 }, className: "react-flow-node-custom" },
  ];

  const initialEdges = [
    { id: "e1-2", source: "start", target: "classifier", animated: true, markerEnd: { type: MarkerType.Arrow } },
    { id: "e2-3", source: "classifier", target: "rag", markerEnd: { type: MarkerType.Arrow } },
    { id: "e2-4", source: "classifier", target: "sandbox", markerEnd: { type: MarkerType.Arrow } },
    { id: "e2-5", source: "classifier", target: "search", markerEnd: { type: MarkerType.Arrow } },
    { id: "e3-6", source: "rag", target: "synth", markerEnd: { type: MarkerType.Arrow } },
    { id: "e4-6", source: "sandbox", target: "synth", markerEnd: { type: MarkerType.Arrow } },
    { id: "e5-6", source: "search", target: "synth", markerEnd: { type: MarkerType.Arrow } },
    { id: "e6-7", source: "synth", target: "end", animated: true, markerEnd: { type: MarkerType.Arrow } },
  ];

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);

  // Simulation highlight loop for graph visualization
  const runGraphSimulation = (requiredAgents: string[]) => {
    // Reset all nodes
    setNodes((nds) => nds.map((n) => ({ ...n, className: "react-flow-node-custom" })));

    setTimeout(() => {
      // Step 1: Highlight classifier
      setNodes((nds) => nds.map((n) => n.id === "classifier" ? { ...n, className: "react-flow-node-custom react-flow-node-active" } : n));
    }, 200);

    setTimeout(() => {
      // Step 2: Completed classifier, highlight subagents
      setNodes((nds) => nds.map((n) => {
        if (n.id === "classifier") return { ...n, className: "react-flow-node-custom react-flow-node-completed" };
        if (requiredAgents.includes(n.id)) return { ...n, className: "react-flow-node-custom react-flow-node-active" };
        return n;
      }));
    }, 800);

    setTimeout(() => {
      // Step 3: Complete subagents, highlight synthesizer
      setNodes((nds) => nds.map((n) => {
        if (requiredAgents.includes(n.id)) return { ...n, className: "react-flow-node-custom react-flow-node-completed" };
        if (n.id === "synth") return { ...n, className: "react-flow-node-custom react-flow-node-active" };
        return n;
      }));
    }, 1600);

    setTimeout(() => {
      // Step 4: Complete synthesizer and start end node
      setNodes((nds) => nds.map((n) => {
        if (n.id === "synth") return { ...n, className: "react-flow-node-custom react-flow-node-completed" };
        if (n.id === "end") return { ...n, className: "react-flow-node-custom react-flow-node-completed" };
        return n;
      }));
    }, 2400);
  };

  // Node log drawer mapping
  const onNodeClick = (_event: any, node: any) => {
    const mockLogs: Record<string, any> = {
      classifier: {
        role: "classifier",
        model: "Arch-Router-1.5B (GGUF)",
        latency: "120ms",
        decision: "complex",
        required_agents: ["rag", "sandbox"],
        raw_output: { complexity: "complex", required_agents: ["rag", "sandbox"], confidence: 0.96 }
      },
      rag: {
        role: "retriever",
        model: "jina-clip-v2",
        latency: "450ms",
        chunks_retrieved: 2,
        graph_entities: 4,
        raw_output: { results_count: 2, matches: ["chunk_9011", "chunk_2411"] }
      },
      sandbox: {
        role: "code_executor",
        engine: "RestrictedPython",
        latency: "340ms",
        script: "def run():\n  return sum([x for x in range(100)])\nresult = run()",
        stdout: "Result evaluated: 4950",
        exit_code: 0
      },
      search: {
        role: "web_search",
        latency: "510ms",
        urls_visited: ["https://docs.litellm.ai"],
        summary: "LiteLLM is a lightweight python proxy client supporting over 50 providers."
      },
      synth: {
        role: "synthesizer",
        model: "Gemma 4 31B IT",
        tokens_generated: 142,
        latency: "940ms",
        provider: "Gemini Cloud"
      }
    };

    if (mockLogs[node.id]) {
      setDrawerNode(mockLogs[node.id]);
    }
  };

  // Chat Execution Handler
  const executeChat = async () => {
    if (!chatInput.trim()) return;
    const promptText = chatInput;
    setChatInput("");
    setMessages((prev) => [...prev, { role: "user", text: promptText }]);
    setLoadingChat(true);

    if (demoMode) {
      // Simulate scatter-gather flow classifier routing
      let agentsToRun = ["rag"];
      if (promptText.toLowerCase().includes("code") || promptText.toLowerCase().includes("math") || promptText.toLowerCase().includes("sandbox")) {
        agentsToRun = ["sandbox", "rag"];
      } else if (promptText.toLowerCase().includes("web") || promptText.toLowerCase().includes("latest") || promptText.toLowerCase().includes("search")) {
        agentsToRun = ["search", "rag"];
      }

      runGraphSimulation(agentsToRun);

      setTimeout(() => {
        // Stream text token by token simulate
        let finalResponse = "I have successfully orchestrated the subagents to address your prompt. ";
        if (agentsToRun.includes("sandbox")) {
          finalResponse += "The RestrictedPython sandbox evaluated the formula successfully, returning result 4950 in 340ms without network leak risks.";
        } else {
          finalResponse += "The RAG Hybrid store fetched relevant documentation regarding the model registry setup and loaded weight slots.";
        }

        setMessages((prev) => [...prev, { role: "bot", text: finalResponse }]);
        setChatMeta({
          complexity: agentsToRun.length > 1 ? "complex" : "medium",
          agents: agentsToRun.join(", "),
          latency: "1.24s",
          model: "Gemma 4 31B IT",
          tokens: 88,
        });
        setLoadingChat(false);
      }, 2600);
      return;
    }

    try {
      // Live API POST request
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (apiKey) headers["X-API-Key"] = apiKey;

      const res = await fetch(`${apiUrl}/api/guardroute/chat`, {
        method: "POST",
        headers,
        body: JSON.stringify({ prompt: promptText }),
      });
      const data = await res.json();
      if (res.ok) {
        setMessages((prev) => [...prev, { role: "bot", text: data.response }]);
        setChatMeta({
          complexity: data.complexity,
          agents: data.subagents_ran ? data.subagents_ran.join(", ") : "none",
          latency: `${data.latency_sec}s`,
          model: "Active default Completion Model",
          tokens: "N/A",
        });
        if (data.subagents_ran) {
          runGraphSimulation(data.subagents_ran);
        }
      } else {
        setMessages((prev) => [...prev, { role: "bot", text: `Error: ${data.detail || "Pipeline execution failed"}` }]);
      }
    } catch (e: any) {
      setMessages((prev) => [...prev, { role: "bot", text: `Network error: ${e.message}` }]);
    } finally {
      setLoadingChat(false);
    }
  };

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "1.5rem", height: "calc(100vh - 180px)", overflow: "hidden" }}>
      {/* Left Pane: LangGraph flowchart flowchart */}
      <div className="glass-card" style={{ display: "flex", flexDirection: "column", height: "100%", padding: "1rem" }}>
        <h3 style={{ fontSize: "1.1rem", marginBottom: "0.5rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <Layers size={18} style={{ color: "var(--accent-indigo)" }} /> LangGraph Scatter-Gather Flowchart Map
        </h3>
        <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginBottom: "1rem" }}>
          Click highlighted nodes to inspect subagent trace variables and sandbox outputs.
        </p>

        <div style={{ flexGrow: 1, border: "1px solid var(--border-color)", borderRadius: "8px", position: "relative" }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            fitView
          >
            <Controls />
            <Background color="#1D1D22" gap={16} />
          </ReactFlow>
        </div>

        {/* Subagent Drawer inside the Graph Container */}
        {drawerNode && (
          <div
            style={{
              position: "absolute",
              bottom: "1rem",
              left: "1rem",
              right: "1rem",
              backgroundColor: "rgba(13, 14, 18, 0.95)",
              border: "1px solid var(--accent-indigo)",
              borderRadius: "8px",
              padding: "1rem",
              zIndex: 10,
              fontSize: "0.8rem",
              maxHeight: "180px",
              overflowY: "auto",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border-color)", paddingBottom: "0.25rem", marginBottom: "0.5rem" }}>
              <span style={{ fontWeight: "600", textTransform: "uppercase", color: "var(--accent-indigo)" }}>
                Role: {drawerNode.role}
              </span>
              <button
                onClick={() => setDrawerNode(null)}
                style={{ background: "none", border: "none", color: "white", cursor: "pointer", fontWeight: "600" }}
              >
                Close
              </button>
            </div>
            <pre style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: "var(--text-primary)", whiteSpace: "pre-wrap" }}>
              {JSON.stringify(drawerNode, null, 2)}
            </pre>
          </div>
        )}
      </div>

      {/* Right Pane: Streaming Chat client */}
      <div className="glass-card" style={{ display: "flex", flexDirection: "column", height: "100%" }}>
        <h3 style={{ fontSize: "1.1rem", marginBottom: "0.5rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <MessageSquare size={18} style={{ color: "var(--accent-indigo)" }} /> GuardRoute Chat Console
        </h3>

        {/* Chat meta stats */}
        {chatMeta && (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(4, 1fr)",
              gap: "0.5rem",
              padding: "0.5rem",
              backgroundColor: "rgba(255,255,255,0.02)",
              border: "1px solid var(--border-color)",
              borderRadius: "6px",
              fontSize: "0.725rem",
              marginBottom: "1rem",
            }}
          >
            <div>
              <span style={{ color: "var(--text-muted)" }}>Complexity: </span>
              <span style={{ fontWeight: "600", textTransform: "capitalize", color: "var(--accent-amber)" }}>{chatMeta.complexity}</span>
            </div>
            <div>
              <span style={{ color: "var(--text-muted)" }}>Subagents: </span>
              <span style={{ fontWeight: "600", color: "var(--accent-cyan)" }}>{chatMeta.agents}</span>
            </div>
            <div>
              <span style={{ color: "var(--text-muted)" }}>Latency: </span>
              <span style={{ fontWeight: "600" }}>{chatMeta.latency}</span>
            </div>
            <div>
              <span style={{ color: "var(--text-muted)" }}>Tokens: </span>
              <span style={{ fontWeight: "600" }}>{chatMeta.tokens}</span>
            </div>
          </div>
        )}

        {/* Messages Stream */}
        <div style={{ flexGrow: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "1rem", marginBottom: "1rem", padding: "0.5rem" }}>
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={msg.role === "user" ? "chat-message-user" : "chat-message-bot"}
            >
              <p style={{ fontSize: "0.875rem", lineHeight: "1.4" }}>{msg.text}</p>
            </div>
          ))}
          {loadingChat && (
            <div className="chat-message-bot" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <RefreshCw size={14} className="animate-spin" />
              <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Orchestrating subagents response...</span>
            </div>
          )}
        </div>

        {/* Input Bar */}
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <input
            type="text"
            className="input-field"
            style={{ flexGrow: 1 }}
            placeholder="Ask GuardRoute (e.g. 'Solve code sum for numbers below 100')..."
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && executeChat()}
          />
          <button className="button-neon button-indigo" onClick={executeChat} disabled={loadingChat}>
            <span>Send</span>
          </button>
        </div>
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────
// Tab 4: EvalOps QA & Benchmarks View
// ──────────────────────────────────────────────────────────────────────
function EvalOpsView({ demoMode, apiUrl, apiKey }: any) {
  const [reports, setReports] = useState<any>({
    retrieval_quality: {
      metrics: {
        gsm8k_reasoning_accuracy: 0.85,
        mmlu_subset_score: 0.78,
        scatter_gather_completeness_rate: 1.0,
        fallback_success_rate: 1.0,
        average_transaction_latency_ms: 520.4,
        primary_provider_failures_injected: 0,
      },
      created_at: "2026-07-17 12:00:00",
    },
    classifier_benchmark: {
      metrics: {
        cold_start_latency_ms: 1240.5,
        warm_start_latency_ms: 120.2,
        average_inference_latency_ms: 145.6,
        complexity_accuracy: 0.95,
        agents_accuracy: 0.9,
        precision: 0.95,
        recall: 0.9,
        f1_score: 0.92,
        vram_eviction_verified: true,
      },
      created_at: "2026-07-17 12:00:00",
    },
    safety_guardrails: {
      metrics: {
        prompt_injection_vulnerabilities: 0,
        toxicity_score: 0.05,
        hallucination_rate: 0.08,
        pii_leakage_detected: false,
      },
      created_at: "2026-07-17 12:00:00",
    },
  });

  const [loading, setLoading] = useState(false);

  // Fetch metrics data from database
  const fetchEvalData = async () => {
    if (demoMode) return;
    setLoading(true);
    try {
      const headers: Record<string, string> = {};
      if (apiKey) headers["X-API-Key"] = apiKey;

      const res = await fetch(`${apiUrl}/api/evalops/dashboard`, { headers });
      const data = await res.json();
      if (data && data.sections) {
        setReports(data.sections);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvalData();
  }, [demoMode]);

  // Recharts metric timeline data
  const chartData = [
    { name: "Run 1", recall: 0.72, faithfulness: 0.78, similarity: 0.75 },
    { name: "Run 2", recall: 0.78, faithfulness: 0.81, similarity: 0.8 },
    { name: "Run 3", recall: 0.84, faithfulness: 0.85, similarity: 0.82 },
    { name: "Run 4", recall: 0.85, faithfulness: 0.88, similarity: 0.86 },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
      {/* Recharts Area Timeline */}
      <div className="glass-card">
        <h3 style={{ fontSize: "1.1rem", marginBottom: "1.5rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <TrendingUp size={18} style={{ color: "var(--accent-amber)" }} /> RAGAS Metric Accuracy Progression Timeline
          {loading && <RefreshCw size={14} className="animate-spin" style={{ marginLeft: "auto" }} />}
        </h3>

        <div style={{ width: "100%", height: "260px" }}>
          <ResponsiveContainer>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="colorRecall" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--accent-emerald)" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="var(--accent-emerald)" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorFaithfulness" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--accent-indigo)" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="var(--accent-indigo)" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorSimilarity" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--accent-cyan)" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="var(--accent-cyan)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#262833" />
              <XAxis dataKey="name" stroke="var(--text-muted)" />
              <YAxis stroke="var(--text-muted)" domain={[0.5, 1.0]} />
              <Tooltip contentStyle={{ backgroundColor: "var(--bg-main)", borderColor: "var(--border-color)" }} />
              <Legend />
              <Area type="monotone" dataKey="recall" stroke="var(--accent-emerald)" fillOpacity={1} fill="url(#colorRecall)" name="Context Recall" />
              <Area type="monotone" dataKey="faithfulness" stroke="var(--accent-indigo)" fillOpacity={1} fill="url(#colorFaithfulness)" name="Faithfulness" />
              <Area type="monotone" dataKey="similarity" stroke="var(--accent-cyan)" fillOpacity={1} fill="url(#colorSimilarity)" name="Semantic Similarity" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Safety Audit logs & OTEL visualization */}
      <div className="status-grid">
        {/* Safety logs */}
        <div className="glass-card">
          <h3 style={{ fontSize: "1.1rem", marginBottom: "1.25rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <ShieldCheck size={18} style={{ color: "var(--accent-amber)" }} /> Safety Guardrails Audit Logs
          </h3>

          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            <div style={{ display: "flex", justifySelf: "stretch", justifyContent: "space-between", padding: "0.75rem", borderRadius: "8px", border: "1px solid var(--border-color)", backgroundColor: "rgba(255,255,255,0.01)" }}>
              <div>
                <p style={{ fontSize: "0.85rem", fontWeight: "600" }}>Prompt Injection Scan</p>
                <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>Vulnerabilities detected: {reports.safety_guardrails.metrics.prompt_injection_vulnerabilities}</p>
              </div>
              <span style={{ fontSize: "0.7rem", backgroundColor: "var(--accent-emerald-glow)", color: "var(--accent-emerald)", padding: "0.2rem 0.4rem", borderRadius: "4px", alignSelf: "center" }}>SECURE</span>
            </div>

            <div style={{ display: "flex", justifySelf: "stretch", justifyContent: "space-between", padding: "0.75rem", borderRadius: "8px", border: "1px solid var(--border-color)", backgroundColor: "rgba(255,255,255,0.01)" }}>
              <div>
                <p style={{ fontSize: "0.85rem", fontWeight: "600" }}>PII Leakage Scanning</p>
                <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                  {reports.safety_guardrails.metrics.pii_leakage_detected ? "PII Exposure identified" : "No PII elements leaked"}
                </p>
              </div>
              <span style={{ fontSize: "0.7rem", backgroundColor: "var(--accent-emerald-glow)", color: "var(--accent-emerald)", padding: "0.2rem 0.4rem", borderRadius: "4px", alignSelf: "center" }}>SECURE</span>
            </div>

            <div style={{ display: "flex", justifySelf: "stretch", justifyContent: "space-between", padding: "0.75rem", borderRadius: "8px", border: "1px solid var(--border-color)", backgroundColor: "rgba(255,255,255,0.01)" }}>
              <div>
                <p style={{ fontSize: "0.85rem", fontWeight: "600" }}>Toxicity Score</p>
                <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>Average baseline: {reports.safety_guardrails.metrics.toxicity_score}</p>
              </div>
              <span style={{ fontSize: "0.7rem", backgroundColor: "var(--accent-emerald-glow)", color: "var(--accent-emerald)", padding: "0.2rem 0.4rem", borderRadius: "4px", alignSelf: "center" }}>0.05 / 0.1</span>
            </div>
          </div>
        </div>

        {/* Diagnostic OpenTelemetry waterfall */}
        <div className="glass-card" style={{ display: "flex", flexDirection: "column" }}>
          <h3 style={{ fontSize: "1.1rem", marginBottom: "1rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <Terminal size={18} style={{ color: "var(--accent-amber)" }} /> OpenTelemetry Diagnostic Waterfall Traces
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", flexGrow: 1, justifyContent: "center" }}>
            {/* Span 1: Gateway */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "var(--text-secondary)", marginBottom: "0.2rem" }}>
                <span>POST /api/guardroute/chat</span>
                <span>1240ms</span>
              </div>
              <div style={{ width: "100%", height: "8px", backgroundColor: "rgba(255,255,255,0.05)", borderRadius: "4px" }}>
                <div style={{ width: "100%", height: "100%", backgroundColor: "var(--accent-indigo)", borderRadius: "4px" }} />
              </div>
            </div>

            {/* Span 2: Intent Classification */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "var(--text-secondary)", marginBottom: "0.2rem" }}>
                <span>POST /infer/classify</span>
                <span>120ms (start offset: 30ms)</span>
              </div>
              <div style={{ width: "100%", height: "8px", backgroundColor: "rgba(255,255,255,0.05)", borderRadius: "4px", position: "relative" }}>
                <div style={{ position: "absolute", left: "10%", width: "15%", height: "100%", backgroundColor: "var(--accent-cyan)", borderRadius: "4px" }} />
              </div>
            </div>

            {/* Span 3: Subagent Execution */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "var(--text-secondary)", marginBottom: "0.2rem" }}>
                <span>RestrictedPython Code Execution</span>
                <span>340ms (start offset: 160ms)</span>
              </div>
              <div style={{ width: "100%", height: "8px", backgroundColor: "rgba(255,255,255,0.05)", borderRadius: "4px", position: "relative" }}>
                <div style={{ position: "absolute", left: "20%", width: "35%", height: "100%", backgroundColor: "var(--accent-emerald)", borderRadius: "4px" }} />
              </div>
            </div>

            {/* Span 4: Synthesis */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "var(--text-secondary)", marginBottom: "0.2rem" }}>
                <span>Completion synthesis</span>
                <span>650ms (start offset: 520ms)</span>
              </div>
              <div style={{ width: "100%", height: "8px", backgroundColor: "rgba(255,255,255,0.05)", borderRadius: "4px", position: "relative" }}>
                <div style={{ position: "absolute", left: "45%", width: "55%", height: "100%", backgroundColor: "var(--accent-amber)", borderRadius: "4px" }} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
