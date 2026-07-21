import { useStore } from '../store/useStore';
import type { SystemTelemetryMessage } from '../types/telemetry';

const STORAGE_KEY = "contained-settings";

function getGatewayUrls(): { wsUrl: string; sseUrl: string } {
  let baseUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed.gatewayUrl) {
        baseUrl = parsed.gatewayUrl;
      }
    }
  } catch {
    // fallback
  }

  // Parse URL
  try {
    const parsedUrl = new URL(baseUrl);
    const wsProtocol = parsedUrl.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${wsProtocol}//${parsedUrl.host}/api/telemetry/ws`;
    const sseUrl = `${parsedUrl.protocol}//${parsedUrl.host}/api/telemetry/stream`;
    return { wsUrl, sseUrl };
  } catch {
    return {
      wsUrl: "ws://localhost:8000/api/telemetry/ws",
      sseUrl: "http://localhost:8000/api/telemetry/stream",
    };
  }
}

class TelemetryService {
  private socket: WebSocket | null = null;
  private sse: EventSource | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  public connect(): void {
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const { wsUrl } = getGatewayUrls();

    try {
      this.socket = new WebSocket(wsUrl);

      this.socket.onopen = () => {
        console.log('[TelemetryService] Connected to Gateway WebSocket');
        useStore.getState().setConnectionStatus(true);
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
      };

      this.socket.onmessage = (event: MessageEvent) => {
        try {
          const data: SystemTelemetryMessage = JSON.parse(event.data);
          useStore.getState().setTelemetry(data);
        } catch (err) {
          console.error('[TelemetryService] Failed to parse message', err);
        }
      };

      this.socket.onerror = (err) => {
        console.warn('[TelemetryService] WebSocket error, attempting SSE fallback', err);
        this.socket?.close();
        this.connectSSE();
      };

      this.socket.onclose = () => {
        useStore.getState().setConnectionStatus(false);
        this.scheduleReconnect();
      };
    } catch (err) {
      console.warn('[TelemetryService] Connection failed, attempting SSE fallback', err);
      this.connectSSE();
    }
  }

  private connectSSE(): void {
    if (this.sse) return;
    const { sseUrl } = getGatewayUrls();
    try {
      this.sse = new EventSource(sseUrl);
      this.sse.onopen = () => {
        useStore.getState().setConnectionStatus(true);
      };
      this.sse.onmessage = (event) => {
        try {
          const data: SystemTelemetryMessage = JSON.parse(event.data);
          useStore.getState().setTelemetry(data);
        } catch (err) {
          console.error('[TelemetryService] Failed to parse SSE data', err);
        }
      };
      this.sse.onerror = () => {
        useStore.getState().setConnectionStatus(false);
        this.sse?.close();
        this.sse = null;
        this.scheduleReconnect();
      };
    } catch (err) {
      console.error('[TelemetryService] SSE connection failed', err);
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, 5000);
  }

  public disconnect(): void {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.socket) this.socket.close();
    if (this.sse) this.sse.close();
    this.socket = null;
    this.sse = null;
    useStore.getState().setConnectionStatus(false);
  }
}

export const telemetryService = new TelemetryService();
