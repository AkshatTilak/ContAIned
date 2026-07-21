/**
 * Telemetry WebSocket & SSE Message Types
 */

export interface SystemTelemetryMessage {
  event: string;
  timestamp: number;
  cpu_usage_percent: number;
  memory_usage_percent: number;
  disk_usage_percent?: number;
  vram_usage_mb: number;
  vram_total_mb: number;
  gpu_available?: boolean;
  active_agents: number;
  active_jobs_count?: number;
  status: string;
}
