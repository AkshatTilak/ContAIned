# AI Developer Agent: Monorepo Guidelines & Coding Standards

This document outlines the strict guidelines, coding practices, system design patterns, folder structures, and testing rules that AI developer agents must follow when implementing, extending, or refactoring code across the unified **Akshat AI Platform Monorepo** (comprising **SyntraFlow**, **GuardRoute**, and **EvalOps**).

---

## 1. Monorepo System Architecture

The platform is structured as a multi-backend monorepo to separate concerns and prevent resource (VRAM) contention:

```
c:\Akshat\proj\
├── pyproject.toml           # Unified Poetry configuration (base + extras)
├── common/                  # Shared library (imported by all backends/submodules)
│   ├── config/              # Composed Pydantic-settings
│   ├── clients/             # Postgres, Qdrant, LiteLLM, and Inference HTTP clients
│   └── observability/       # Structured logging and OpenTelemetry tracing
├── gateway/                 # Process 1: CPU-only FastAPI API Gateway
├── inference/               # Process 2: GPU-bound Model Inference Server
└── projects/                # Process 3: Submodule directories (SyntraFlow, GuardRoute, EvalOps)
```

### Architectural Principles
1. **Separation of GPU and API Concerns**:
   - The **gateway** is lightweight and CPU-only. It must *never* load model weights.
   - The **inference** server is GPU-bound. It runs as a separate process and manages the local VRAM budget.
   - Submodule projects call model inference by executing HTTP requests to the inference server using `common.clients.inference.InferenceClient`.
2. **Dynamic Plug-and-Play Loader**:
   - Projects in `projects/` act as Git submodules.
   - The gateway dynamically loads active projects at startup by reading `ACTIVE_PROJECTS` from `.env` and executing their `projects/<project>/setup.py` hooks and mounting `projects/<project>/api.py` routers.
3. **Database Schema Isolation**:
   - All submodules share the same `DATABASE_URL` (Postgre), `QDRANT_URL`, and `NEO4J_URL` but must maintain isolated namespace boundaries.
   - SQL operations must use schema namespacing or table prefixes (e.g. `syntraflow_`).
   - Neo4j graph nodes and relations must use submodule prefixes in labels (e.g. `SyntraFlow_Entity`, `SyntraFlow_RELATION`).
   - All MCP endpoints (SQL and Cypher queries) must utilize parameterized dictionaries or predefined cypher structures instead of raw query string inputs to prevent injection.

---

## 2. Shared Library (`common/`)

All backends and submodules must import standard utilities from `common`:

- **Settings**: Import the composed settings singleton:
  ```python
  from common.config import settings
  ```
- **Clients**: Use shared clients to interact with external databases:
  ```python
  from common.clients.postgres import get_db
  from common.clients.qdrant import VectorClient
  ```
- **Inference client**: Submodules must call models asynchronously:
  ```python
  from common.clients.inference import InferenceClient
  
  async def run_pipeline(request: Request):
      client = request.app.state.syntraflow_inference
      ocr_result = await client.ocr(image_bytes)
  ```
- **Observability**: Use the unified logger and tracing setups:
  ```python
  from common.observability.logger import get_logger
  from common.observability.tracing import setup_tracing
  ```

---

## 3. GPU Model Management & VRAM Budgeting

The `inference/` server manages local VRAM allocations via `VRAMManager`:
1. **Lazy Loading**: Models are loaded into VRAM on-demand on the first incoming request and updated with a "last used" timestamp.
2. **LRU Eviction**: If a model load would exceed the VRAM budget (e.g., loading Qwen2.5-VL while Whisper is in VRAM), the manager evicts the least recently used model.
3. **Idle Cleanup**: A background daemon automatically unloads models from VRAM after a configurable idle threshold (default: 5 minutes).

### Model Selection Constraints
When updating model parameters or introducing new pipelines, consult this VRAM budget map:

| Model Role | Selected Model | Target VRAM |
|---|---|---|
| **OCR & Layout** | Baidu Unlimited-OCR (loaded only when `OCR_PROVIDER=local`) | ~4-6 GB |
| **Unified Text & Image Embeddings** | jina-clip-v2 (Multimodal) | ~1 GB |
| **ASR (Transcription)** | SenseVoice-Small (Non-Autoregressive) | ~0.25 GB |
| **Task Routing Classifier** | Arch-Router-1.5B (GGUF) | ~1-2 GB |

---

## 4. LiteLLM Multi-Provider Routing

For external models, GuardRoute calls LiteLLM with a fallback chain configuration:
- **Primary**: Google Gemini Flash API (or Gemini Pro).
- **Secondary Fallbacks**: OpenRouter free-tier endpoints (`openrouter/google/gemini-2.5-flash:free`, `openrouter/meta-llama/llama-3-8b-instruct:free`).
- **Prompt Isolation**: Subagents must adjust their prompt templates depending on the model tier resolved at runtime, ensuring robust behavior when falling back to models with smaller context windows or limited tool calling capabilities.

---

## 5. Development & CI Workflow (EvalOps)

1. **Dependency Installation**: Dependencies are managed via Poetry at the monorepo root. Always run `poetry install --all-extras` during local setup.
2. **Mocking for Local Testing**: For offline testing, spin up the `inference` server which serves mock endpoints representing local models.
3. **DeepEval & RAGAS Integration**:
   - EvalOps runs unit safety tests (hallucination, injection, toxicity checks) on gateway PRs.
   - Retrieval quality is validated using RAGAS benchmarks against Qdrant collection chunks.
