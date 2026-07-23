/**
 * API Response & Request DTO Interfaces matching backend Pydantic models.
 */

export interface SystemHealthResponse {
  status: string;
  platform_version?: string;
  environment: string;
  active_projects: string[];
  services: {
    gateway: string;
    inference_server: string;
    database: string;
    redis: string;
    neo4j: string;
    qdrant: string;
    kafka: string;
    [serviceName: string]: string;
  };
  latencies_ms?: Record<string, number>;
  inference_details?: Record<string, any>;
}

export interface ModelRegistryEntry {
  model_id: string;
  display_name: string;
  role: string;
  provider: string;
  is_enabled: boolean;
  is_default: boolean;
}

export interface ModelRegistryResponse {
  [role: string]: {
    active: ModelRegistryEntry | null;
    available: ModelRegistryEntry[];
  };
}

export interface AgentResponse {
  id: string;
  name: string;
  role: string;
  system_prompt: string;
  model_id: string;
  tools: string[];
  temperature: number;
  max_tokens: number;
  created_at: string;
  updated_at: string;
}

export interface AgentCreatePayload {
  name: string;
  role: string;
  system_prompt: string;
  model_id: string;
  tools?: string[];
  temperature?: number;
  max_tokens?: number;
}

export interface AgentUpdatePayload {
  name?: string;
  role?: string;
  system_prompt?: string;
  model_id?: string;
  tools?: string[];
  temperature?: number;
  max_tokens?: number;
}

export interface WorkflowResponse {
  id: string;
  name: string;
  graph_json: Record<string, any>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface WorkflowCreatePayload {
  name: string;
  graph_json: Record<string, any>;
  is_active?: boolean;
}

export interface IngestionResponse {
  status: string;
  job_id?: string;
  document_id?: string;
  filename?: string;
  message?: string;
  skipped?: boolean;
  chunks_count?: number;
  embeddings_count?: number;
}

export interface IngestionJobResponse {
  job_id: string;
  document_id: string | null;
  status: string;
  progress: number;
  error_msg: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface PaginatedJobsResponse {
  status: string;
  total_count: number;
  limit: number;
  offset: number;
  items: IngestionJobResponse[];
}

export interface SyntraFlowDocument {
  id: string;
  filename: string;
  file_hash: string;
  file_type: string;
  created_at: string | null;
}

export interface PaginatedDocumentsResponse {
  status: string;
  total_count: number;
  limit: number;
  offset: number;
  items: SyntraFlowDocument[];
}

export interface DocumentChunk {
  id: string;
  document_id: string;
  chunk_index: number;
  text: string;
  token_count: number;
  metadata?: Record<string, any>;
}

export interface PaginatedChunksResponse {
  status: string;
  document_id: string;
  total_count: number;
  limit: number;
  offset: number;
  items: DocumentChunk[];
}

export interface EvalDashboardResponse {
  total_test_cases: number;
  avg_faithfulness: number;
  avg_relevance: number;
  pass_rate: number;
  recent_runs_count: number;
}

export interface EvalRunResponse {
  id: string;
  agent_id: string;
  suite_id?: string;
  total_cases: number;
  passed_cases: number;
  avg_faithfulness: number;
  avg_relevance: number;
  status: string;
  created_at: string;
}

export interface TestCaseResponse {
  id: string;
  agent_id: string;
  query: string;
  expected_output: string;
  context?: string;
  faithfulness_score?: number;
  answer_relevance_score?: number;
  status?: "pass" | "fail" | "pending";
}

export interface PlaygroundMessage {
  role: "user" | "assistant" | "system";
  content: string;
  tokens?: number;
  attachment_ids?: string[];
}

export interface PlaygroundAttachment {
  attachment_id: string;
  filename: string;
  file_type: string;
  extracted_text_preview?: string;
  extracted_text?: string;
  total_chars?: number;
  created_at: string;
  status?: string;
}

export interface PlaygroundSession {
  id: string;
  user_id?: string | null;
  name: string;
  model_id?: string;
  system_prompt?: string;
  messages: PlaygroundMessage[];
  attachments?: PlaygroundAttachment[];
  temperature?: number;
  max_tokens?: number;
  created_at: string;
  updated_at: string;
}

export interface PlaygroundChatResponse {
  response: string;
  model_used: string;
  input_tokens: number;
  output_tokens: number;
  latency_ms: number;
  status: string;
}

