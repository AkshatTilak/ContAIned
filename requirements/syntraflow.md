# SyntraFlow Ingestion & Hybrid RAG Requirements

SyntraFlow handles ingestion, layout-aware OCR extraction, keyframe/ASR audio alignment, index writing (PostgreSQL, Qdrant, Neo4j), and MCP retrieval server tasks. Model selection is configurable via the Model Registry (see `requirements/models.md`).

---

## 1. Document Ingestion Requirements
- [ ] **Configurable OCR Engine (via Model Registry):**
  - **Local Mode:** Load the configured local OCR model (default: GLM-OCR) into the inference server VRAM on request. Extract raw document structures, cells, and layouts. Optionally pass markup to an LLM (Gemini Flash) to convert to layout-preserving Markdown JSON.
  - **API Mode:** Pass document images directly to the configured cloud OCR model (default: Gemini 3.5 Flash API) in a single vision-aware completion pass to output layout-preserving Markdown and tabular JSON. Runs at zero local VRAM cost.
  - See `requirements/models.md` §3 for all OCR model options.
- [ ] **Layout-Aware Chunking Engine:**
  - Split documents by logical layout boundaries (headers, paragraphs, sections) instead of arbitrary token lengths.
  - Maintain parent-child mappings for headers to conserve contextual hierarchies.
  - Configurable parameters:
    - `CHUNK_MAX_TOKENS=512` — Maximum tokens per chunk.
    - `CHUNK_OVERLAP=50` — Token overlap between consecutive chunks.
    - Minimum chunk size: 50 tokens (avoid tiny fragments).

---

## 2. Video & Audio Ingestion Requirements
- [ ] **Asynchronous Stream Demuxing:**
  - Extract the audio channel from uploaded video containers (`.mp4`, `.mov`, `.webm`, `.mkv`) using an async media pipeline.
  - Generate temporary WAV audio files (`.wav`) for transcription.
  - **Dependency Fix:** Use `ffmpeg-python` or `pydub` (NOT `aiortc`, which is for WebRTC). Require `ffmpeg` binary in Docker image.
- [ ] **Speech-to-Text Transcription:**
  - Pass audio files to the configured ASR model on the inference server (default: SenseVoice-Small).
  - Return transcribed word segments mapping start/end timestamps.
  - Capture emotion markers and audio event tags (laughter, applause, crying) — unique feature of SenseVoice-Small.
  - See `requirements/models.md` §4 for all ASR model options.
- [ ] **Keyframe Scene-Change Sampling:**
  - Sample video keyframes on scene change limits (e.g., tracking pixel delta thresholds or visual SSIM changes).
  - Pass keyframes to the configured cloud LLM (default: Gemini 3.5 Flash) to generate visual summaries and describe charts/drawings.
- [ ] **Temporal Aligner:**
  - Align ASR transcript timestamps with LLM keyframe visual descriptions chronologically.
  - Store aligned timeline blocks in the relational database.

---

## 3. File Upload & Processing

### [ ] File Size & Format Limits
- [ ] Maximum upload size:
  - Documents: 100 MB (PDF, DOCX, PPTX, images)
  - Videos: 500 MB (MP4, MOV, WebM, MKV)
  - Audio: 200 MB (WAV, MP3, FLAC)
- [ ] Supported formats:
  - Documents: `.pdf`, `.png`, `.jpg`, `.jpeg`, `.tiff`, `.bmp`, `.docx`, `.pptx`
  - Video: `.mp4`, `.mov`, `.webm`, `.mkv`
  - Audio: `.wav`, `.mp3`, `.flac`, `.ogg`
- [ ] Enforce limits via FastAPI `UploadFile` size constraints on the gateway.

### [x] Duplicate Document Detection
- [x] Compute SHA-256 hash of file content on upload.
- [x] Check against existing hashes in the `syntraflow_documents` table.
- [x] If duplicate: return existing document ID and metadata; skip re-processing.

### [x] Ingestion Job Status Tracking
- [x] Maintain a `syntraflow_jobs` table:
  ```sql
  CREATE TABLE syntraflow_jobs (
      id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      document_id UUID REFERENCES syntraflow_documents(id),
      status      VARCHAR(20) NOT NULL DEFAULT 'queued',  -- queued, processing, completed, failed
      progress    FLOAT DEFAULT 0.0,                       -- 0.0 to 1.0
      error_msg   TEXT,
      created_at  TIMESTAMP DEFAULT NOW(),
      updated_at  TIMESTAMP DEFAULT NOW()
  );
  ```
