# GuardRoute Decision Routing & Orchestration Requirements

GuardRoute classifies query complexity, coordinates parallel subagents using LangGraph, implements fallback routing via LiteLLM, publishes diagnostic logs to Kafka, and manages multi-turn conversations. Model selection is configurable via the Model Registry (see `requirements/models.md`).

---

## 1. Intent & Complexity Classifier Requirements
- [ ] **Configurable Model Routing (via Model Registry):**
  - Route the user's prompt to the inference server `/infer/classify` endpoint.
  - Default local model: `Arch-Router-1.5B` (GGUF). See `requirements/models.md` §6 for alternatives.
  - Alternative: `Semantic Router` (zero VRAM — uses embedding model for cosine similarity routing).
  - Cloud option: `Gemini 3.5 Flash` with structured JSON output.
- [ ] **Complexity Categorization:**
  - **Simple:** Directly route query to the Synthesis Agent.
  - **Medium:** Trigger a single subagent (e.g. RAG retrieval).
  - **Complex:** Trigger a Scatter-Gather graph to execute parallel subagents concurrently.
- [ ] **Rule-Based Fallback:**
  - If the remote classifier endpoint fails or times out, fall back to regex rule-based route classification (e.g., checking if prompt contains keywords like "code", "search", or "retrieve").
- [ ] **Circuit Breaker:**
  - After N consecutive classifier failures (default: 5), automatically bypass the classifier and use rule-based routing for M seconds (default: 60) before retrying.

---

## 2. LangGraph Scatter-Gather Orchestration
- [ ] **Parallel Execution (Scatter):**
  - Concurrently invoke worker subagents based on the classifier's output:
    - **Retrieval Agent:** Queries the SyntraFlow MCP tools.
    - **Coding Agent:** Runs code in a sandboxed environment (see `requirements/security.md` §4).
    - **Web Search Agent:** Fetches live external data via search APIs.
- [ ] **Partial Failures Resolution (Gather):**
  - If a subagent times out or errors, catch the exception, set its status to `ERROR` or `TIMEOUT` in the Graph State, and continue to the Synthesis node.
  - Avoid blocking the entire pipeline due to a single subagent failure.
  - Configurable timeout per subagent: `SUBAGENT_TIMEOUT_SECONDS=30` (env var).
- [ ] **Context Consolidation (Synthesis):**
  - The Synthesis Agent gathers context fragments, cleans formatting, and runs the final completion request using the configured LLM (see §4).
  - Must support **Server-Sent Events (SSE) streaming** for token-by-token output to the frontend.

---

## 3. Worker Agent Tool Connections
- [ ] **Python Execution Sandbox (Coding Subagent):**
  - Use `RestrictedPython` for AST-level sandboxing (lightweight, pip-installable).
  - Block: file I/O, subprocess, network access, `__import__`, `eval`, `exec`.
  - Allow: math, string operations, list comprehensions, basic data structures.
  - Execution timeout: 10 seconds.
  - Memory limit to prevent memory bombs.
  - See `requirements/security.md` §4 for full sandbox specification.
- [ ] **Search Engine Connectors (Web Search Subagent):**
  - Use `duckduckgo-search` library (must be added to `pyproject.toml` guardroute extras).
  - Set tight timeouts (max 2 seconds) to avoid slowing down user chat interactions.
  - Return top 5 results with title, URL, and snippet.

---

## 4. LLM Completion & Provider Fallbacks
- [ ] **Multi-Provider Routing (via Model Registry):**
  - Use `completion_with_fallback()` from `common.clients.litellm` to handle rate limits or API outage events.
  - Primary model: `gemini/gemini-3.5-flash` (configurable via `COMPLETION_MODEL` env var).
  - Default fallback chain (see `requirements/models.md` §7 for full list):
    1. `gemini/gemini-3.5-flash` (Google AI Studio)
    2. `groq/llama-3.3-70b-versatile` (Groq LPU — fast)
    3. `openrouter/google/gemini-3.5-flash:free` (OpenRouter aggregator)
    4. `openrouter/qwen/qwen3-235b:free` (Open-weight fallback)
    5. `openrouter/meta-llama/llama-4-scout:free` (Last resort)
