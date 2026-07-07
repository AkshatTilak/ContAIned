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

### [x] PostgreSQL Client (`postgres.py`)
- [x] **Fix Critical Bug:** Switch from synchronous `create_engine()` to `create_async_engine()` from `sqlalchemy.ext.asyncio`.
- [x] Use `AsyncSession` throughout (compatible with `asyncpg` driver in `DATABASE_URL`).
- [x] Maintain connection pooling: `pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`.
- [x] Provide `get_async_db()` FastAPI dependency generator yielding `AsyncSession`.
- [x] Handle connection failures with retry/backoff on startup.

### [x] Qdrant Client (`qdrant.py`)
- [x] Maintain the existing `VectorClient` wrapper.
- [x] Add configurable timeout and retry policy.
- [x] Add `async_search_similarity()` for non-blocking searches.
- [x] Accept vector dimension dynamically from the Model Registry.

### [x] Neo4j Client (`neo4j.py`) — NEW
- [x] Create `common/clients/neo4j.py` wrapping the `neo4j` Python driver.
- [x] Provide connection pooling with configurable session lifecycle management.
- [x] Implement **read-only mode enforcement**: block Cypher commands containing `CREATE`, `MERGE`, `DELETE`, `SET`, `REMOVE`, `DROP` for read-only tools.
- [x] Provide parameterized query helpers to prevent Cypher injection.
- [x] Handle graceful connection failure with retry logic.
- [x] Provide `get_neo4j_session()` dependency generator.

### [x] Inference Client (`inference.py`)
- [x] **Fix Docstring:** Change `transcribe()` docstring from "Whisper-v3-turbo" to model-agnostic description.
- [x] Update return schema comments to include `emotion` and `audio_events` fields for ASR.
- [x] Add configurable timeout (default: 120s).
- [x] Add retry policy for transient failures (503, connection reset).
- [x] Add circuit breaker: after N consecutive failures, mark inference server as degraded.

### [x] LiteLLM Client (`litellm.py`)
- [x] **Fix Default Model:** Update from `gemini/gemini-1.5-flash` to `gemini/gemini-3.5-flash`.
- [x] **Update Fallback Chain:** Use the Model Registry's fallback configuration instead of hardcoded list.
- [x] Add Groq and Cerebras to the fallback chain.
- [x] Add token counting for cost tracking.
- [x] Add context truncation logic for models with smaller context windows.

### [x] Redis Client (`redis.py`) — NEW
- [x] Create `common/clients/redis.py` wrapping `redis[hiredis]`.
- [x] Provide async Redis client for caching, session storage, and pub/sub.
- [x] Configure connection from `REDIS_URL` setting.

---

## 3. Observability (`common/observability/`)

### [x] Logger (`logger.py`)
- [x] **Fix:** Read `LOG_LEVEL` from settings instead of hardcoding `INFO`.
- [x] Support structured JSON logging for production (`APP_ENV=production`).
- [x] Add request ID correlation to log entries.

### [x] Tracing (`tracing.py`)
- [x] **Fix Critical Bug:** Add `from typing import Optional` import (missing, causes crash).
- [x] Configure OpenTelemetry OTLP export to Jaeger (recommended backend).
- [x] Maintain LangSmith integration toggle for LLM-specific tracing.
- [x] Add span naming conventions: `{project}.{operation}` (e.g., `syntraflow.ingest`, `guardroute.classify`).

---

## 4. Schemas (`common/schemas/`)

### [x] Agent Types (`agent_types.py`)
- [x] Maintain existing schemas: `TaskComplexity`, `SubAgentStatus`, `SubAgentResult`, `ClassificationResult`.
- [x] Add `latency_ms: float` field to `SubAgentResult` for timing.
- [x] Add `model_used: str` field to track which model was used (from Registry).

### [x] Model Registry Types — NEW
- [x] `ModelSpec` — Pydantic model representing a registry entry.
- [x] `ModelRole` — Enum of roles: `OCR`, `ASR`, `EMBEDDING`, `CLASSIFIER`, `COMPLETION`.
- [x] `ModelMode` — Enum: `LOCAL`, `CLOUD`, `AUTO`.

### [x] API Request/Response Schemas — NEW
- [x] Define shared request/response schemas for common API patterns.
- [x] `HealthResponse` — Standardized health check response.
- [x] `ErrorResponse` — Standardized error response with error codes.
- [x] `PaginatedResponse` — Standardized paginated list response.

---

## 5. Dependencies Required

All of the above requires these additions to `pyproject.toml` base dependencies:
```toml
"redis[hiredis] (>=5.0.0,<6.0.0)",
"huggingface-hub (>=0.23.0,<1.0.0)",
"neo4j (>=5.20.0,<6.0.0)",        # move from syntraflow extras to base
```
