/**
 * REST API Client Layer for ContAIned Platform Gateway.
 * Interacts with /api/* routes (System health, Ingestion, Agent Hub CRUD, Workflows, EvalOps).
 */

import { useStore } from "../store/useStore";
import type {
  SystemHealthResponse,
  ModelRegistryResponse,
  AgentResponse,
  AgentCreatePayload,
  AgentUpdatePayload,
  WorkflowResponse,
  WorkflowCreatePayload,
  IngestionResponse,
  IngestionJobResponse,
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
    const storeState = useStore.getState();
    if (storeState?.gatewayUrl) {
      return {
        baseUrl: storeState.gatewayUrl,
        apiKey: storeState.apiKey || "sk_live_default_key",
      };
    }
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

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  retries: number = 3,
  timeoutMs: number = 30000
): Promise<T> {
  const config = getClientConfig();
  const url = `${config.baseUrl}${endpoint}`;

  const token = localStorage.getItem("contained_auth_token");
  const headers: Record<string, string> = {
    "X-API-Key": config.apiKey,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers as Record<string, string> || {}),
  };

  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  let lastError: Error | null = null;

  for (let attempt = 0; attempt < retries; attempt++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal,
      });

      clearTimeout(timer);

      if (!response.ok) {
        let errorMsg = `HTTP Error ${response.status}: ${response.statusText}`;
        try {
          const errJson = await response.json();
          errorMsg = errJson.detail || errJson.message || errorMsg;
        } catch {
          // ignore json parse error
        }

        // Retry on 5xx status codes only
        if (response.status >= 500 && attempt < retries - 1) {
          const backoff = Math.pow(2, attempt) * 1000;
          await new Promise((res) => setTimeout(res, backoff));
          continue;
        }

        const err = new Error(errorMsg);
        try {
          useStore.getState().addNotification({
            type: "error",
            title: `API Request Failed (${response.status})`,
            message: errorMsg,
          });
        } catch {
          // ignore if store not ready
        }
        throw err;
      }

      return await response.json();
    } catch (err: any) {
      clearTimeout(timer);
      const isAbort = err?.name === "AbortError";
      const errorMsg = isAbort
        ? `Request timed out after ${timeoutMs / 1000}s`
        : err?.message || "Network request failed";

      lastError = new Error(errorMsg);

      if (attempt < retries - 1 && !isAbort) {
        const backoff = Math.pow(2, attempt) * 1000;
        await new Promise((res) => setTimeout(res, backoff));
      } else {
        try {
          useStore.getState().addNotification({
            type: "error",
            title: "API Error",
            message: lastError.message,
          });
        } catch {
          // ignore
        }
        throw lastError;
      }
    }
  }

  throw lastError || new Error("Request failed after retries");
}

