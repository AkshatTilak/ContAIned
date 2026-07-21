import React from "react";
import {
  Cpu,
  Database,
  Activity,
  Zap,
  Server,
  Layers,
  ShieldCheck,
  CheckCircle2,
  AlertCircle
} from "lucide-react";
import { useStore } from "../store/useStore";

interface SystemMetricsProps {
  systemHealth: any;
  modelRegistry: any;
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

  return (
    <div className="space-y-6">
      {/* Real-time Telemetry Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* CPU Usage */}
        <div className="p-4 rounded-xl bg-[#15171e] border border-[#26282d]">
          <div className="flex items-center justify-between text-zinc-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">CPU Utilization</span>
            <Cpu className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-white">
            {telemetry.cpu_usage_percent.toFixed(1)}%
          </div>
          <div className="w-full bg-[#26282d] rounded-full h-1.5 mt-3 overflow-hidden">
            <div
              className="bg-emerald-400 h-1.5 rounded-full transition-all duration-500"
              style={{ width: `${Math.min(telemetry.cpu_usage_percent, 100)}%` }}
            />
          </div>
        </div>

        {/* System Memory */}
        <div className="p-4 rounded-xl bg-[#15171e] border border-[#26282d]">
          <div className="flex items-center justify-between text-zinc-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Memory Usage</span>
            <Activity className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold text-white">
            {telemetry.memory_usage_percent.toFixed(1)}%
          </div>
          <div className="w-full bg-[#26282d] rounded-full h-1.5 mt-3 overflow-hidden">
            <div
              className="bg-indigo-400 h-1.5 rounded-full transition-all duration-500"
              style={{ width: `${Math.min(telemetry.memory_usage_percent, 100)}%` }}
            />
          </div>
        </div>

        {/* VRAM Utilization */}
        <div className="p-4 rounded-xl bg-[#15171e] border border-[#26282d]">
          <div className="flex items-center justify-between text-zinc-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">VRAM Allocation</span>
            <Zap className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-white">
            {telemetry.vram_usage_mb} <span className="text-sm text-zinc-400 font-normal">/ {telemetry.vram_total_mb} MB</span>
          </div>
          <div className="w-full bg-[#26282d] rounded-full h-1.5 mt-3 overflow-hidden">
            <div
              className="bg-amber-400 h-1.5 rounded-full transition-all duration-500"
              style={{ width: `${Math.min((telemetry.vram_usage_mb / telemetry.vram_total_mb) * 100, 100)}%` }}
            />
          </div>
        </div>

        {/* Active Agents */}
        <div className="p-4 rounded-xl bg-[#15171e] border border-[#26282d]">
          <div className="flex items-center justify-between text-zinc-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Active Agents</span>
            <Server className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-bold text-white">
            {telemetry.active_agents} <span className="text-xs text-emerald-400 font-normal">Running</span>
          </div>
          <div className="text-xs text-zinc-400 mt-2">
            System status: <span className="text-emerald-400 font-medium">{telemetry.status}</span>
          </div>
        </div>
      </div>

      {/* Microservices Health Section */}
      <div className="p-5 rounded-xl bg-[#15171e] border border-[#26282d]">
        <h2 className="text-sm font-semibold text-white mb-4 uppercase tracking-wider">
          Platform Microservices Health
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {services.map((s) => {
            const Icon = s.icon;
            const isOk = s.status === "connected" || s.status === "active";
            return (
              <div key={s.name} className="flex items-center justify-between p-3 rounded-lg bg-[#181a21] border border-[#22252c]">
                <div className="flex items-center gap-3">
                  <Icon className="w-4 h-4 text-zinc-400" />
                  <span className="text-xs font-medium text-zinc-300">{s.name}</span>
                </div>
                {isOk ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                ) : (
                  <AlertCircle className="w-4 h-4 text-amber-400" />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Model Registry Overview */}
      <div className="p-5 rounded-xl bg-[#15171e] border border-[#26282d]">
        <h2 className="text-sm font-semibold text-white mb-4 uppercase tracking-wider">
          Loaded Local LLM & Multi-Modal Models
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 rounded-lg bg-[#181a21] border border-[#22252c]">
            <div className="text-xs text-zinc-400 font-medium mb-1">OCR Model</div>
            <div className="text-sm font-bold text-white">{modelRegistry?.ocr?.active?.display_name || "GLM-OCR (0.9B)"}</div>
            <div className="text-xs text-emerald-400 mt-2">Mode: Local PyTorch (2000 MB VRAM)</div>
          </div>

          <div className="p-4 rounded-lg bg-[#181a21] border border-[#22252c]">
            <div className="text-xs text-zinc-400 font-medium mb-1">ASR Transcription</div>
            <div className="text-sm font-bold text-white">{modelRegistry?.asr?.active?.display_name || "SenseVoice-Small"}</div>
            <div className="text-xs text-emerald-400 mt-2">Mode: FunASR (250 MB VRAM)</div>
          </div>

          <div className="p-4 rounded-lg bg-[#181a21] border border-[#22252c]">
            <div className="text-xs text-zinc-400 font-medium mb-1">Multi-Modal Embedding</div>
            <div className="text-sm font-bold text-white">{modelRegistry?.embedding?.active?.display_name || "Jina Clip v2 (1024d)"}</div>
            <div className="text-xs text-emerald-400 mt-2">Mode: HuggingFace (1000 MB VRAM)</div>
          </div>
        </div>
      </div>
    </div>
  );
};
