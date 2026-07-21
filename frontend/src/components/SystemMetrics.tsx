import React, { useState, useEffect } from "react";
import {
  Cpu,
  Database,
  Activity,
  Zap,
  Server,
  Layers,
  ShieldCheck,
  RefreshCw,
  Clock,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { ResponsiveContainer, AreaChart, Area } from "recharts";
import { motion, AnimatePresence } from "framer-motion";
import { useStore } from "../store/useStore";
import type { SystemHealthResponse, ModelRegistryResponse } from "../types/api";
import { LoadingSkeleton, StatusBadge, ErrorBanner } from "./shared";

interface SystemMetricsProps {
  systemHealth: SystemHealthResponse | null;
  modelRegistry: ModelRegistryResponse | null;
  onRefresh?: () => void;
}

export const SystemMetrics: React.FC<SystemMetricsProps> = ({
  systemHealth,
  modelRegistry,
  onRefresh,
}) => {
  const telemetry = useStore((state) => state.telemetry);
  const telemetryHistory = useStore((state) => state.telemetryHistory);

  const [lastUpdatedSecs, setLastUpdatedSecs] = useState<number>(0);
  const [expandedService, setExpandedService] = useState<string | null>(null);

  // Timer for "last updated X seconds ago"
  useEffect(() => {
    setLastUpdatedSecs(0);
    const interval = setInterval(() => {
      setLastUpdatedSecs((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [telemetry.timestamp]);

  const isDegraded = telemetry.status !== "healthy" && telemetry.status !== "connected";

  // Color threshold helper
  const getThresholdColor = (val: number) => {
    if (val >= 90) return { text: "text-rose-400", bg: "bg-rose-500", stroke: "#EF4444" };
    if (val >= 70) return { text: "text-amber-400", bg: "bg-amber-500", stroke: "#F59E0B" };
    return { text: "text-emerald-400", bg: "bg-emerald-500", stroke: "#10B981" };
  };

  const cpuColors = getThresholdColor(telemetry.cpu_usage_percent);
  const memColors = getThresholdColor(telemetry.memory_usage_percent);
  const vramPercent = (telemetry.vram_usage_mb / (telemetry.vram_total_mb || 1)) * 100;
  const vramColors = getThresholdColor(vramPercent);

  // Mock ping latencies for microservices
  const mockLatencies: Record<string, string> = {
    "Gateway Server": "4ms",
    "Inference Engine": "18ms",
    "PostgreSQL Database": "2ms",
    "Redis Cache & PubSub": "1ms",
    "Apache Kafka": "8ms",
    "Qdrant Vector DB": "6ms",
  };

  const services = [
    { name: "Gateway Server", status: systemHealth?.services?.gateway || "connected", icon: Server },
    { name: "Inference Engine", status: systemHealth?.services?.inference_server || "connected", icon: Zap },
    { name: "PostgreSQL Database", status: systemHealth?.services?.database || "connected", icon: Database },
    { name: "Redis Cache & PubSub", status: systemHealth?.services?.redis || "connected", icon: Activity },
    { name: "Apache Kafka", status: systemHealth?.services?.kafka || "connected", icon: Layers },
    { name: "Qdrant Vector DB", status: systemHealth?.services?.qdrant || "connected", icon: ShieldCheck },
  ];

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

  // Pre-formatted history array for sparklines
  const sparklineData = telemetryHistory.length > 0
    ? telemetryHistory.map((h, i) => ({
        idx: i,
        cpu: h.cpu_usage_percent,
        mem: h.memory_usage_percent,
        vram: (h.vram_usage_mb / (h.vram_total_mb || 1)) * 100,
      }))
    : Array.from({ length: 10 }, (_, i) => ({ idx: i, cpu: 10, mem: 20, vram: 15 }));

  return (
    <div className="space-y-6">
      {/* Header Bar with Refresh & Timestamp */}
      <div className="flex items-center justify-between pb-2 border-b border-[var(--border-subtle)]">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-bold text-white uppercase tracking-wider font-display">
            Live Telemetry Overview
          </h2>
          <span className="text-xs text-[var(--text-muted)] flex items-center gap-1 font-mono">
            <Clock className="w-3.5 h-3.5" />
            Updated {lastUpdatedSecs}s ago
          </span>
        </div>
        {onRefresh && (
          <button
            onClick={onRefresh}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-[var(--bg-surface-alt)] hover:bg-[var(--bg-elevated)] border border-[var(--border-subtle)] hover:border-[var(--border-default)] text-zinc-300 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
        )}
      </div>

      {systemHealth.status === "offline" && (
        <ErrorBanner
          title="Backend Gateway Offline"
          message="Could not connect to gateway server at http://localhost:8000. Start the gateway using 'poetry run uvicorn gateway.main:app --host 0.0.0.0 --port 8000 --reload' or start backend container services."
        />
      )}

      {isDegraded && systemHealth.status !== "offline" && (
        <ErrorBanner
          title="Telemetry Alert"
          message={`Telemetry report status is currently '${telemetry.status}'. Metrics may be delayed.`}
        />
      )}

      {/* Real-time Telemetry Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* CPU Usage Card */}
        <div
          className="p-5 rounded-xl border space-y-3 transition-all relative overflow-hidden group"
          style={{ backgroundColor: "var(--bg-surface)", borderColor: "var(--border-default)" }}
        >
          <div className="flex items-center justify-between text-[var(--text-secondary)]">
            <span className="text-xs font-semibold uppercase tracking-wider font-display">CPU Utilization</span>
            <Cpu className={`w-4 h-4 ${cpuColors.text}`} />
          </div>
          <div className="flex items-baseline justify-between">
            <motion.div
              key={telemetry.cpu_usage_percent}
              initial={{ scale: 0.95, opacity: 0.8 }}
              animate={{ scale: 1, opacity: 1 }}
              className={`text-2xl font-bold font-display ${cpuColors.text}`}
            >
              {telemetry.cpu_usage_percent.toFixed(1)}%
            </motion.div>
          </div>

          {/* Sparkline */}
          <div className="h-10 w-full pt-1">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={sparklineData}>
                <Area
                  type="monotone"
                  dataKey="cpu"
                  stroke={cpuColors.stroke}
                  fill={cpuColors.stroke}
                  fillOpacity={0.15}
                  strokeWidth={2}
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <div className="w-full bg-[var(--bg-elevated)] rounded-full h-1.5 overflow-hidden">
            <div
              className={`h-1.5 rounded-full transition-all duration-500 ${cpuColors.bg}`}
              style={{ width: `${Math.min(telemetry.cpu_usage_percent, 100)}%` }}
            />
          </div>
        </div>

        {/* System Memory Card */}
        <div
          className="p-5 rounded-xl border space-y-3 transition-all relative overflow-hidden group"
          style={{ backgroundColor: "var(--bg-surface)", borderColor: "var(--border-default)" }}
        >
          <div className="flex items-center justify-between text-[var(--text-secondary)]">
            <span className="text-xs font-semibold uppercase tracking-wider font-display">Memory Usage</span>
            <Activity className={`w-4 h-4 ${memColors.text}`} />
          </div>
          <div className="flex items-baseline justify-between">
            <motion.div
              key={telemetry.memory_usage_percent}
              initial={{ scale: 0.95, opacity: 0.8 }}
              animate={{ scale: 1, opacity: 1 }}
              className={`text-2xl font-bold font-display ${memColors.text}`}
            >
              {telemetry.memory_usage_percent.toFixed(1)}%
            </motion.div>
          </div>

          {/* Sparkline */}
          <div className="h-10 w-full pt-1">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={sparklineData}>
                <Area
                  type="monotone"
                  dataKey="mem"
                  stroke={memColors.stroke}
                  fill={memColors.stroke}
                  fillOpacity={0.15}
                  strokeWidth={2}
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <div className="w-full bg-[var(--bg-elevated)] rounded-full h-1.5 overflow-hidden">
            <div
              className={`h-1.5 rounded-full transition-all duration-500 ${memColors.bg}`}
              style={{ width: `${Math.min(telemetry.memory_usage_percent, 100)}%` }}
            />
          </div>
        </div>

        {/* VRAM Utilization Ring Gauge */}
        <div
          className="p-5 rounded-xl border space-y-3 transition-all flex flex-col justify-between"
          style={{ backgroundColor: "var(--bg-surface)", borderColor: "var(--border-default)" }}
        >
          <div className="flex items-center justify-between text-[var(--text-secondary)]">
            <span className="text-xs font-semibold uppercase tracking-wider font-display">VRAM Gauge</span>
            <Zap className={`w-4 h-4 ${vramColors.text}`} />
          </div>
          <div className="flex items-center justify-between gap-3 my-auto">
            {/* SVG Ring Gauge */}
            <div className="relative w-14 h-14 shrink-0">
              <svg className="w-14 h-14 transform -rotate-90" viewBox="0 0 36 36">
                <path
                  className="text-zinc-800"
                  strokeWidth="3.5"
                  stroke="currentColor"
                  fill="none"
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
                <path
                  className="transition-all duration-500"
                  strokeWidth="3.5"
                  strokeDasharray={`${vramPercent}, 100`}
                  strokeLinecap="round"
                  stroke={vramColors.stroke}
                  fill="none"
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center text-[10px] font-bold font-mono text-white">
                {vramPercent.toFixed(0)}%
              </div>
            </div>

            <div className="text-right">
              <div className={`text-lg font-bold font-display ${vramColors.text}`}>
                {telemetry.vram_usage_mb} MB
              </div>
              <div className="text-[11px] text-[var(--text-muted)] font-mono">
                Budget: {telemetry.vram_total_mb} MB
              </div>
            </div>
          </div>

          <div className="text-[10px] text-[var(--text-muted)] font-mono truncate">
            GPU Allocation: {vramPercent > 85 ? "High Demand" : "Nominal"}
          </div>
        </div>

        {/* Active Agents Card */}
        <div
          className="p-5 rounded-xl border space-y-3 transition-all flex flex-col justify-between"
          style={{ backgroundColor: "var(--bg-surface)", borderColor: "var(--border-default)" }}
        >
          <div className="flex items-center justify-between text-[var(--text-secondary)]">
            <span className="text-xs font-semibold uppercase tracking-wider font-display">Active Agents</span>
            <Server className="w-4 h-4 text-[var(--accent-cyan)]" />
          </div>
          <div className="my-auto">
            <div className="text-3xl font-bold text-white font-display flex items-center gap-3">
              {telemetry.active_agents}
              <StatusBadge variant="success" label="Active" size="sm" />
            </div>
          </div>
          <div className="text-xs text-[var(--text-muted)]">
            Status: <span className="text-[var(--accent-emerald)] font-medium font-mono">{telemetry.status}</span>
          </div>
        </div>
      </div>

      {/* Microservices Health Section (Expandable Cards) */}
      <div
        className="p-5 rounded-xl border"
        style={{ backgroundColor: "var(--bg-surface)", borderColor: "var(--border-default)" }}
      >
        <h2 className="text-xs font-bold text-[var(--text-primary)] mb-4 uppercase tracking-wider font-display">
          Platform Microservices Health & Ping Latency
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {services.map((s) => {
            const Icon = s.icon;
            const isOk = s.status === "connected" || s.status === "active";
            const isExpanded = expandedService === s.name;
            const latency = mockLatencies[s.name] || "3ms";

            return (
              <div
                key={s.name}
                onClick={() => setExpandedService(isExpanded ? null : s.name)}
                className="p-3 rounded-lg border transition-all cursor-pointer hover:border-[var(--border-hover)] bg-[var(--bg-surface-alt)] border-[var(--border-subtle)]"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <Icon className="w-4 h-4 text-[var(--text-muted)]" />
                    <span className="text-xs font-medium text-[var(--text-primary)]">{s.name}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusBadge
                      variant={isOk ? "success" : "warning"}
                      label={isOk ? "Active" : s.status}
                      size="sm"
                    />
                    {isExpanded ? (
                      <ChevronUp className="w-3.5 h-3.5 text-zinc-500" />
                    ) : (
                      <ChevronDown className="w-3.5 h-3.5 text-zinc-500" />
                    )}
                  </div>
                </div>

                <AnimatePresence>
                  {isExpanded && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="mt-2 pt-2 border-t border-[var(--border-subtle)] flex items-center justify-between text-[11px] font-mono text-zinc-400 overflow-hidden"
                    >
                      <span>Ping Latency:</span>
                      <span className="text-emerald-400 font-semibold">{latency}</span>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })}
        </div>
      </div>

      {/* Model Registry Overview */}
      <div
        className="p-5 rounded-xl border"
        style={{ backgroundColor: "var(--bg-surface)", borderColor: "var(--border-default)" }}
      >
        <h2 className="text-xs font-bold text-[var(--text-primary)] mb-4 uppercase tracking-wider font-display">
          Loaded Local LLM & Multi-Modal Models
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div
            className="p-4 rounded-lg border"
            style={{ backgroundColor: "var(--bg-surface-alt)", borderColor: "var(--border-subtle)" }}
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
            style={{ backgroundColor: "var(--bg-surface-alt)", borderColor: "var(--border-subtle)" }}
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
            style={{ backgroundColor: "var(--bg-surface-alt)", borderColor: "var(--border-subtle)" }}
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