- [ ] **Capability-Aware Context Truncation:**
  - If the fallback chain resolves to a model with a smaller context window, automatically truncate the context payload.
  - Truncation must be in **tokens** (not characters), using `tiktoken` or LiteLLM's built-in token counter.
  - Default limits by tier:
    - Frontier models (Gemini 3.x): No truncation (1M+ context).
    - Mid-tier models (70B class): Truncate to 32,000 tokens.
    - Small free-tier models: Truncate to 8,000 tokens.

---

## 5. Conversation History & Session Management
- [ ] **Session Storage:**
  - Store conversation turns in Redis (keyed by session ID) for fast access.
  - Persist completed conversations to PostgreSQL `guardroute_sessions` table for audit.
- [ ] **Multi-Turn Context:**
  - Maintain a sliding window of conversation history (configurable: default 20 turns).
  - When context exceeds the model's window, summarize older turns using the LLM.
- [ ] **Session Lifecycle:**
  - Create session on first message.
  - Expire inactive sessions after configurable timeout (default: 30 minutes).
  - Support explicit session reset via API.

---

## 6. Streaming Response Support
- [ ] **Server-Sent Events (SSE):**
  - The synthesis agent must stream LLM output token-by-token to the frontend via SSE.
  - Use `sse-starlette` library (must be added to base dependencies in `pyproject.toml`).
  - Endpoint: `POST /api/guardroute/chat` with `Accept: text/event-stream` header.
- [ ] **Metadata Header:**
  - Before streaming tokens, emit a metadata event containing:
    - Complexity classification result.
    - Active subagent list.
    - Classification latency (ms).
    - Model used for synthesis.

---

## 7. Runtime Guardrails (Pre/Post LLM)
- [ ] **Pre-Flight Input Validation:**
  - Scan user prompts for prompt injection patterns before sending to the LLM.
  - Block attempts to override system prompts.
  - See `requirements/security.md` §3 for details.
- [ ] **Post-Flight Output Validation:**
  - Scan LLM output for PII before returning to the user.
  - Optionally check toxicity score (configurable threshold, default: 0.1).
  - See `requirements/security.md` §3 for details.

---

## 8. Async Session Logging & Auditing
- [ ] **Execution Spans Tracing:**
  - On graph completion, construct a trace payload documenting:
    - User prompt.
    - Complexity categorization and confidence.
    - List of subagents executed with individual latencies.
    - Total execution latency (ms).
    - Response text (truncated for storage).
    - Model used for each step (from Registry).
    - Input/output token counts (for cost tracking).
- [ ] **Asynchronous Kafka Writes:**
  - Publish the trace payload to the Kafka topic `guardroute-traces`.
  - Handle Kafka broker offline scenarios gracefully by falling back to local file logging without blocking the user response thread.
- [ ] **Token Usage Tracking:**
  - Track cumulative input/output tokens per session for cost monitoring.
  - Store aggregated usage in `guardroute_usage` PostgreSQL table.

---

## 9. Missing Dependencies (pyproject.toml)
The `guardroute` optional dependency group must include:
```toml
guardroute = [
    "langchain (>=0.3.0,<1.0.0)",
    "langgraph (>=0.2.0,<1.0.0)",
    "mcp (>=0.1.0,<1.0.0)",
    "confluent-kafka (>=2.4.0,<3.0.0)",      # NEW: for trace publishing
    "duckduckgo-search (>=6.0.0,<7.0.0)",    # NEW: web search subagent
    "RestrictedPython (>=7.0,<8.0)",          # NEW: code sandbox
    "sse-starlette (>=2.0.0,<3.0.0)",        # NEW: SSE streaming (or add to base)
    "tiktoken (>=0.7.0,<1.0.0)",             # NEW: token counting
]
```
