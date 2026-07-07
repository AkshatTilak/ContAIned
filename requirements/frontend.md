# Frontend UI & Visual Requirements Checklist

This document details the user interface, component layout, dynamic route loading parameters, and technical stack of the unified web client.

---

## 1. Technical Stack & Project Setup

### [ ] Framework & Build Tool
- [ ] **Framework:** React 18+ with TypeScript.
- [ ] **Build Tool:** Vite (fast HMR, optimized builds).
- [ ] **Project Location:** `frontend/` directory at the monorepo root.
- [ ] **Package Manager:** npm or pnpm.
- [ ] **Key Libraries:**
  - `@xyflow/react` (React Flow) — for LangGraph execution flowcharts.
  - `recharts` or `chart.js` — for EvalOps metric charts.
  - `@tanstack/react-query` — for API data fetching and caching.
  - `react-markdown` + `react-syntax-highlighter` — for chat message rendering.
  - `lucide-react` — icon library.

### [ ] API Client Layer
- [ ] Communicate with the gateway via REST (`fetch` / `axios`).
- [ ] SSE (Server-Sent Events) for streaming chat responses from GuardRoute.
- [ ] Auto-generate TypeScript types from FastAPI's OpenAPI spec (`/openapi.json`).
- [ ] Base URL configurable via `VITE_API_URL` environment variable (default: `http://localhost:8000`).

### [ ] Docker Integration
- [ ] Add `frontend` service to `docker-compose.yml` (behind a `frontend` profile or default).
- [ ] Alternative: Serve built static files from the gateway using `fastapi.staticfiles`.

---

## 2. Design Tokens & UI Aesthetics

- [ ] **Dark Mode Styling:** Base themes must use sleek graphite backgrounds (`#0F0F11` to `#18181B`) with neon accents for component actions (e.g. emerald borders for success, indigo triggers for loading, amber for warnings).
- [ ] **Typography Hierarchy:** Leverage Google Fonts like `Inter` or `Outfit` instead of default browser sans-serif options.
- [ ] **Glassmorphism Panels:** Implement translucent cards utilizing `backdrop-filter: blur(12px)` and thin border structures (`border: 1px solid rgba(255, 255, 255, 0.05)`).
- [ ] **Fluid Micro-Animations:** All button hover states, dialog openings, and list popups must use cubic-bezier transitions (`transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1)`).
- [ ] **Responsive Design:** Optimize for desktop and tablet viewports (minimum 1024px width). Mobile support is not required for this developer dashboard.

---

## 3. Pluggable Dashboard Architecture
The frontend must automatically configure its panels depending on active submodules.

- [ ] **Status Mapping Logic:** Perform an initial GET check to `/health` on Gateway startup. Read the `active_projects` array.
- [ ] **Dynamic Navigation Loader:** Disable dashboard routes and menu sidebars pointing to inactive modules.
- [ ] **Fallback UI Placeholders:** If a user manually browses to a disabled module route, show a detailed status card mapping the steps to enable the project inside `.env` configurations.

---

## 4. Global System Status & Control Panel

- [ ] **Connection Grid:** Display status indicators showing the health of:
  - Gateway (port 8000)
  - Inference Server (port 8010)
  - PostgreSQL (port 5432)
  - Qdrant (port 6333)
  - Neo4j (port 7687)
  - Redis (port 6379)
  - Kafka Broker (port 9092)
- [ ] **Inference Server VRAM Monitor:**
  - Render a visual gauge tracking VRAM memory allocations (used / budget).
  - Display a live list of model slots currently loaded in VRAM (fetched from `/health` on the inference server).
  - Show cold-start vs warm latency metrics.
- [ ] **Model Registry Panel (NEW):**
  - Display active model configuration per role (OCR, ASR, Embedding, Classifier, Completion).
  - Show whether each role is using a local or cloud model.
  - Display VRAM budget impact based on selected local models.
  - Link to model benchmark scores and documentation.
  - Allow toggling model selection via API (if `AUTH_ENABLED`).
- [ ] **Admin Quick-Console Links:** Place links directing developers to:
  - Qdrant collection dashboard: `http://localhost:6333/dashboard`
  - Neo4j Cypher interactive browser: `http://localhost:7474`
  - pgAdmin database studio: `http://localhost:5050`
  - Kafka UI dashboard: `http://localhost:8080`
  - Jaeger trace console: `http://localhost:16686`

---

## 5. SyntraFlow Dashboard UI Specifications

- [ ] **Uploader Component:** Multi-modal drag-and-drop panel.
  - Display upload speeds, file categories, and processing logs.
  - Show file size validation errors inline.
  - Display duplicate detection results (existing document found vs. new upload).