export const api = {
  // System & Health
  getSystemHealth: () => request<SystemHealthResponse>("/health", {}, 1, 5000),
  getModels: () => request<ModelRegistryResponse>("/api/agents/models"),

  // Agent Hub CRUD & Invocation
  getAgents: () => request<AgentResponse[]>("/api/agents"),
  getAgent: (id: string) => request<AgentResponse>(`/api/agents/${id}`),
  createAgent: (data: AgentCreatePayload) =>
    request<AgentResponse>("/api/agents", { method: "POST", body: JSON.stringify(data) }),
  updateAgent: (id: string, data: AgentUpdatePayload) =>
    request<AgentResponse>(`/api/agents/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteAgent: (id: string) => request<{ status: string; message: string }>(`/api/agents/${id}`, { method: "DELETE" }),
  toggleAgentActive: (id: string) => request<AgentResponse>(`/api/agents/${id}/toggle`, { method: "PATCH" }),
  getAgentStats: (id: string) => request<any>(`/api/agents/${id}/stats`),
  invokeAgent: (idOrSlug: string, prompt: string, sessionId?: string) =>
    request<any>(`/api/agents/${idOrSlug}/invoke`, {
      method: "POST",
      body: JSON.stringify({ prompt, session_id: sessionId }),
    }),

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
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 60000); // 60s for file uploads

    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "X-API-Key": config.apiKey },
        body: formData,
        signal: controller.signal,
      });
      clearTimeout(timer);
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        const msg = err.detail || "Ingestion request failed";
        useStore.getState().addNotification({
          type: "error",
          title: "Ingestion Failed",
          message: msg,
        });
        throw new Error(msg);
      }
      return res.json();
    } catch (err: any) {
      clearTimeout(timer);
      throw err;
    }
  },

  getDocuments: (limit: number = 10, offset: number = 0) =>
    request<PaginatedDocumentsResponse>(`/api/syntraflow/documents?limit=${limit}&offset=${offset}`),
  getJobs: (status?: string, limit: number = 10, offset: number = 0) => {
    const statusParam = status ? `&status=${status}` : "";
    return request<PaginatedJobsResponse>(`/api/syntraflow/jobs?limit=${limit}&offset=${offset}${statusParam}`);
  },
  getJobStatus: (jobId: string) =>
    request<IngestionJobResponse>(`/api/syntraflow/jobs/${jobId}`),
  getDocumentChunks: (docId: string, limit: number = 20, offset: number = 0) =>
    request<PaginatedChunksResponse>(`/api/syntraflow/documents/${docId}/chunks?limit=${limit}&offset=${offset}`),
  deleteDocument: (docId: string) =>
    request<{ status: string; message: string; deleted_counts: Record<string, number> }>(
      `/api/syntraflow/documents/${docId}`,
      { method: "DELETE" }
    ),

  // EvalOps & Synthetic Generation
  getEvalDashboard: () => request<EvalDashboardResponse>("/api/evalops/dashboard"),
  getDashboardStats: (agentId?: string) =>
    request<any>(`/api/evalops/dashboard/stats${agentId ? `?agent_id=${agentId}` : ""}`),
  getDashboardTrends: (agentId?: string, days: number = 30) =>
    request<any>(`/api/evalops/dashboard/trends?days=${days}${agentId ? `&agent_id=${agentId}` : ""}`),
  getDashboardComparison: () => request<any>("/api/evalops/dashboard/comparison"),

  // EvalOps Test Suite & Case Management (S5-01g)
  listSuites: (agentId?: string) =>
    request<any>(`/api/evalops/suites${agentId ? `?agent_id=${agentId}` : ""}`),
  getSuite: (suiteId: string) => request<any>(`/api/evalops/suites/${suiteId}`),
  createSuite: (data: { agent_id: string; name: string; description?: string }) =>
    request<any>("/api/evalops/suites", { method: "POST", body: JSON.stringify(data) }),
  updateSuite: (suiteId: string, data: { name?: string; description?: string }) =>
    request<any>(`/api/evalops/suites/${suiteId}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteSuite: (suiteId: string) => request<any>(`/api/evalops/suites/${suiteId}`, { method: "DELETE" }),
  cloneSuite: (suiteId: string, newName?: string) =>
    request<any>(`/api/evalops/suites/${suiteId}/clone${newName ? `?new_name=${encodeURIComponent(newName)}` : ""}`, {
      method: "POST",
    }),

  addTestCase: (suiteId: string, data: { input_query: string; expected_output?: string; expected_context?: string }) =>
    request<any>(`/api/evalops/suites/${suiteId}/cases`, { method: "POST", body: JSON.stringify(data) }),
  listTestCases: (suiteId: string) => request<any>(`/api/evalops/suites/${suiteId}/cases`),
  updateTestCase: (caseId: string, data: { input_query?: string; expected_output?: string; expected_context?: string }) =>
    request<any>(`/api/evalops/cases/${caseId}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteTestCase: (caseId: string) => request<any>(`/api/evalops/cases/${caseId}`, { method: "DELETE" }),
  importSuiteCasesJson: (suiteId: string, jsonPayload: any[]) =>
    request<any>(`/api/evalops/suites/${suiteId}/import`, { method: "POST", body: JSON.stringify(jsonPayload) }),
  exportSuiteCases: (suiteId: string) => request<any>(`/api/evalops/suites/${suiteId}/export`),

  // Enhanced Eval Run Trigger & Metric Drill-Down (S5-01h)
  generateSyntheticCases: (agentId: string, count: number = 10) =>
    request<{ status: string; cases: TestCaseResponse[] }>("/api/evalops/generate", {
      method: "POST",
      body: JSON.stringify({ agent_id: agentId, count }),
    }),
  triggerEvalRunEnhanced: (data: {
    agent_id: string;
    suite_id?: string;
    framework?: string;
    metrics?: string[];
    thresholds?: Record<string, number>;
  }) =>
    request<any>("/api/evalops/run", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  triggerEvalRun: (agentId: string, suiteId?: string) =>
    request<EvalRunResponse>("/api/evalops/run", {
      method: "POST",
      body: JSON.stringify({ agent_id: agentId, suite_id: suiteId }),
    }),
  getEvalRuns: (agentId: string) => request<EvalRunResponse[]>(`/api/evalops/runs/${agentId}`),
  getRunMetrics: (runId: string) => request<any>(`/api/evalops/runs/detail/${runId}/metrics`),
  getEvalTestCases: (agentId: string) => request<TestCaseResponse[]>(`/api/evalops/test-cases/${agentId}`),

  // Auth & RBAC
  getMe: () => request<any>("/auth/me"),
  logout: () => request<{ status: string }>("/auth/logout", { method: "POST" }),
  listUsers: () => request<any[]>("/auth/users"),
  updateUserRole: (userId: string, role: string) =>
    request<any>(`/auth/users/${userId}/role`, {
      method: "PUT",
      body: JSON.stringify({ role }),
    }),
  deactivateUser: (userId: string) =>
    request<{ status: string; id: string }>(`/auth/users/${userId}`, {
      method: "DELETE",
    }),
};
