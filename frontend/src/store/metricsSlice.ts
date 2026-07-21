export interface TelemetryMetrics {
  cpu_usage_percent: number;
  memory_usage_percent: number;
  vram_usage_mb: number;
  vram_total_mb: number;
  active_agents: number;
  status: string;
  timestamp: number;
}

export interface MetricsSlice {
  telemetry: TelemetryMetrics;
  isConnected: boolean;
  setTelemetry: (metrics: Partial<TelemetryMetrics>) => void;
  setConnectionStatus: (status: boolean) => void;
}

export const createMetricsSlice = (set: any): MetricsSlice => ({
  telemetry: {
    cpu_usage_percent: 0,
    memory_usage_percent: 0,
    vram_usage_mb: 0,
    vram_total_mb: 16384,
    active_agents: 0,
    status: 'connecting',
    timestamp: Date.now(),
  },
  isConnected: false,
  setTelemetry: (metrics) =>
    set((state: any) => ({
      telemetry: { ...state.telemetry, ...metrics },
    })),
  setConnectionStatus: (status) =>
    set(() => ({
      isConnected: status,
    })),
});
