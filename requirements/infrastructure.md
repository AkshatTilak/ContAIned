# Infrastructure & Deployment Requirements Checklist

This document details Docker images, docker-compose services, local development setup, and production deployment guidance.

---

## 1. Docker Images

### [x] Dockerfile.gateway (CPU-only)
- [x] Base: `python:3.11-slim`
- [x] Install Poetry for dependency management.
- [x] Install base + all project extras (syntraflow, guardroute, evalops).
- [x] Install `ffmpeg` binary for media processing (required by SyntraFlow).
- [x] Copy `common/`, `gateway/`, `projects/`, and `inference/__init__.py`.
- [x] Do NOT install GPU packages (`torch`, `transformers`, `paddleocr`).
- [x] Expose port 8000.

### [x] Dockerfile.inference (GPU)
- [x] Base: `nvidia/cuda:12.4.1-runtime-ubuntu22.04`
- [x] Install Python 3.11, Poetry, and system build tools.
- [x] Install base + inference extras (includes `torch`, `transformers`, `llama-cpp-python`).
- [x] Install framework-specific packages based on configured models (`funasr`, `paddleocr`, `surya-ocr`, etc.).
- [x] Copy `common/` and `inference/`.
- [x] Create `/app/models` directory for weight storage (mount as volume at runtime).
- [x] Expose port 8010.

### [x] Image Security & Optimization
- [ ] Use multi-stage builds to reduce final image size.
- [ ] Pin base image versions (avoid `latest` tags in production).
- [ ] Run as non-root user.
- [ ] Add `.dockerignore` to exclude `__pycache__`, `.git`, `.env`, `node_modules`.

---

## 2. docker-compose Services

### [x] Fix Critical Bug: Malformed `deploy.resources`
The inference service has a duplicated `resources` key. Fix:
```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

### [x] Core Services (Default Profile)

#### PostgreSQL
- [x] Image: `postgres:16`
- [x] Port: 5432
- [x] Volume: `pgdata:/var/lib/postgresql/data`
- [x] Healthcheck: `pg_isready -U contained -d contained_platform`
- [x] Environment: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`

#### Qdrant
- [x] Image: `qdrant/qdrant:latest`
- [x] Port: 6333
- [x] Volume: `qdrant_data:/qdrant/storage`
- [x] Healthcheck: HTTP check on `/readyz`

#### Neo4j
- [x] Image: `neo4j:5.20.0`
- [x] Ports: 7474 (HTTP), 7687 (Bolt)
- [x] Volume: `neo4j_data:/data`, `neo4j_logs:/logs`
- [x] Healthcheck: `cypher-shell -u neo4j -p $password RETURN 1`

#### Redis — NEW
- [x] Image: `redis:7-alpine`
- [x] Port: 6379
- [x] Volume: `redis_data:/data`
- [x] Healthcheck: `redis-cli ping`
- [x] Configuration: Enable AOF persistence.

#### Kafka + ZooKeeper — NEW
- [x] Image: `confluentinc/cp-kafka:7.6.0` (or KRaft mode)
- [x] Kafka Port: 9092
- [x] ZooKeeper Port: 2181 (if not using KRaft)
- [x] Volume: `kafka_data:/var/lib/kafka/data`
- [x] Auto-create topics on startup:
  - [x] `syntraflow-ingestion-jobs`
  - [x] `guardroute-traces`
- [x] Healthcheck: Kafka broker readiness check.

#### Gateway
- [x] Build from `Dockerfile.gateway`
- [x] Port: 8000
- [x] Depends on: postgres (healthy), qdrant (started), neo4j (healthy), redis (healthy)
- [x] Environment overrides for container networking (e.g., `DATABASE_URL=postgresql+asyncpg://contained:changeme@postgres:5432/contained_platform`)
- [x] Command: `uvicorn gateway.main:app --host 0.0.0.0 --port 8000 --reload`

#### Inference
- [x] Build from `Dockerfile.inference`
- [x] Port: 8010
- [x] GPU reservation via `deploy.resources`
- [x] Volume mount: `./models:/app/models` for pre-downloaded weights
- [x] Command: `uvicorn inference.main:app --host 0.0.0.0 --port 8010`

### [x] Admin Profile (`--profile admin`)

#### pgAdmin
- [x] Image: `dpage/pgadmin4`
- [x] Port: 5050
- [x] Default credentials via environment variables.

#### Kafka UI
- [x] Image: `provectuslabs/kafka-ui:latest`
- [x] Port: 8080
- [x] Connect to Kafka broker.

### [x] Observability Profile (`--profile observability`)

#### Jaeger (All-in-One)
- [x] Image: `jaegertracing/all-in-one:latest`
- [x] Ports: 16686 (UI), 4317 (OTLP gRPC), 4318 (OTLP HTTP)
- [x] Receives traces from OpenTelemetry Collector and application SDKs.

#### OpenTelemetry Collector
- [x] Image: `otel/opentelemetry-collector:latest`
- [x] Ports: 4317, 4318
- [x] Configured to export to Jaeger.

### [ ] Test Profile (`--profile test`)

#### EvalOps Runner
- [ ] Build from `Dockerfile.gateway`
- [ ] Depends on: gateway, inference, neo4j
- [ ] Command: `pytest projects/evalops/ -v`

### [x] Volume Declarations
```yaml
volumes:
  pgdata:
  qdrant_data:
  neo4j_data:
  neo4j_logs:
  redis_data:
  kafka_data:
```

---

## 3. Local Development (Without Docker)

### [ ] Minimal Setup
Run only infrastructure services via Docker, with gateway and inference running natively:
```bash
# Start only databases
docker compose -f infrastructure/docker-compose.yml up postgres qdrant neo4j redis kafka

# In terminal 1: Start gateway
poetry install --all-extras
uvicorn gateway.main:app --host 0.0.0.0 --port 8000 --reload

# In terminal 2: Start inference
uvicorn inference.main:app --host 0.0.0.0 --port 8010 --reload
```

### [ ] Selective Service Startup
Support running with only specific databases:
```bash
# Just Postgres + Qdrant (no Neo4j, no Kafka)
docker compose up postgres qdrant
```
The gateway should gracefully handle missing services (log warnings, skip functionality).

### [ ] Hot Reload
- [ ] Gateway: `--reload` flag enabled when `APP_ENV=development`.
- [ ] Inference: `--reload` flag enabled when `APP_ENV=development`.
- [ ] Frontend (if Vite): `npm run dev` with HMR.

---

## 4. Production Deployment Considerations (Future)

### [ ] Cloud Provider
- [ ] Recommended: Google Cloud Platform (GCP) for proximity to Gemini API.
- [ ] GPU instances: GCE with NVIDIA T4/L4 for inference.
- [ ] Alternative: Any provider with NVIDIA GPU support and Docker/Kubernetes.

### [ ] Container Orchestration
- [ ] Kubernetes manifests or Helm charts (future).
- [ ] Cloud Run for stateless gateway (future).
- [ ] Persistent volumes for model weights.

### [ ] CI/CD Pipeline
- [ ] GitHub Actions workflow for:
  - Linting (`ruff`, `mypy`)
  - Unit tests (`pytest`)
  - EvalOps safety tests on PR
  - Docker image builds
  - Optional: Deploy to staging on merge to main