- [ ] **Ingestion Job Tracker (NEW):**
  - List active and recent ingestion jobs with status (queued, processing, completed, failed).
  - Show progress bar for active jobs.
  - Link to detailed job logs.
- [ ] **Layout OCR Split Panel:**
  - Left panel: Uploaded PDF document renderer.
  - Right panel: Extracted layout-preserving Markdown string.
  - Show which OCR model was used (from Model Registry).
- [ ] **Video Segment Timeline Widget:**
  - Embed HTML5 video player.
  - Display transcription snippets mapped to timestamps. Clicking a segment jumps the video playhead to the corresponding start mark.
  - Display aligned visual keyframe descriptions and event tags (e.g. emotional status or detected audio events like laughter).
  - Show which ASR model was used.
- [ ] **RAG Sandbox Interface:**
  - Query box allowing custom search strings.
  - Strategy selector (Vector vs Graph vs Hybrid).
  - Side-by-side search results comparison tables showing scoring outputs.
  - Show embedding model and vector dimension used.

---

## 6. GuardRoute Dashboard UI Specifications

- [ ] **LangGraph Execution Flowchart:**
  - Render an interactive flow map using React Flow (`@xyflow/react`) representing active execution steps.
  - Highlight current execution nodes in real-time.
  - Show timing annotations on edges (latency between nodes).
- [ ] **Subagent Node Logs:** Clicking any node in the flowchart opens an inspection side-drawer containing:
  - Raw JSON results (e.g. generated sandbox Python codes, search parameters, document vector chunks).
  - Execution latency.
  - Model used for that step.
  - Token count (input/output).
- [ ] **Streaming Chat Client:**
  - Modern messaging console supporting Markdown styles and syntax highlighting for coding prompts.
  - SSE-based streaming for real-time token display.
  - Above each response, render a meta-header documenting:
    - Complexity category.
    - Active subagent triggers.
    - Classification latency (ms).
    - Model used for synthesis.
    - Token usage (input/output).
  - Support for multi-turn conversations with session management.

---

## 7. EvalOps Dashboard UI Specifications

- [ ] **RAGAS Metric Charts:** Linear timeline graphs plotting historical trends for Context Recall, Faithfulness, and Semantic Similarity. Use `recharts` or `chart.js`.
- [ ] **Safety Audit Logs:** Data grids tracking blocked prompt injection inputs, Toxicity ratings, and PII leakage alerts.
- [ ] **Diagnostic Trace Waterfall:**
  - Waterfall graph representing nested OpenTelemetry execution spans.
  - Highlight bottlenecks (e.g. OCR layout loads, embedding computation, model VRAM cold-starts, LiteLLM provider switchovers).
  - Link to Jaeger UI for detailed trace exploration.
- [ ] **Model Comparison Dashboard (NEW):**
  - Display benchmark results from `bench_models.py` across different model options.
  - Comparative tables/charts showing accuracy, latency, and VRAM usage per model role.

---

## 8. Error Handling & Loading States

- [ ] **Skeleton Loaders:** Display animated skeleton placeholders while data loads.
- [ ] **Error Banners:** Show dismissible error banners with:
  - Error message.
  - Retry button.
  - Timestamp.
  - Suggestion (e.g., "Check if the inference server is running").
- [ ] **Upload Failure States:** Show specific error messages for:
  - File too large (exceeds size limit).
  - Unsupported format.
  - Duplicate document detected (with link to existing).
  - Ingestion pipeline failure (with error details).
- [ ] **LLM Provider Outage:** Show provider status and which fallback model was used if the primary is down.
- [ ] **Empty States:** Meaningful empty state illustrations for dashboards with no data yet (e.g., "No documents ingested yet. Upload your first file above.").

---

## 9. Admin Services (docker-compose additions)
The following services should be added to `docker-compose.yml` behind profiles:

### Admin Profile (`--profile admin`)
```yaml
pgadmin:
  image: dpage/pgadmin4
  ports: ["5050:80"]
  environment:
    PGADMIN_DEFAULT_EMAIL: admin@local.dev
    PGADMIN_DEFAULT_PASSWORD: admin
  profiles: ["admin"]

kafka-ui:
  image: provectuslabs/kafka-ui:latest
  ports: ["8080:8080"]
  environment:
    KAFKA_CLUSTERS_0_NAME: local
    KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS: kafka:9092
  profiles: ["admin"]
```

### Observability Profile (`--profile observability`)
```yaml
jaeger:
  image: jaegertracing/all-in-one:latest
  ports:
    - "16686:16686"   # Jaeger UI
    - "4317:4317"     # OTLP gRPC
    - "4318:4318"     # OTLP HTTP
  profiles: ["observability"]
```