- [x] Publish job to Kafka topic `syntraflow-ingestion-jobs` for async processing.
- [x] Expose `GET /api/syntraflow/jobs/{job_id}` status endpoint.

---

## 4. Database Writing & KG Population
- [ ] **Relational DB Operations (PostgreSQL):**
  - Write document metadata, aligned video segments, and chunk payloads to Postgres database schemas.
  - Use `syntraflow_` prefix for all tables (`syntraflow_documents`, `syntraflow_chunks`, `syntraflow_video_segments`).
- [ ] **Vector Indexing (Qdrant):**
  - Generate embeddings for each text block or aligned keyframe segment using the configured embedding model (default: jina-clip-v2).
  - Index embeddings inside the `syntraflow_chunks_v1` collection.
  - **Vector dimension:** Determined by the active embedding model (default: 1024 for jina-clip-v2). See `requirements/models.md` §5.
  - Batch upserts: process in batches of 100 vectors per upsert call.
- [ ] **Knowledge Graph Population (Neo4j):**
  - Run an LLM extraction pass over text chunks to extract Entities (People, Orgs, Locations), Relationships, and factual Claims.
  - **LLM for Extraction:** Use the configured completion model (default: Gemini 3.5 Flash via LiteLLM).
  - **Entity Types:** Person, Organization, Location, Concept, Event, Product.
  - **Output Schema per chunk:**
    ```json
    {
      "entities": [{"name": "...", "type": "Person|Organization|...", "description": "..."}],
      "relationships": [{"source": "...", "target": "...", "type": "WORKS_AT|LOCATED_IN|...", "description": "..."}]
    }
    ```
  - Write graph nodes and edges to Neo4j using the prefix `SyntraFlow_` for labels (e.g., `SyntraFlow_Entity`, `SyntraFlow_RELATION`).
  - Batch processing: extract entities per chunk, deduplicate, then batch write to Neo4j.

---

## 5. Model Context Protocol (MCP) Specifications
Expose standard retriever capabilities as tools via a FastMCP server:

### [ ] Transport
- [ ] Use **SSE (Server-Sent Events)** transport for MCP server (compatible with web clients and LangGraph).
- [ ] Alternative: **streamable-HTTP** for simpler integrations.

### [ ] Tools
- [ ] **`retrieve_documents(query: str, strategy: str, limit: int) -> str`**
  - Performs hybrid retrieval. Calls Vector Similarity Search on Qdrant, Cypher query traversal on Neo4j, merges results using Reciprocal Rank Fusion (RRF), and returns ranked texts.
  - `strategy` parameter: `vector`, `graph`, or `hybrid` (default from `RAG_STRATEGY` setting).
- [ ] **`retrieve_video_segments(query: str, limit: int) -> str`**
  - Performs semantic searches against video timeline blocks in Qdrant and returns aligned transcripts and visual descriptions.
- [ ] **`query_database(table: str, filters: dict, columns: list) -> str`**
  - Parameterized database helper. Must block access if table does not start with `syntraflow_` and prevent SQL injections via parameterized queries only.
- [ ] **`query_graph(cypher_query: str) -> str`**
  - Read-only parameterized Cypher traversal. Reject Cypher commands containing forbidden write keywords (`CREATE`, `MERGE`, `DELETE`, `SET`, `REMOVE`, `DROP`).

---

## 6. Document Deletion & Cleanup

### [x] Deletion API
- [x] `DELETE /api/syntraflow/documents/{doc_id}` — Cascade delete:
  - [x] Remove vectors from Qdrant by document ID filter.
  - [x] Remove graph nodes/edges from Neo4j by document reference.
  - [x] Remove rows from Postgres (`syntraflow_documents`, `syntraflow_chunks`, `syntraflow_video_segments`, `syntraflow_jobs`).
  - [x] Return confirmation with counts of deleted items.

---

## 7. Missing Dependencies (pyproject.toml)
The `syntraflow` optional dependency group must include:
```toml
syntraflow = [
    "langchain (>=0.3.0,<1.0.0)",
    "langgraph (>=0.2.0,<1.0.0)",
    "sentence-transformers (>=3.0.0,<4.0.0)",
    "mcp (>=0.1.0,<1.0.0)",
    "neo4j (>=5.20.0,<6.0.0)",
    "confluent-kafka (>=2.4.0,<3.0.0)",
    "ffmpeg-python (>=0.2.0,<1.0.0)",   # NEW: replaces aiortc for media processing
    "pydub (>=0.25.1,<1.0.0)",           # NEW: audio processing
]
```
Remove: `aiortc` (WebRTC library — incorrect for file-based media demuxing), `mlflow` (move to evalops if needed).
