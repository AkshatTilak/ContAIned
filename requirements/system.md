# System & Core Infrastructure Requirements Checklist

This document details the system-level architectures, environment configurations, database connections, and message queue guidelines that unify the components in the monorepo.

---

## 1. Monorepo Integration Rules
- [x] **Strict Process Separation:**
  - The API Gateway and all project submodules must run on CPU-only.
  - The Inference Server must load all deep learning weights.
  - Submodules must never import or call torch/transformers models directly; all execution must go through the typed `InferenceClient`.
- [x] **Dynamic Plug-and-Play Lifecycles:**
  - The Gateway must discover active modules via the `ACTIVE_PROJECTS` array in the environment.
  - The Gateway lifespan setup hooks (`setup.py` files) must trigger collection checks and database setups at start time.
  - If a project directory is missing or has unmet dependencies, log a warning and skip — do not crash the gateway.
- [x] **Shared Database Namespacing:**
  - All submodules share the same PostgreSQL database, Neo4j instance, and Qdrant cluster.
  - SQL tables must use submodule prefixes (`syntraflow_`, `guardroute_`, `evalops_`, `model_registry_`).
  - Neo4j node labels must be namespaced with project prefixes (`SyntraFlow_Entity`, `SyntraFlow_RELATION`).
- [x] **Model Configuration via Registry:**
  - All model references must be resolved through the Model Registry (see `requirements/models.md`).
  - Submodules must not hardcode model names, dimensions, or provider strings.

---

## 2. Environment Configuration Specifications
Create and maintain a central `.env` file at the monorepo root containing the following parameters:

### [ ] Server & Environment Setup
- [ ] `APP_NAME="Akshat AI Platform"` (Display name)
- [ ] `APP_ENV="development"` (development/production/testing)
- [ ] `APP_HOST="0.0.0.0"`
- [ ] `APP_PORT=8000` (Gateway port)
- [ ] `INFERENCE_SERVER_URL="http://localhost:8010"` (Inference server URL)
- [ ] `INFERENCE_SERVER_PORT=8010` (Explicit inference port)
- [ ] `ACTIVE_PROJECTS=["syntraflow", "guardroute", "evalops"]` (JSON list of active modules)
- [ ] `LOG_LEVEL="INFO"` (Log verbosity: DEBUG, INFO, WARNING, ERROR)

### [ ] External AI Provider APIs
- [ ] `GOOGLE_API_KEY="your-gemini-key"` (Primary completion model — Gemini)
- [ ] `OPENROUTER_API_KEY="your-openrouter-key"` (Aggregator fallback tier)
- [ ] `GROQ_API_KEY="your-groq-key"` (Fast inference fallback — Groq LPU)
- [ ] `CEREBRAS_API_KEY="your-cerebras-key"` (High-volume fallback — Cerebras)
- [ ] `OPENAI_API_KEY="your-openai-key"` (Used by DeepEval QA tests)

### [ ] Storage Connections
- [ ] `DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/contained"` (Async SQL — must use `asyncpg` driver)
- [ ] `QDRANT_URL="http://localhost:6333"` (Vector Store URL)
- [ ] `QDRANT_API_KEY=""` (Optional security token)
- [ ] `NEO4J_URL="bolt://localhost:7687"` (Graph Database URL)
- [ ] `NEO4J_USER="neo4j"`
- [ ] `NEO4J_PASSWORD="password"`
- [ ] `REDIS_URL="redis://localhost:6379"` (Cache, sessions, lightweight pub/sub)

### [ ] Model Selection Overrides
- [ ] `OCR_MODEL="glm"` (Active OCR model — see `requirements/models.md` for options)
- [ ] `ASR_MODEL="sensevoice"` (Active ASR model)
- [ ] `EMBEDDING_MODEL="jina"` (Active embedding model)
- [ ] `CLASSIFIER_MODEL="arch"` (Active task classifier model)
- [ ] `COMPLETION_MODEL="gemini"` (Active LLM completion provider)
- [ ] `OCR_PROVIDER="api"` (Legacy compat: `local` for local OCR or `api` for cloud OCR)

### [ ] Inference Server Configurations
- [ ] `VRAM_BUDGET_MB=20000` (Maximum VRAM budget in MB — adjust for your GPU)
- [ ] `CLASSIFIER_IDLE_TIMEOUT=300` (Model VRAM eviction timeout in seconds)
- [ ] `DEVICE="auto"` (Device selection: `auto`, `cuda`, `cpu`)

