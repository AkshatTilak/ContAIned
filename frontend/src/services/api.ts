/**
 * REST API Client Layer for ContAIned Platform Gateway.
 * Interacts with /api/* routes (System health, Ingestion, Agent Hub CRUD, Workflows, EvalOps).
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = {
    "Content-Type": "application/json",
    "X-API-Key": "sk_live_default_key",
    ...(options.headers || {}),
  };

  const response = await fetch(url, { ...options, headers });
  if (!response.ok) {
    let errorMsg = `HTTP Error ${response.status}: ${response.statusText}`;
    try {
      const errJson = await response.json();
      errorMsg = errJson.detail || errJson.message || errorMsg;
    } catch {
      // ignore json parse error
    }
    throw new Error(errorMsg);
  }
  return response.json();
}

export const api = {
  // System & Health
  getSystemHealth: () => request<any>("/health"),
  getModels: () => request<any>("/api/agents/models"),

  // Agent Hub CRUD
  getAgents: () => request<any[]>("/api/agents"),
  getAgent: (id: string) => request<any>(`/api/agents/${id}`),
  createAgent: (data: any) => request<any>("/api/agents", { method: "POST", body: JSON.stringify(data) }),
  updateAgent: (id: string, data: any) => request<any>(`/api/agents/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteAgent: (id: string) => request<any>(`/api/agents/${id}`, { method: "DELETE" }),

  // Visual Workflows
  getWorkflows: () => request<any[]>("/api/guardroute/workflows"),
  getActiveWorkflow: () => request<any>("/api/guardroute/workflows/active"),
  createWorkflow: (data: any) => request<any>("/api/guardroute/workflows", { method: "POST", body: JSON.stringify(data) }),
  activateWorkflow: (id: string) => request<any>(`/api/guardroute/workflows/${id}/activate`, { method: "PUT" }),

  // SyntraFlow Ingestion
  ingestDocument: async (formData: FormData) => {
    const url = `${API_BASE_URL}/api/syntraflow/ingest`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "X-API-Key": "sk_live_default_key" },
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Ingestion request failed");
    }
    return res.json();
  },

  // EvalOps & Synthetic Generation
  getEvalDashboard: () => request<any>("/api/evalops/dashboard"),
  generateSyntheticCases: (agentId: string, count: number = 10) =>
    request<any>("/api/evalops/generate", {
      method: "POST",
      body: JSON.stringify({ agent_id: agentId, count }),
    }),
  triggerEvalRun: (agentId: string, suiteId?: string) =>
    request<any>("/api/evalops/run", {
      method: "POST",
      body: JSON.stringify({ agent_id: agentId, suite_id: suiteId }),
    }),
  getEvalRuns: (agentId: string) => request<any>(`/api/evalops/runs/${agentId}`),
  getEvalTestCases: (agentId: string) => request<any>(`/api/evalops/test-cases/${agentId}`),
};
