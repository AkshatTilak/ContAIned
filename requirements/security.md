# Security Requirements Checklist

This document details API security, data protection, LLM safety guardrails, and sandbox isolation requirements across the platform.

---

## 1. API Security

### [x] Authentication Middleware
- [x] Implement API key validation middleware on the gateway.
- [x] API keys passed via `X-API-Key` header.
- [x] Toggle via `AUTH_ENABLED=false` (default for local dev) / `AUTH_ENABLED=true` (production).
- [x] When disabled, all requests are allowed without a key.
- [x] When enabled, reject requests without a valid key with `401 Unauthorized`.
- [x] Store valid API keys in PostgreSQL (`api_keys` table) or environment variable for simplicity.

### [x] Rate Limiting
- [x] Apply rate limiting on the gateway using `slowapi` or `fastapi-limiter`.
- [x] Default limits:
  - General endpoints: 100 requests/minute per IP.
  - Inference-proxied endpoints: 30 requests/minute per IP.
  - File upload endpoints: 10 requests/minute per IP.
- [x] Return `429 Too Many Requests` with `Retry-After` header.
- [x] Store rate limit state in Redis for distributed deployments.

### [x] CORS Configuration
- [x] Replace the current `allow_origins=["*"]` with a configurable allowlist.
- [x] Default: `["http://localhost:3000", "http://localhost:5173"]` (development frontends).
- [x] Read from `CORS_ORIGINS` environment variable.
- [x] Production should restrict to the actual frontend domain.

### [x] Request Validation
- [x] Enforce maximum request body size (default: 100 MB for file uploads, 1 MB for JSON payloads).
- [x] Validate `Content-Type` headers on upload endpoints.
- [x] Sanitize filename inputs to prevent path traversal.

---

## 2. Data Security

### [ ] Secret Management
- [ ] `.env` file MUST be in `.gitignore` (verify this is the case).
- [ ] Provide `.env.example` with placeholder values only — never real keys.
- [ ] For production: document Docker secrets or cloud secret manager integration.
- [ ] API keys, database passwords, and provider keys must never appear in logs.

### [ ] PII Handling
- [ ] Ingested documents may contain PII. Ensure PII is not leaked in:
  - API responses (use post-flight PII scanning).
  - Log messages (redact sensitive content in structured logs).
  - Kafka trace payloads (strip PII from user prompts before publishing).
- [ ] EvalOps must include PII leakage detection tests (already specified in evalops.md).

### [ ] Database Security
- [ ] Use parameterized queries exclusively — no string-formatted SQL.
- [ ] PostgreSQL: Use a dedicated user with minimal privileges (not superuser).
- [ ] Neo4j: Read-only mode enforcement in `common/clients/neo4j.py` (block `CREATE`, `MERGE`, `DELETE`, `SET`, `REMOVE`, `DROP`).
- [ ] Qdrant: Use `QDRANT_API_KEY` when exposed to network (not just localhost).

---

## 3. LLM Safety Guardrails

### [ ] Pre-Flight Input Validation
- [ ] **Prompt Injection Detection:**
  - Scan user prompts for known injection patterns before sending to the LLM.
  - Check for attempts to override system prompts (e.g., "ignore previous instructions").
  - Block or flag suspicious inputs.
- [ ] **Input Sanitization:**
  - Strip HTML/script tags from user input.
  - Enforce maximum prompt length (configurable per model context window).

### [ ] Post-Flight Output Validation
- [ ] **PII Scrubbing:**
  - Scan LLM output for email addresses, phone numbers, API keys, SSNs.
  - Redact or replace detected PII before returning to the user.
- [ ] **Toxicity Check:**
  - Optional: Run output through a toxicity classifier.
  - Block or flag responses exceeding toxicity threshold (default: 0.1).
- [ ] **Hallucination Grounding:**
  - When using RAG, validate that the response references the retrieved context.
  - EvalOps faithfulness metric should catch this in CI.

### [ ] MCP / Tool Security
- [ ] `query_database` tool must reject queries on tables not starting with the project prefix (e.g., `syntraflow_`).
- [ ] `query_graph` tool must reject Cypher containing write operations.
- [ ] All MCP tools must use parameterized queries — no raw string interpolation.

---

## 4. Code Execution Sandbox (GuardRoute Coding Agent)

### [x] Sandbox Implementation
- [x] Use `RestrictedPython` as the initial sandbox approach (lightweight, pip-installable).
- [x] `RestrictedPython` compiles Python code with AST-level restrictions:
  - Block: file I/O (`open()`, `os.path`, `pathlib`), subprocess, network access, `__import__`.
  - Allow: math, string operations, list comprehensions, basic data structures.
- [x] Set execution timeout (default: 10 seconds) to prevent infinite loops.
- [x] Set memory limit to prevent memory bombs.

### [x] Future Upgrade Path
- [x] For stronger isolation (if needed): migrate to container-based sandboxing using `docker-py` to spawn ephemeral containers for code execution.
- [x] Alternative: WASM-based sandbox using `pyodide` for browser-compatible execution.

### [x] Sandbox Output Capture
- [x] Capture `stdout` and `stderr` from sandboxed execution.
- [x] Return output as structured result in the `SubAgentResult` schema.
- [x] Truncate output to a maximum length (default: 10,000 characters).

---

## 5. Network Security

### [ ] Internal Service Communication
- [ ] Services within docker-compose communicate via the internal Docker network.
- [ ] Only the gateway and admin tools expose ports to the host.
- [ ] Inference server should NOT be exposed externally — only accessible via the gateway.

### [ ] External API Calls
- [ ] All outbound API calls (Gemini, OpenRouter, Groq) use HTTPS.
- [ ] Set strict timeouts on external calls:
  - LLM completion: 60 seconds.
  - Web search agent: 2 seconds.
  - Inference server internal: 120 seconds.
- [ ] Handle provider outages gracefully via fallback chains.

---

## 6. Audit & Compliance

### [ ] Request Logging
- [ ] Log all API requests (method, path, status code, latency) to structured logs.
- [ ] Do NOT log request/response bodies by default (may contain PII).
- [ ] Optionally enable body logging in development mode only.

### [ ] Security Event Logging
- [ ] Log authentication failures (invalid API keys).
- [ ] Log rate limit violations.
- [ ] Log prompt injection detection triggers.
- [ ] Log sandbox execution attempts and outcomes.
