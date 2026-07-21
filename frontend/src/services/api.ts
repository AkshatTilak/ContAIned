/**
 * REST API Client Layer for ContAIned Platform Gateway.
 * Interacts with /api/* routes (System health, Ingestion, Agent Hub CRUD, Workflows, EvalOps).
 */

import {
  SystemHealthResponse,
  ModelRegistryResponse,
  AgentResponse,
  AgentCreatePayload,
  AgentUpdatePayload,
  WorkflowResponse,
  WorkflowCreatePayload,
  IngestionResponse,
  PaginatedJobsResponse,
  PaginatedDocumentsResponse,
  PaginatedChunksResponse,
  EvalDashboardResponse,
  EvalRunResponse,
  TestCaseResponse,
} from "../types/api";

const STORAGE_KEY = "contained-settings";

function getClientConfig(): { baseUrl: string; apiKey: string } {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      return {
        baseUrl: parsed.gatewayUrl || import.meta.env.VITE_API_URL || "http://localhost:8000",
        apiKey: parsed.apiKey || "sk_live_default_key",
      };
    }
  } catch {
    // fallback
  }
  return {
    baseUrl: import.meta.env.VITE_API_URL || "http://localhost:8000",
    apiKey: "sk_live_default_key",
  };
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const config = getClientConfig();
  const url = `${config.baseUrl}${endpoint}`;
  const headers = {
    "Content-Type": "application/json",
    "X-API-Key": config.apiKey,
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
  getSystemHealth: () => request<SystemHealthResponse>("/health"),
  getModels: () => request<ModelRegistryResponse>("/api/agents/models"),

  // Agent Hub CRUD
  getAgents: () => request<AgentResponse[]>("/api/agents"),
  getAgent: (id: string) => request<AgentResponse>(`/api/agents/${id}`),
  createAgent: (data: AgentCreatePayload) =>
    request<AgentResponse>("/api/agents", { method: "POST", body: JSON.stringify(data) }),
  updateAgent: (id: string, data: AgentUpdatePayload) =>
    request<AgentResponse>(`/api/agents/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteAgent: (id: string) => request<{ status: string; message: string }>(`/api/agents/${id}`, { method: "DELETE" }),

  // Visual Workflows
  getWorkflows: () => request<WorkflowResponse[]>("/api/guardroute/workflows"),
  getActiveWorkflow: () => request<WorkflowResponse>("/api/guardroute/workflows/active"),
  createWorkflow: (data: WorkflowCreatePayload) =>
    request<WorkflowResponse>("/api/guardroute/workflows", { method: "POST", body: JSON.stringify(data) }),
  activateWorkflow: (id: string) =>
    request<WorkflowResponse>(`/api/guardroute/workflows/${id}/activate`, { method: "PUT" }),

  // SyntraFlow Ingestion & Documents
  ingestDocument: async (formData: FormData): Promise<IngestionResponse> => {
    const config = getClientConfig();
    const url = `${config.baseUrl}/api/syntraflow/ingest`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "X-API-Key": config.apiKey },
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Ingestion request failed");
    }
    return res.json();
  },
  getDocuments: (limit: number = 10, offset: number = 0) =>
    request<PaginatedDocumentsResponse>(`/api/syntraflow/documents?limit=${limit}&offset=${offset}`),
  getJobs: (status?: string, limit: number = 10, offset: number = 0) => {
    const statusParam = status ? `&status=${status}` : "";
    return request<PaginatedJobsResponse>(`/api/syntraflow/jobs?limit=${limit}&offset=${offset}${statusParam}`);
  },
  getDocumentChunks: (docId: string, limit: number = 20, offset: number = 0) =>
    request<PaginatedChunksResponse>(`/api/syntraflow/documents/${docId}/chunks?limit=${limit}&offset=${offset}`),
  deleteDocument: (docId: string) =>
    request<{ status: string; message: string; deleted_counts: Record<string, number> }>(
      `/api/syntraflow/documents/${docId}`,
      { method: "DELETE" }
    ),

  // EvalOps & Synthetic Generation
  getEvalDashboard: () => request<EvalDashboardResponse>("/api/evalops/dashboard"),
  generateSyntheticCases: (agentId: string, count: number = 10) =>
    request<{ status: string; cases: TestCaseResponse[] }>("/api/evalops/generate", {
      method: "POST",
      body: JSON.stringify({ agent_id: agentId, count }),
    }),
  triggerEvalRun: (agentId: string, suiteId?: string) =>
    request<EvalRunResponse>("/api/evalops/run", {
      method: "POST",
      body: JSON.stringify({ agent_id: agentId, suite_id: suiteId }),
    }),
  getEvalRuns: (agentId: string) => request<EvalRunResponse[]>(`/api/evalops/runs/${agentId}`),
  getEvalTestCases: (agentId: string) => request<TestCaseResponse[]>(`/api/evalops/test-cases/${agentId}`),
};