### [ ] HuggingFace Hub
- [ ] `HF_HOME="~/.cache/huggingface/hub"` (Model weight cache directory)
- [ ] `HF_HUB_ENABLE_HF_TRANSFER=1` (Faster downloads)
- [ ] `HF_HUB_OFFLINE=0` (Set to 1 for air-gapped deployments)
- [ ] `HF_TOKEN=""` (Token for gated model access)
- [ ] `MODEL_CACHE_DIR="./models"` (Custom cache for GGUF and non-HF files)

### [ ] Security
- [ ] `AUTH_ENABLED=false` (Toggle API key authentication)
- [ ] `CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]` (CORS allowlist)

### [ ] Observability & Tracing
- [ ] `OTEL_SERVICE_NAME="akshat-platform"`
- [ ] `OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4317"` (Jaeger or OTEL Collector)
- [ ] `LANGSMITH_TRACING=false` (Toggle LangSmith LLM tracing)
- [ ] `LANGSMITH_API_KEY=""`
- [ ] `LANGSMITH_PROJECT="akshat-platform"`

---

## 3. Database & Message Queue Setup

### [x] PostgreSQL Services (Relational)
- [x] Use **asynchronous** SQLAlchemy engine (`create_async_engine` with `asyncpg` driver).
- [x] Setup schema migrations using **Alembic** rather than executing programmatic startup `create_all()`.
  - [x] Add `alembic.ini` and `migrations/` directory at the monorepo root.
  - [x] Each submodule maintains migration revisions with prefixed IDs.
- [x] Verify connection pooling configurations (`pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`) to handle concurrent subagent requests.
- [x] Implement retry/backoff on startup if database is not yet ready.

### [x] Qdrant Services (Vector RAG)
- [x] Maintain the collection named `syntraflow_chunks_v1`.
- [x] Vector dimension is **dynamically determined** by the active embedding model (see `requirements/models.md`):
  - jina-clip-v2: 1024
  - nomic-embed-vision-v2: 768
  - Gemini Embedding 2: configurable up to 3072
- [x] Distance metric: **Cosine**.
- [x] On startup, validate that the existing collection dimension matches the active embedding model. Warn if mismatched.

### [x] Neo4j Services (GraphRAG)
- [x] Implement the shared Neo4j client in `common/clients/neo4j.py` (currently missing).
- [x] Verify read-only query protections in tools. All Cypher queries must block write commands (`CREATE`, `MERGE`, `DELETE`, `SET`, `REMOVE`, `DROP`).
- [x] Ensure transaction sessions are closed cleanly after each read-write batch.
- [x] Use parameterized Cypher queries exclusively — no string interpolation.

### [x] Redis Services (Cache & Sessions)
- [x] Maintain a Redis instance at `localhost:6379`.
- [ ] Use for: session storage (GuardRoute conversations), response caching, rate limit state.
- [x] Enable AOF persistence for durability.

### [x] Kafka Services (Asynchronous Messaging)
- [x] Maintain a Kafka broker at `localhost:9092`.
- [x] Add Kafka + ZooKeeper (or KRaft) services to `docker-compose.yml`.
- [x] Maintain the following topics:
  - `syntraflow-ingestion-jobs` (Ingestion queue)
  - `guardroute-traces` (Orchestration spans)
- [x] Add `confluent-kafka` dependency to `guardroute` and `evalops` extras in `pyproject.toml` (currently only in `syntraflow`).
- [ ] Handle Kafka broker offline scenarios gracefully — fall back to local file logging without blocking the user response thread.

---

## 4. Startup & Shutdown Lifecycle

### [ ] Startup Sequence
1. Load `.env` and validate required settings (fail-fast on missing critical keys).
2. Initialize database connections (Postgres, Qdrant, Neo4j, Redis) with retry/backoff.
3. Run Alembic migrations (if `APP_ENV != testing`).
4. Load Model Registry from database; apply environment overrides.
5. Iterate `ACTIVE_PROJECTS`: import `setup.py` hooks, call `init_app_state()`.
6. Mount project API routers dynamically.
7. Start OpenTelemetry instrumentation.
8. Start serving requests.

### [ ] Shutdown Sequence
1. Stop accepting new requests (graceful drain with configurable timeout).
2. Call `shutdown_app_state()` for each active project.
3. Close inference client connections.
4. Commit/flush Kafka producer buffers.
5. Close database connections (Postgres, Neo4j, Redis sessions).
6. Log shutdown confirmation.

### [ ] Graceful Degradation
- [ ] If Neo4j is unavailable: disable GraphRAG features; log warning; vector-only retrieval.
- [ ] If Kafka is unavailable: fall back to local file logging for traces.
- [ ] If Inference Server is unavailable: return `503 Service Unavailable` for model endpoints; cloud-only models still work.
- [ ] If Redis is unavailable: disable caching and rate limiting; log warning.
