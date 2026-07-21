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
  telemetryHistory: TelemetryMetrics[];
  isConnected: boolean;
  reconnectAttempts: number;
  lastConnectedAt: number | null;
  setTelemetry: (metrics: Partial<TelemetryMetrics>) => void;
  setConnectionStatus: (status: boolean) => void;
  incrementReconnectAttempts: () => void;
  resetReconnectAttempts: () => void;
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
  telemetryHistory: [],
  isConnected: false,
  reconnectAttempts: 0,
  lastConnectedAt: null,
  setTelemetry: (metrics) =>
    set((state: any) => {
      const updatedTelemetry = { ...state.telemetry, ...metrics };
      const telemetryHistory = [...state.telemetryHistory, updatedTelemetry].slice(-60);
      return {
        telemetry: updatedTelemetry,
        telemetryHistory,
      };
    }),
  setConnectionStatus: (status) =>
    set((state: any) => ({
      isConnected: status,
      lastConnectedAt: status ? Date.now() : state.lastConnectedAt,
      reconnectAttempts: status ? 0 : state.reconnectAttempts,
    })),
  incrementReconnectAttempts: () =>
    set((state: any) => ({
      reconnectAttempts: state.reconnectAttempts + 1,
    })),
  resetReconnectAttempts: () =>
    set(() => ({
      reconnectAttempts: 0,
    })),
});

