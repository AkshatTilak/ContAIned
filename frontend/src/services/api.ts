/**
 * REST API Client Layer for ContAIned Platform Gateway.
 * Interacts with /api/* and /hubs/* routes.
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
  MCPServer,
  MCPServerCreatePayload,
  MCPServerUpdatePayload,
  MCPTool,
  MCPTestResult,
  Hub,
  HubMember,
  HubLink,
  HubType,
  HubRole,
  HubAccessLevel,
  HubCreatePayload,
  HubUpdatePayload,
  DatastoreBinding,
} from "../types/api";

const STORAGE_KEY = "contained-settings";

export type HubErrorCode =
  | "HUB_NOT_FOUND"
  | "HUB_ROLE_INSUFFICIENT"
  | "HUB_ARCHIVED"
  | "HUB_LINK_REQUIRED"
  | "HUB_LINK_REVOKED";

export class HubApiError extends Error {
  code: HubErrorCode;
  hubId?: string;
  targetHubId?: string;
  status: number;

  constructor(message: string, code: HubErrorCode, status: number, hubId?: string, targetHubId?: string) {
    super(message);
    this.name = "HubApiError";
    this.code = code;
    this.status = status;
    this.hubId = hubId;
    this.targetHubId = targetHubId;
  }
}

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
    ...((options.headers as Record<string, string>) || {}),
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
        let errorCode: HubErrorCode | undefined;
        let hubId: string | undefined;
        let targetHubId: string | undefined;

        try {
          const errJson = await response.json();
          if (errJson.error) {
            errorMsg = errJson.error.message || errorMsg;
            errorCode = errJson.error.code as HubErrorCode;
            hubId = errJson.error.hub_id;
            targetHubId = errJson.error.target_hub_id;
          } else if (errJson.detail) {
            errorMsg = typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail);
          }
        } catch {
          // ignore json parse error
        }

        if (errorCode) {
          throw new HubApiError(errorMsg, errorCode, response.status, hubId, targetHubId);
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

      if (response.status === 240 || response.status === 204) {
        return {} as T;
      }

      return await response.json();
    } catch (err: any) {
      clearTimeout(timer);
      if (err instanceof HubApiError) {
        throw err;
      }
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
  getSystemHealth: () => request<SystemHealthResponse>("/health", {}, 1, 15000),
  getModels: () => request<ModelRegistryResponse>("/api/models"),
  localModels: {
    status: () => request<any>("/api/models/local/status"),
    start: (modelId: string) => request<any>(`/api/models/local/${modelId}/start`, { method: "POST" }),
    stop: (modelId: string) => request<any>(`/api/models/local/${modelId}/stop`, { method: "POST" }),
    selectActive: (role: string, modelId: string) =>
      request<any>("/api/models/select", { method: "POST", body: JSON.stringify({ role, model_id: modelId }) }),
    register: (payload: any) =>
      request<any>("/api/models/register", { method: "POST", body: JSON.stringify(payload) }),
    update: (modelId: string, payload: any) =>
      request<any>(`/api/models/${modelId}`, { method: "PUT", body: JSON.stringify(payload) }),
    delete: (modelId: string) =>
      request<any>(`/api/models/${modelId}`, { method: "DELETE" }),
    purgeLocal: (modelId: string, purgeDisk: boolean = false) =>
      request<any>(`/api/models/local/${encodeURIComponent(modelId)}?purge_disk=${purgeDisk}`, { method: "DELETE" }),
    getLiteLLMModels: (provider: string) =>
      request<any>(`/api/models/litellm/available?provider=${encodeURIComponent(provider)}`),
  },

  // Hubs API Namespace
  hubs: {
    list: (opts?: { includeArchived?: boolean }) =>
      request<Hub[]>(`/api/hubs${opts?.includeArchived ? "?include_archived=true" : ""}`),
    get: (_hubType: string, hubId: string) =>
      request<{ hub: Hub; membership: HubMember | null }>(`/api/hubs/${hubId}`),
    create: (payload: HubCreatePayload) =>
      request<Hub>("/api/hubs", { method: "POST", body: JSON.stringify(payload) }),
    update: (hubId: string, payload: HubUpdatePayload) =>
      request<Hub>(`/api/hubs/${hubId}`, { method: "PATCH", body: JSON.stringify(payload) }),
    archive: (hubId: string) =>
      request<Hub>(`/api/hubs/${hubId}/archive`, { method: "POST" }),
    unarchive: (hubId: string) =>
      request<Hub>(`/api/hubs/${hubId}/unarchive`, { method: "POST" }),
    checkSlug: (hubType: HubType, slug: string) =>
      request<{ available: boolean }>(`/api/hubs/slug-available?hub_type=${hubType}&slug=${encodeURIComponent(slug)}`),
    members: {
      list: (hubId: string) => request<HubMember[]>(`/api/hubs/${hubId}/members`),
      invite: (hubId: string, payload: { email: string; hub_role: HubRole }) =>
        request<HubMember>(`/api/hubs/${hubId}/members`, { method: "POST", body: JSON.stringify(payload) }),
      updateRole: (hubId: string, userId: string, hub_role: HubRole) =>
        request<HubMember>(`/api/hubs/${hubId}/members/${userId}`, {
          method: "PATCH",
          body: JSON.stringify({ hub_role }),
        }),
      remove: (hubId: string, userId: string) =>
        request<void>(`/api/hubs/${hubId}/members/${userId}`, { method: "DELETE" }),
    },
    links: {
      list: (hubId: string) => request<HubLink[]>(`/api/hubs/${hubId}/links`),
      create: (hubId: string, payload: { target_hub_id: string; access_level: HubAccessLevel }) =>
        request<HubLink>(`/api/hubs/${hubId}/links`, { method: "POST", body: JSON.stringify(payload) }),
      revoke: (hubId: string, linkId: string) =>
        request<void>(`/api/hubs/${hubId}/links/${linkId}`, { method: "DELETE" }),
      dependents: (hubId: string) => request<HubLink[]>(`/api/hubs/${hubId}/dependents`),
    },
  },

  // Ingestion Hub API Namespace
  ingestion: {
    collections: {
      list: (hubId: string) =>
        request<{ status: string; collections: any[]; count: number }>(`/api/hubs/${hubId}/ingestion/collections`),
      create: (hubId: string, payload: any) =>
        request<{ status: string; collection: any }>(`/api/hubs/${hubId}/ingestion/collections`, {
          method: "POST",
          body: JSON.stringify(payload),
        }),
      get: (hubId: string, collectionId: string) =>
        request<{ status: string; collection: any }>(`/api/hubs/${hubId}/ingestion/collections/${collectionId}`),
      delete: (hubId: string, collectionId: string) =>
        request<{ status: string; message: string }>(`/api/hubs/${hubId}/ingestion/collections/${collectionId}`, {
          method: "DELETE",
        }),
    },
    datastores: {
      list: (hubId: string) => request<DatastoreBinding[]>(`/api/hubs/${hubId}/ingestion/datastores`),
      create: (hubId: string, payload: any) =>
        request<DatastoreBinding>(`/api/hubs/${hubId}/ingestion/datastores`, {
          method: "POST",
          body: JSON.stringify(payload),
        }),
    },
    documents: {
      list: (hubId: string, limit: number = 10, offset: number = 0) =>
        request<PaginatedDocumentsResponse>(`/api/hubs/${hubId}/ingestion/documents?limit=${limit}&offset=${offset}`),
      delete: (hubId: string, docId: string) =>
        request<{ status: string; message: string }>(`/api/hubs/${hubId}/ingestion/documents/${docId}`, {
          method: "DELETE",
        }),
      ingest: async (hubId: string, formData: FormData): Promise<IngestionResponse> => {
        const config = getClientConfig();
        const url = `${config.baseUrl}/api/hubs/${hubId}/ingestion/documents`;
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 60000);
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
            const msg = err.detail || "Ingestion failed";
            throw new Error(msg);
          }
          return res.json();
        } catch (err: any) {
          clearTimeout(timer);
          throw err;
        }
      },
    },
    jobs: {
      list: (hubId: string, status?: string, limit: number = 10, offset: number = 0) =>
        request<PaginatedJobsResponse>(
          `/api/hubs/${hubId}/ingestion/jobs?limit=${limit}&offset=${offset}${status ? `&status=${status}` : ""}`
        ),
      get: (hubId: string, jobId: string) =>
        request<IngestionJobResponse>(`/api/hubs/${hubId}/ingestion/jobs/${jobId}`),
    },
    search: (hubId: string, payload: any) =>
      request<any>(`/api/hubs/${hubId}/ingestion/search`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  },

  // Agent Hub API Namespace
  agents: {
    list: (hubId: string) => request<AgentResponse[]>(`/api/hubs/${hubId}/agents`),
    get: (hubId: string, agentId: string) => request<AgentResponse>(`/api/hubs/${hubId}/agents/${agentId}`),
    create: (hubId: string, data: AgentCreatePayload) =>
      request<AgentResponse>(`/api/hubs/${hubId}/agents`, { method: "POST", body: JSON.stringify(data) }),
    update: (hubId: string, agentId: string, data: AgentUpdatePayload) =>
      request<AgentResponse>(`/api/hubs/${hubId}/agents/${agentId}`, { method: "PUT", body: JSON.stringify(data) }),
    delete: (hubId: string, agentId: string) =>
      request<{ status: string; message: string }>(`/api/hubs/${hubId}/agents/${agentId}`, { method: "DELETE" }),
    invoke: (hubId: string, agentId: string, payload: { prompt: string; session_id?: string }) =>
      request<any>(`/api/hubs/${hubId}/agents/${agentId}/invoke`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  },

  // Workflow Hub API Namespace
  workflows: {
    list: (hubId: string) => request<WorkflowResponse[]>(`/api/hubs/${hubId}/workflows`),
    get: (hubId: string, workflowId: string) =>
      request<WorkflowResponse>(`/api/hubs/${hubId}/workflows/${workflowId}`),
    create: (hubId: string, data: WorkflowCreatePayload) =>
      request<WorkflowResponse>(`/api/hubs/${hubId}/workflows`, { method: "POST", body: JSON.stringify(data) }),
    update: (hubId: string, workflowId: string, data: Partial<WorkflowCreatePayload>) =>
      request<WorkflowResponse>(`/api/hubs/${hubId}/workflows/${workflowId}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    delete: (hubId: string, workflowId: string) =>
      request<any>(`/api/hubs/${hubId}/workflows/${workflowId}`, { method: "DELETE" }),
    run: (hubId: string, workflowId: string, inputData: any) =>
      request<any>(`/api/hubs/${hubId}/workflows/${workflowId}/runs`, {
        method: "POST",
        body: JSON.stringify(inputData),
      }),
    runs: {
      list: (hubId: string, workflowId: string) =>
        request<any[]>(`/api/hubs/${hubId}/workflows/${workflowId}/runs`),
    },
  },

  // Eval Hub API Namespace
  evals: {
    suites: {
      list: (hubId: string, params?: { target_type?: string; target_id?: string; q?: string }) => {
        const query = new URLSearchParams();
        if (params?.target_type) query.append("target_type", params.target_type);
        if (params?.target_id) query.append("target_id", params.target_id);
        if (params?.q) query.append("q", params.q);
        const qs = query.toString();
        return request<any[]>(`/api/hubs/${hubId}/eval/suites${qs ? `?${qs}` : ""}`);
      },
      get: (hubId: string, suiteId: string) => request<any>(`/api/hubs/${hubId}/eval/suites/${suiteId}`),
      create: (hubId: string, data: any) =>
        request<any>(`/api/hubs/${hubId}/eval/suites`, { method: "POST", body: JSON.stringify(data) }),
      update: (hubId: string, suiteId: string, data: any) =>
        request<any>(`/api/hubs/${hubId}/eval/suites/${suiteId}`, { method: "PUT", body: JSON.stringify(data) }),
      delete: (hubId: string, suiteId: string) =>
        request<any>(`/api/hubs/${hubId}/eval/suites/${suiteId}`, { method: "DELETE" }),
      clone: (hubId: string, suiteId: string) =>
        request<any>(`/api/hubs/${hubId}/eval/suites/${suiteId}/clone`, { method: "POST" }),
    },
    cases: {
      list: (hubId: string, suiteId: string) =>
        request<any[]>(`/api/hubs/${hubId}/eval/suites/${suiteId}/cases`),
      add: (hubId: string, suiteId: string, data: any) =>
        request<any>(`/api/hubs/${hubId}/eval/suites/${suiteId}/cases`, {
          method: "POST",
          body: JSON.stringify(data),
        }),
      update: (hubId: string, suiteId: string, caseId: string, data: any) =>
        request<any>(`/api/hubs/${hubId}/eval/suites/${suiteId}/cases/${caseId}`, {
          method: "PUT",
          body: JSON.stringify(data),
        }),
      delete: (hubId: string, suiteId: string, caseId: string) =>
        request<any>(`/api/hubs/${hubId}/eval/suites/${suiteId}/cases/${caseId}`, { method: "DELETE" }),
    },
    runs: {
      create: (hubId: string, payload: { suite_id: string; framework?: string; async?: boolean }) =>
        request<any>(`/api/hubs/${hubId}/eval/runs`, { method: "POST", body: JSON.stringify(payload) }),
      list: (hubId: string, params?: any) => {
        const query = new URLSearchParams(params || {}).toString();
        return request<any[]>(`/api/hubs/${hubId}/eval/runs${query ? `?${query}` : ""}`);
      },
      get: (hubId: string, runId: string) => request<any>(`/api/hubs/${hubId}/eval/runs/${runId}`),
      traces: (hubId: string, runId: string) => request<any>(`/api/hubs/${hubId}/eval/runs/${runId}/traces`),
    },
    dashboard: {
      stats: (hubId: string, params?: any) => {
        const query = new URLSearchParams(params || {}).toString();
        return request<EvalDashboardResponse>(
          `/api/hubs/${hubId}/eval/dashboard/stats${query ? `?${query}` : ""}`
        );
      },
      trends: (hubId: string, days: number = 30) =>
        request<any>(`/api/hubs/${hubId}/eval/dashboard/trends?days=${days}`),
      comparison: (hubId: string) => request<any>(`/api/hubs/${hubId}/eval/dashboard/comparison`),
    },
  },

  // Auth & RBAC
  login: (credentials: { email: string; password: string }) =>
    request<{ access_token: string; token_type: string; user: any }>("/auth/login", {
      method: "POST",
      body: JSON.stringify(credentials),
    }),
  register: (payload: { email: string; password: string; display_name?: string }) =>
    request<{ status: string }>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getMe: () => request<any>("/auth/me"),
  deleteMe: () => request<{ status: string; message: string }>("/auth/me", { method: "DELETE" }),
  logout: () => request<{ status: string }>("/auth/logout", { method: "POST" }),
  listUsers: (params?: {
    status?: string;
    platform_role?: string;
    hub_id?: string;
    q?: string;
    include_deleted?: boolean;
    limit?: number;
    offset?: number;
  }) => {
    const query = new URLSearchParams();
    if (params?.status) query.append("status", params.status);
    if (params?.platform_role) query.append("platform_role", params.platform_role);
    if (params?.hub_id) query.append("hub_id", params.hub_id);
    if (params?.q) query.append("q", params.q);
    if (params?.include_deleted) query.append("include_deleted", "true");
    if (params?.limit) query.append("limit", params.limit.toString());
    if (params?.offset) query.append("offset", params.offset.toString());
    const qs = query.toString();
    return request<any>(`/admin/users${qs ? `?${qs}` : ""}`);
  },
  updateUserRole: (userId: string, platform_role: string) =>
    request<any>(`/admin/users/${userId}`, {
      method: "PATCH",
      body: JSON.stringify({ platform_role }),
    }),
  deactivateUser: (userId: string) =>
    request<any>(`/admin/users/${userId}/suspend`, {
      method: "POST",
    }),
  deleteUser: (userId: string, hard: boolean = false) =>
    request<{ status: string; id: string }>(`/admin/users/${userId}${hard ? "?hard=true" : ""}`, {
      method: "DELETE",
    }),
  approveUser: (userId: string, payload?: { platform_role?: string; hub_grants?: any[] }) =>
    request<any>(`/admin/users/${userId}/approve`, {
      method: "POST",
      body: JSON.stringify(payload || {}),
    }),
  rejectUser: (userId: string, reason?: string) =>
    request<any>(`/admin/users/${userId}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),

  // Playground API
  playgroundChat: (payload: {
    model_id: string;
    messages: any[];
    system_prompt?: string;
    temperature?: number;
    max_tokens?: number;
    attachment_ids?: string[];
    stream?: boolean;
  }) =>
    request<any>("/api/playground/chat", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  uploadPlaygroundFile: async (file: File): Promise<any> => {
    const config = getClientConfig();
    const url = `${config.baseUrl}/api/playground/upload`;
    const formData = new FormData();
    formData.append("file", file);
    const token = localStorage.getItem("contained_auth_token");
    const headers: Record<string, string> = {
      "X-API-Key": config.apiKey,
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
    const res = await fetch(url, { method: "POST", headers, body: formData });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "File upload failed");
    }
    return res.json();
  },
  getPlaygroundAttachment: (id: string) => request<any>(`/api/playground/attachments/${id}`),
  deletePlaygroundAttachment: (id: string) => request<any>(`/api/playground/attachments/${id}`, { method: "DELETE" }),
  listPlaygroundSessions: () => request<any[]>("/api/playground/sessions"),
  createPlaygroundSession: (data: any) =>
    request<any>("/api/playground/sessions", { method: "POST", body: JSON.stringify(data) }),
  getPlaygroundSession: (id: string) => request<any>(`/api/playground/sessions/${id}`),
  updatePlaygroundSession: (id: string, data: any) =>
    request<any>(`/api/playground/sessions/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deletePlaygroundSession: (id: string) => request<any>(`/api/playground/sessions/${id}`, { method: "DELETE" }),

  // MCP Registry APIs
  getMCPServers: () => request<MCPServer[]>("/api/mcp/servers"),
  createMCPServer: (payload: MCPServerCreatePayload) =>
    request<MCPServer>("/api/mcp/servers", { method: "POST", body: JSON.stringify(payload) }),
  updateMCPServer: (id: string, payload: MCPServerUpdatePayload) =>
    request<MCPServer>(`/api/mcp/servers/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteMCPServer: (id: string) => request<void>(`/api/mcp/servers/${id}`, { method: "DELETE" }),
  checkMCPServerHealth: (id: string) => request<any>(`/api/mcp/servers/${id}/health`, { method: "POST" }),
  syncServerTools: (id: string) => request<MCPTool[]>(`/api/mcp/servers/${id}/tools`),
  getAllMCPTools: () => request<MCPTool[]>("/api/mcp/tools"),
  toggleMCPTool: (id: string) => request<any>(`/api/mcp/tools/${id}/toggle`, { method: "PUT" }),
  invokeMCPTool: (payload: { server_id: string; tool_name: string; parameters?: Record<string, any> }) =>
    request<MCPTestResult>("/api/mcp/tools/invoke", { method: "POST", body: JSON.stringify(payload) }),
  testMCPTool: (serverId: string, toolName: string, parameters: Record<string, any>) =>
    request<MCPTestResult>(`/api/mcp/servers/${serverId}/tools/${toolName}/test`, {
      method: "POST",
      body: JSON.stringify({ parameters }),
    }),

  // Admin API Namespace
  admin: {
    users: {
      pending: () => request<any>("/api/admin/users/pending"),
      approve: (userId: string, payload: any) =>
        request<any>(`/api/admin/users/${userId}/approve`, { method: "POST", body: JSON.stringify(payload) }),
      reject: (userId: string, payload: any) =>
        request<any>(`/api/admin/users/${userId}/reject`, { method: "POST", body: JSON.stringify(payload) }),
    },
    invites: {
      list: () => request<any>("/api/admin/invites"),
      resend: (inviteId: string) => request<any>(`/api/admin/invites/${inviteId}/resend`, { method: "POST" }),
      revoke: (inviteId: string) => request<void>(`/api/admin/invites/${inviteId}`, { method: "DELETE" }),
    },
    credentials: {
      list: () => request<any>("/api/settings/credentials"),
      upsert: (payload: { provider: string; api_key: string }) =>
        request<any>("/api/settings/credentials", { method: "POST", body: JSON.stringify(payload) }),
      remove: (provider: string) =>
        request<void>(`/api/settings/credentials/${provider}`, { method: "DELETE" }),
    },
  },
};
