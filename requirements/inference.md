# Inference Server & Model Requirements Checklist

The Inference Server runs GPU-bound deep learning workloads behind a single API Gateway and coordinates memory allocations to prevent VRAM out-of-memory (OOM) crashes. Models are selected from the configurable Model Registry (see `requirements/models.md`).

---

## 1. VRAM Manager & Budgeting Requirements
- [ ] **On-Demand Lazy Loading:**
  - Keep model weights unloaded from VRAM until an incoming router request targets a specific endpoint.
  - Automatically load the target model at request time and update its last-used timestamp.
  - Auto-download model weights from HuggingFace Hub on first use if not cached (see `requirements/models.md` §2).
- [ ] **LRU Eviction Scheduler:**
  - Maintain a configurable VRAM memory budget (default: 20 GB, via `VRAM_BUDGET_MB` env var).
  - If loading a model would exceed this limit, evict the Least Recently Used (LRU) model from memory before loading the new model.
- [ ] **Idle Cleanup Daemon:**
  - Run a background task that checks model status every 60 seconds.
  - If a model remains inactive for more than `CLASSIFIER_IDLE_TIMEOUT` seconds (default: 300), unload it from VRAM.
- [ ] **Device Auto-Detection:**
  - Read `DEVICE` setting (`auto`, `cuda`, `cpu`).
  - If `auto`: detect CUDA availability; fall back to CPU.
  - If `cpu`: load all models on CPU (degraded performance, useful for dev environments without GPU).
- [ ] **Model Registry Integration:**
  - On startup, read enabled local models from the Model Registry.
  - Register loader functions only for models marked as `is_enabled=True` and `mode='local'`.
  - Support hot-reload: if registry changes, re-register model loaders without restarting.

---

## 2. Task Classifier Requirements
- [ ] **Default Model:** `Arch-Router-1.5B` (GGUF format). See `requirements/models.md` §6 for alternatives.
- [ ] **VRAM Allocation Budget:** ~1-2 GB VRAM.
- [ ] **Inference Framework:** `llama-cpp-python`.
- [ ] **Alternative: Semantic Router** (zero VRAM) — uses the active embedding model for cosine-similarity-based routing when VRAM is constrained.
- [ ] **JSON Schema Contract:**
  - Input: `{"prompt": "User query text"}`
  - Output:
    ```json
    {
      "complexity": "simple|medium|complex",
      "required_agents": ["retrieval", "coding", "web_search"],
      "confidence": 0.92
    }
    ```

---

## 3. ASR (Speech-to-Text) Requirements
- [ ] **Default Model:** SenseVoice-Small (Alibaba). See `requirements/models.md` §4 for alternatives.
- [ ] **VRAM Allocation Budget:** ~250 MB VRAM.
- [ ] **Inference Framework:** `funasr` (must be added to `pyproject.toml` inference extras).
- [ ] **JSON Schema Contract:**
  - Input: Raw WAV/MP3 audio file bytes.
  - Output:
    ```json
    {
      "text": "Full transcript...",
      "segments": [{"start": 0.0, "end": 2.5, "text": "Hello world", "confidence": 0.95}],
      "emotion": "happy|sad|neutral|angry",
      "audio_events": ["laughter", "applause"],
      "language": "en"
    }
    ```
  - Note: `emotion` and `audio_events` are unique to SenseVoice. Other ASR models return `null`.

---

## 4. Embedding (Joint Text & Image) Requirements
- [ ] **Default Model:** `jinaai/jina-clip-v2`. See `requirements/models.md` §5 for alternatives.
- [ ] **VRAM Allocation Budget:** ~1 GB VRAM.
- [ ] **Inference Framework:** `sentence-transformers` or `transformers` / `torch`.
- [ ] **Functionality Scope:**
  - Provide a single unified embedding space for both text sentences and image inputs.
  - Support Matryoshka dimensions. **Native output: 1024 elements** (NOT 768 — that was jina-clip-v1).
  - Vector dimension must match the Qdrant collection configuration.
- [ ] **Cloud Alternative:** Gemini Embedding 2 (up to 3072 dimensions; free tier: 10M tok/min).

---

## 5. OCR (Document Layout Extraction) Requirements
- [ ] **Default Local Model:** `GLM-OCR` (0.9B params, ~2 GB VRAM). See `requirements/models.md` §3 for alternatives.
- [ ] **Legacy Option:** `Baidu Unlimited-OCR` / PaddleOCR (~2-5 GB VRAM depending on optimization).
- [ ] **Cloud Option:** `Gemini 3.5 Flash` (vision mode, zero local VRAM).
- [ ] **Inference Framework:** Depends on selected model (`transformers`, `paddleocr`, `litellm`).
- [ ] **Missing Dependencies (must add to `pyproject.toml` inference extras):**
  - `funasr` — for SenseVoice ASR
  - `paddlepaddle-gpu`, `paddleocr` — if PaddleOCR is enabled
  - `surya-ocr` — if Surya is enabled
  - `docling` — if Docling is enabled
  - `llama-cpp-python` — move from `[tool.poetry.dependencies]` to `[project.optional-dependencies.inference]`
- [ ] **JSON Schema Contract:**
  - Input: PDF page or document image bytes.
  - Output:
    ```json
    {
      "text": "Extracted full text...",
      "blocks": [{"type": "paragraph|header|table|list", "content": "...", "bbox": [x1,y1,x2,y2]}],
      "tables": [{"cells": [[{"row":0,"col":0,"text":"..."}]], "bbox": [x1,y1,x2,y2]}],
      "layout": "Markdown string preserving document structure"
    }
    ```

---

## 6. Health Endpoint

### [x] `/health` Response Schema
```json
{
  "status": "healthy",
  "loaded_models": [
    {"name": "jina-clip-v2", "vram_mb": 1000, "last_used": 1720000000.0, "load_count": 5}
  ],
  "vram_used_mb": 3250,
  "vram_budget_mb": 20000,
  "device": "cuda",
  "registered_models": ["baidu-ocr", "jina-clip-v2", "sensevoice-small", "arch-router-1.5b"]
}
```

---

## 7. Concurrency & Performance

### [x] Request Queuing
- [x] If two requests arrive simultaneously requiring the same model load, the second should wait for the load to complete (handled by `asyncio.Lock` in `VRAMManager`).
- [x] If two inference requests arrive for an already-loaded model, they should execute concurrently (no lock on inference, only on load/unload).

### [x] Per-Model Concurrency Limits
- [x] Optionally limit concurrent inference calls per model (e.g., max 4 concurrent embedding batches).
- [x] Prevent GPU memory spikes from oversized batch requests.

### [x] Cold-Start vs Warm Latency Tracking
- [x] Log cold-start latency (first request requiring VRAM load) separately from warm latency (model already loaded).
- [x] Include these metrics in the health endpoint for monitoring.
