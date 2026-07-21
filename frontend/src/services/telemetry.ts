import { useStore } from '../store/useStore';

class TelemetryService {
  private socket: WebSocket | null = null;
  private sse: EventSource | null = null;
  private reconnectTimer: any = null;
  private url: string;

  constructor() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.hostname || 'localhost';
    const port = '8000';
    this.url = `${protocol}//${host}:${port}/api/telemetry/ws`;
  }

  public connect(): void {
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      this.socket = new WebSocket(this.url);

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
          const data = JSON.parse(event.data);
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
    const sseUrl = `http://${window.location.hostname || 'localhost'}:8000/api/telemetry/stream`;
    try {
      this.sse = new EventSource(sseUrl);
      this.sse.onopen = () => {
        useStore.getState().setConnectionStatus(true);
      };
      this.sse.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
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
