import React from "react";
import {
  Cpu,
  Database,
  Activity,
  Zap,
  Server,
  Layers,
  ShieldCheck,
} from "lucide-react";
import { useStore } from "../store/useStore";
import type { SystemHealthResponse, ModelRegistryResponse } from "../types/api";
import { LoadingSkeleton, StatusBadge, ErrorBanner } from "./shared";

interface SystemMetricsProps {
  systemHealth: SystemHealthResponse | null;
  modelRegistry: ModelRegistryResponse | null;
}

export const SystemMetrics: React.FC<SystemMetricsProps> = ({
  systemHealth,
  modelRegistry,
}) => {
  const telemetry = useStore((state) => state.telemetry);

  const services = [
    { name: "Gateway Server", status: systemHealth?.services?.gateway || "connected", icon: Server },
    { name: "Inference Engine", status: systemHealth?.services?.inference_server || "connected", icon: Zap },
    { name: "PostgreSQL Database", status: systemHealth?.services?.database || "connected", icon: Database },
    { name: "Redis Cache & PubSub", status: systemHealth?.services?.redis || "connected", icon: Activity },
    { name: "Apache Kafka", status: systemHealth?.services?.kafka || "connected", icon: Layers },
    { name: "Qdrant Vector DB", status: systemHealth?.services?.qdrant || "connected", icon: ShieldCheck },
  ];

  const isDegraded = telemetry.status !== 'healthy' && telemetry.status !== 'connected';

  if (!systemHealth) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <LoadingSkeleton variant="card" count={4} />
        </div>
        <LoadingSkeleton variant="chart" count={1} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {isDegraded && (
        <ErrorBanner
          title="Telemetry Alert"
          message={`Telemetry report status is currently '${telemetry.status}'. Metrics may be delayed.`}
        />
      )}

      {/* Real-time Telemetry Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* CPU Usage */}
        <div
          className="p-5 rounded-xl border space-y-3 transition-all"
          style={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border-default)' }}
        >
          <div className="flex items-center justify-between text-[var(--text-secondary)]">
            <span className="text-xs font-semibold uppercase tracking-wider font-display">CPU Utilization</span>
            <Cpu className="w-4 h-4 text-[var(--accent-emerald)]" />
          </div>
          <div className="text-2xl font-bold text-[var(--text-primary)] font-display">
            {telemetry.cpu_usage_percent.toFixed(1)}%
          </div>
          <div className="w-full bg-[var(--bg-elevated)] rounded-full h-1.5 overflow-hidden">
            <div
              className="bg-[var(--accent-emerald)] h-1.5 rounded-full transition-all duration-500"
              style={{ width: `${Math.min(telemetry.cpu_usage_percent, 100)}%` }}
            />
          </div>
        </div>

        {/* System Memory */}
        <div
          className="p-5 rounded-xl border space-y-3 transition-all"
          style={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border-default)' }}
        >
          <div className="flex items-center justify-between text-[var(--text-secondary)]">
            <span className="text-xs font-semibold uppercase tracking-wider font-display">Memory Usage</span>
            <Activity className="w-4 h-4 text-[var(--accent-indigo)]" />
          </div>
          <div className="text-2xl font-bold text-[var(--text-primary)] font-display">
            {telemetry.memory_usage_percent.toFixed(1)}%
          </div>
          <div className="w-full bg-[var(--bg-elevated)] rounded-full h-1.5 overflow-hidden">
            <div
              className="bg-[var(--accent-indigo)] h-1.5 rounded-full transition-all duration-500"
              style={{ width: `${Math.min(telemetry.memory_usage_percent, 100)}%` }}
            />
          </div>
        </div>

        {/* VRAM Utilization */}
        <div
          className="p-5 rounded-xl border space-y-3 transition-all"
          style={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border-default)' }}
        >
          <div className="flex items-center justify-between text-[var(--text-secondary)]">
            <span className="text-xs font-semibold uppercase tracking-wider font-display">VRAM Allocation</span>
            <Zap className="w-4 h-4 text-[var(--accent-amber)]" />
          </div>
          <div className="text-2xl font-bold text-[var(--text-primary)] font-display">
            {telemetry.vram_usage_mb} <span className="text-xs text-[var(--text-muted)] font-normal">/ {telemetry.vram_total_mb} MB</span>
          </div>
          <div className="w-full bg-[var(--bg-elevated)] rounded-full h-1.5 overflow-hidden">
            <div
              className="bg-[var(--accent-amber)] h-1.5 rounded-full transition-all duration-500"
              style={{ width: `${Math.min((telemetry.vram_usage_mb / telemetry.vram_total_mb) * 100, 100)}%` }}
            />
          </div>
        </div>

        {/* Active Agents */}
        <div
          className="p-5 rounded-xl border space-y-3 transition-all"
          style={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border-default)' }}
        >
          <div className="flex items-center justify-between text-[var(--text-secondary)]">
            <span className="text-xs font-semibold uppercase tracking-wider font-display">Active Agents</span>
            <Server className="w-4 h-4 text-[var(--accent-cyan)]" />
          </div>
          <div className="text-2xl font-bold text-[var(--text-primary)] font-display flex items-center gap-2">
            {telemetry.active_agents}
            <StatusBadge variant="success" label="Running" size="sm" />
          </div>
          <div className="text-xs text-[var(--text-muted)] mt-1">
            System status: <span className="text-[var(--accent-emerald)] font-medium">{telemetry.status}</span>
          </div>
        </div>
      </div>

      {/* Microservices Health Section */}
      <div
        className="p-5 rounded-xl border"
        style={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border-default)' }}
      >
        <h2 className="text-xs font-bold text-[var(--text-primary)] mb-4 uppercase tracking-wider font-display">
          Platform Microservices Health
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {services.map((s) => {
            const Icon = s.icon;
            const isOk = s.status === "connected" || s.status === "active";
            return (
              <div
                key={s.name}
                className="flex items-center justify-between p-3 rounded-lg border transition-colors"
                style={{
                  backgroundColor: 'var(--bg-surface-alt)',
                  borderColor: 'var(--border-subtle)',
                }}
              >
                <div className="flex items-center gap-3">
                  <Icon className="w-4 h-4 text-[var(--text-muted)]" />
                  <span className="text-xs font-medium text-[var(--text-primary)]">{s.name}</span>
                </div>
                <StatusBadge
                  variant={isOk ? 'success' : 'warning'}
                  label={isOk ? 'Active' : s.status}
                  size="sm"
                />
              </div>
            );
          })}
        </div>
      </div>

      {/* Model Registry Overview */}
      <div
        className="p-5 rounded-xl border"
        style={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border-default)' }}
      >
        <h2 className="text-xs font-bold text-[var(--text-primary)] mb-4 uppercase tracking-wider font-display">
          Loaded Local LLM & Multi-Modal Models
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div
            className="p-4 rounded-lg border"
            style={{ backgroundColor: 'var(--bg-surface-alt)', borderColor: 'var(--border-subtle)' }}
          >
            <div className="text-xs text-[var(--text-muted)] font-medium mb-1">OCR Model</div>
            <div className="text-sm font-bold text-[var(--text-primary)]">
              {modelRegistry?.ocr?.active?.display_name || "GLM-OCR (0.9B)"}
            </div>
            <div className="text-xs text-[var(--accent-emerald)] mt-2 font-mono">
              Mode: Local PyTorch (2000 MB VRAM)
            </div>
          </div>

          <div
            className="p-4 rounded-lg border"
            style={{ backgroundColor: 'var(--bg-surface-alt)', borderColor: 'var(--border-subtle)' }}
          >
            <div className="text-xs text-[var(--text-muted)] font-medium mb-1">ASR Transcription</div>
            <div className="text-sm font-bold text-[var(--text-primary)]">
              {modelRegistry?.asr?.active?.display_name || "SenseVoice-Small"}
            </div>
            <div className="text-xs text-[var(--accent-emerald)] mt-2 font-mono">
              Mode: FunASR (250 MB VRAM)
            </div>
          </div>

          <div
            className="p-4 rounded-lg border"
            style={{ backgroundColor: 'var(--bg-surface-alt)', borderColor: 'var(--border-subtle)' }}
          >
            <div className="text-xs text-[var(--text-muted)] font-medium mb-1">Multi-Modal Embedding</div>
            <div className="text-sm font-bold text-[var(--text-primary)]">
              {modelRegistry?.embedding?.active?.display_name || "Jina Clip v2 (1024d)"}
            </div>
            <div className="text-xs text-[var(--accent-emerald)] mt-2 font-mono">
              Mode: HuggingFace (1000 MB VRAM)
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SystemMetrics;
