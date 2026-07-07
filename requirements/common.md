# Shared Library (`common/`) Requirements Checklist

This document details the shared library modules used by all backends and project submodules: configuration, database clients, observability, schemas, and model registry.

---

## 1. Configuration (`common/config/`)

### [x] Pydantic-Settings Composition Pattern
- [x] Use multi-inheritance to compose domain-specific settings classes into a single `Settings` instance.
- [x] All backends and projects must import settings from `common.config.settings`.
- [x] Add new settings classes as parents to the composed `Settings` when adding features.

### [x] Settings Validation on Startup
- [x] Fail-fast if required environment variables are missing (e.g., `DATABASE_URL`).
- [x] Log a warning for optional but recommended variables (e.g., `GOOGLE_API_KEY`).
- [x] Validate `ACTIVE_PROJECTS` entries against available project directories.

### [x] New Settings Fields Required
- [x] `LOG_LEVEL: str = "INFO"` — Configurable log verbosity.
- [x] `VRAM_BUDGET_MB: int = 20000` — GPU memory budget (currently hardcoded).
- [x] `REDIS_URL: str = "redis://localhost:6379"` — Redis connection.
- [x] `CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]` — CORS allowlist.
- [x] `AUTH_ENABLED: bool = False` — Toggle API key authentication.
- [x] `GROQ_API_KEY: Optional[str] = None` — Groq provider key.
- [x] `CEREBRAS_API_KEY: Optional[str] = None` — Cerebras provider key.
- [x] `HF_HOME: str = "~/.cache/huggingface/hub"` — HuggingFace cache directory.
- [x] `DEVICE: str = "auto"` — Device selection (auto/cuda/cpu).
- [x] `INFERENCE_SERVER_PORT: int = 8010` — Explicit port field.

### [x] Model Override Settings
- [x] `OCR_MODEL: str = "glm"` — Active OCR model shorthand.
- [x] `ASR_MODEL: str = "sensevoice"` — Active ASR model shorthand.
- [x] `EMBEDDING_MODEL: str = "jina"` — Active embedding model shorthand.
- [x] `CLASSIFIER_MODEL: str = "arch"` — Active classifier model shorthand.
- [x] `COMPLETION_MODEL: str = "gemini"` — Active completion model shorthand.

---

## 2. Database Clients (`common/clients/`)

### [ ] PostgreSQL Client (`postgres.py`)
- [ ] **Fix Critical Bug:** Switch from synchronous `create_engine()` to `create_async_engine()` from `sqlalchemy.ext.asyncio`.
- [ ] Use `AsyncSession` throughout (compatible with `asyncpg` driver in `DATABASE_URL`).
- [ ] Maintain connection pooling: `pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`.
- [ ] Provide `get_async_db()` FastAPI dependency generator yielding `AsyncSession`.
- [ ] Handle connection failures with retry/backoff on startup.

### [ ] Qdrant Client (`qdrant.py`)
- [ ] Maintain the existing `VectorClient` wrapper.
- [ ] Add configurable timeout and retry policy.
- [ ] Add `async_search_similarity()` for non-blocking searches.
- [ ] Accept vector dimension dynamically from the Model Registry.

### [ ] Neo4j Client (`neo4j.py`) — NEW
- [ ] Create `common/clients/neo4j.py` wrapping the `neo4j` Python driver.
- [ ] Provide connection pooling with configurable session lifecycle management.
- [ ] Implement **read-only mode enforcement**: block Cypher commands containing `CREATE`, `MERGE`, `DELETE`, `SET`, `REMOVE`, `DROP` for read-only tools.
- [ ] Provide parameterized query helpers to prevent Cypher injection.
- [ ] Handle graceful connection failure with retry logic.
- [ ] Provide `get_neo4j_session()` dependency generator.

### [ ] Inference Client (`inference.py`)
- [ ] **Fix Docstring:** Change `transcribe()` docstring from "Whisper-v3-turbo" to model-agnostic description.
- [ ] Update return schema comments to include `emotion` and `audio_events` fields for ASR.
- [ ] Add configurable timeout (default: 120s).
- [ ] Add retry policy for transient failures (503, connection reset).
- [ ] Add circuit breaker: after N consecutive failures, mark inference server as degraded.

### [ ] LiteLLM Client (`litellm.py`)
- [ ] **Fix Default Model:** Update from `gemini/gemini-1.5-flash` to `gemini/gemini-3.5-flash`.
- [ ] **Update Fallback Chain:** Use the Model Registry's fallback configuration instead of hardcoded list.
- [ ] Add Groq and Cerebras to the fallback chain.
- [ ] Add token counting for cost tracking.
- [ ] Add context truncation logic for models with smaller context windows.

### [ ] Redis Client (`redis.py`) — NEW
- [ ] Create `common/clients/redis.py` wrapping `redis[hiredis]`.
- [ ] Provide async Redis client for caching, session storage, and pub/sub.
- [ ] Configure connection from `REDIS_URL` setting.

---

## 3. Observability (`common/observability/`)

### [ ] Logger (`logger.py`)
- [ ] **Fix:** Read `LOG_LEVEL` from settings instead of hardcoding `INFO`.
- [ ] Support structured JSON logging for production (`APP_ENV=production`).
- [ ] Add request ID correlation to log entries.

### [ ] Tracing (`tracing.py`)
- [ ] **Fix Critical Bug:** Add `from typing import Optional` import (missing, causes crash).
- [ ] Configure OpenTelemetry OTLP export to Jaeger (recommended backend).
- [ ] Maintain LangSmith integration toggle for LLM-specific tracing.
- [ ] Add span naming conventions: `{project}.{operation}` (e.g., `syntraflow.ingest`, `guardroute.classify`).

---

## 4. Schemas (`common/schemas/`)

### [ ] Agent Types (`agent_types.py`)
- [ ] Maintain existing schemas: `TaskComplexity`, `SubAgentStatus`, `SubAgentResult`, `ClassificationResult`.
- [ ] Add `latency_ms: float` field to `SubAgentResult` for timing.
- [ ] Add `model_used: str` field to track which model was used (from Registry).

### [ ] Model Registry Types — NEW
- [ ] `ModelSpec` — Pydantic model representing a registry entry.
- [ ] `ModelRole` — Enum of roles: `OCR`, `ASR`, `EMBEDDING`, `CLASSIFIER`, `COMPLETION`.
- [ ] `ModelMode` — Enum: `LOCAL`, `CLOUD`, `AUTO`.

### [ ] API Request/Response Schemas — NEW
- [ ] Define shared request/response schemas for common API patterns.
- [ ] `HealthResponse` — Standardized health check response.
- [ ] `ErrorResponse` — Standardized error response with error codes.
- [ ] `PaginatedResponse` — Standardized paginated list response.

---

## 5. Dependencies Required

All of the above requires these additions to `pyproject.toml` base dependencies:
```toml
"redis[hiredis] (>=5.0.0,<6.0.0)",
"huggingface-hub (>=0.23.0,<1.0.0)",
"neo4j (>=5.20.0,<6.0.0)",        # move from syntraflow extras to base
```
