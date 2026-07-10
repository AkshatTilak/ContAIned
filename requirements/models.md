# Model Selection Registry & Provider Requirements

This document defines the configurable model selection system that allows operators to choose between local (GPU) and cloud (API) models per task role. All model references across the platform are resolved through this registry rather than hardcoded values.

---

## 1. Model Registry Architecture

### [x] Registry Storage
- [x] Maintain a `model_registry` table in PostgreSQL:
  ```sql
  CREATE TABLE model_registry (
      id              SERIAL PRIMARY KEY,
      role            VARCHAR(50) NOT NULL,    -- 'ocr', 'asr', 'embedding', 'classifier', 'completion'
      mode            VARCHAR(10) NOT NULL,    -- 'local' or 'cloud'
      provider        VARCHAR(50) NOT NULL,    -- 'huggingface', 'gemini', 'openrouter', 'paddleocr', etc.
      model_id        VARCHAR(200) NOT NULL,   -- HF repo ID, API model string, or local path
      display_name    VARCHAR(100) NOT NULL,
      framework       VARCHAR(50),             -- 'transformers', 'llama-cpp', 'paddleocr', 'litellm', etc.
      vram_mb         INT,                     -- estimated VRAM for local models; NULL for cloud
      vector_dim      INT,                     -- for embedding models; NULL otherwise
      context_window  INT,                     -- for completion/classifier models
      quantization    VARCHAR(20),             -- 'fp16', 'int8', 'q4_k_m', 'gguf', NULL
      is_default      BOOLEAN DEFAULT FALSE,
      is_enabled      BOOLEAN DEFAULT TRUE,
      priority        INT DEFAULT 0,           -- fallback ordering (lower = higher priority)
      metadata_json   JSONB,                   -- extra config (API keys, max_tokens, etc.)
      created_at      TIMESTAMP DEFAULT NOW()
  );
  ```
- [x] Seed the table with all supported model entries on first startup.
- [x] Use the `model_registry_` prefix for namespace isolation.

### [x] Environment Override Pattern
Allow quick model switching without touching the database:
```env
OCR_MODEL=gemini          # shorthand for the default 'cloud' OCR model
ASR_MODEL=sensevoice      # shorthand for the default 'local' ASR model
EMBEDDING_MODEL=jina      # or 'gemini' for cloud
CLASSIFIER_MODEL=arch     # or 'semantic' for embedding-based routing
COMPLETION_MODEL=gemini   # or 'openrouter', 'groq', 'local'
```
Environment overrides take priority over database entries.

### [x] Registry API (`common/models/registry.py`)
- [x] `get_model_spec(role: str, mode: str = "auto") -> ModelSpec` — Resolve the active model for a given role.
- [x] `get_active_model(role: str) -> ModelSpec` — Get the current default model.
- [x] `list_available(role: str) -> list[ModelSpec]` — List all enabled models for a role.
- [x] `get_fallback_chain(role: str) -> list[ModelSpec]` — Get ordered fallback list.

### [x] Dynamic Vector Dimension
- [x] Qdrant collection creation must read the `vector_dim` from the active embedding model's registry entry.
- [x] Switching embedding models requires re-indexing all vectors. The system must detect dimension mismatches and warn/block on startup.

---

## 2. HuggingFace Hub Integration

### [ ] Auto-Download on First Use
- [ ] When a local model is selected but weights are not cached, auto-download from HuggingFace Hub using `huggingface_hub.snapshot_download()` or `transformers.AutoModel.from_pretrained()`.
- [ ] Display download progress in logs.
- [ ] Support gated models with `HF_TOKEN` authentication.

### [ ] Environment Variables
```env
HF_HOME=/app/models                    # HuggingFace cache root
HF_HUB_ENABLE_HF_TRANSFER=1           # Faster downloads
HF_HUB_OFFLINE=0                       # Set to 1 for air-gapped environments
HF_TOKEN=                              # Token for gated model access
MODEL_CACHE_DIR=/app/models/cache      # Custom cache for GGUF/non-HF files
```

### [ ] Quantization Support
- [ ] For `transformers`-based models: support `load_in_8bit` / `load_in_4bit` via `bitsandbytes`.
- [ ] For GGUF models: support Q4_K_M, Q5_K_M, Q8_0 quantization levels.
- [ ] Registry entry specifies the quantization level per model.

### [ ] Device Map Auto-Detection
- [ ] `DEVICE=auto` (default): auto-detect CUDA availability; fall back to CPU.
- [ ] `DEVICE=cuda`: force GPU (fail if unavailable).
- [ ] `DEVICE=cpu`: force CPU (degraded performance for local models).

---

## 3. OCR Models — Available Options

Selection criteria: **OmniDocBench** (2026) scores, VRAM usage, deployment complexity.

### [ ] Local Options

#### Option 1: GLM-OCR ⭐ Recommended Default
- **Model:** `THUDM/GLM-OCR` (0.9B parameters)
- **VRAM:** ~2 GB (FP16)
- **Framework:** `transformers`
- **Strengths:** #1 on OmniDocBench; compact; excellent text and table extraction.
- **Quantization:** FP16, INT8

#### Option 2: Surya OCR 2
- **Model:** `surya-ocr` (via pip)
- **VRAM:** ~4 GB
- **Framework:** `surya-ocr`
- **Strengths:** 90+ language support; strong table/layout detection.

#### Option 3: PaddleOCR-VL (Baidu)
- **Model:** `paddleocr` (PaddleOCR-VL 1.6B)
- **VRAM:** ~2-3 GB (FP16 + FlashAttention-2) to ~5 GB (default)
- **Framework:** `paddlepaddle-gpu` / `paddleocr`
- **Strengths:** Production-grade; well-supported; high throughput (pages/minute).
- **Note:** Requires FlashAttention-2 and `torch.inference_mode()` for optimal VRAM usage.

#### Option 4: GOT-OCR 2.0
- **Model:** `stepfun-ai/GOT-OCR2_0`
- **VRAM:** ~8.5 GB
- **Framework:** `transformers`
- **Strengths:** Excellent complex table extraction; handles printed + handwritten text.

#### Option 5: Docling (IBM)
- **Model:** `docling` (via pip; uses `granite-docling` models)
- **VRAM:** CPU-only (negligible GPU usage)
- **Framework:** `docling`
- **Strengths:** RAG-optimized; outputs structured Markdown/JSON natively; runs fully on CPU.
- **Best For:** Layout-aware parsing without GPU costs.

### [ ] Cloud Options

#### Option 6: Gemini 3.5 Flash (Vision) ⭐ Recommended Cloud Default
- **Model String:** `gemini/gemini-3.5-flash` (via LiteLLM)
- **VRAM:** 0 (cloud)
- **Strengths:** Frontier-class vision reasoning; agentic document understanding; layout-preserving Markdown output.
- **Free Tier:** Google AI Studio free tier (1500 RPD).

#### Option 7: Mistral OCR
- **Model String:** `mistral/pixtral-large-latest` (via Mistral API)
- **VRAM:** 0 (cloud)
- **Strengths:** Strong spatial reasoning; document understanding.

### [ ] JSON Schema Contract (All OCR Models)
- **Input:** PDF page or document image bytes.
- **Output:**
  ```json
  {
    "text": "Extracted full text...",
    "blocks": [{"type": "paragraph|header|table|list", "content": "...", "bbox": [x1,y1,x2,y2]}],
    "tables": [{"cells": [[{"row":0,"col":0,"text":"..."}]], "bbox": [x1,y1,x2,y2]}],
    "layout": "markdown string preserving document structure"
  }
  ```

---

## 4. ASR (Speech-to-Text) Models — Available Options

Selection criteria: **HuggingFace Open ASR Leaderboard** WER scores, VRAM usage, special features (emotion/event detection).

### [ ] Local Options

#### Option 1: SenseVoice-Small ⭐ Recommended Default
- **Model:** `FunAudioLLM/SenseVoiceSmall` (234M parameters)
- **VRAM:** ~250 MB
- **Framework:** `funasr`
- **WER:** ~7-8% average
- **Strengths:** Ultra-fast (non-autoregressive); emotion recognition; audio event detection (laughter, applause, crying). 50+ languages.
- **Unique:** Only model with native emotion/event tags — required by SyntraFlow video ingestion.

#### Option 2: Whisper V3 Turbo
- **Model:** `openai/whisper-large-v3-turbo` (809M parameters)
- **VRAM:** ~3-4 GB
- **Framework:** `faster-whisper` (CTranslate2 optimization)
- **WER:** ~7.8% average
- **Strengths:** Broad language support (99+ languages); massive ecosystem; robust against noise.

#### Option 3: Whisper Large V3
- **Model:** `openai/whisper-large-v3` (1.55B parameters)
- **VRAM:** ~6-10 GB
- **Framework:** `faster-whisper`
- **WER:** ~7.4% average
- **Strengths:** Highest-accuracy Whisper variant; best multilingual coverage.

#### Option 4: Parakeet TDT 1.1B (NVIDIA)
- **Model:** `nvidia/parakeet-tdt-1.1b`
- **VRAM:** ~2-4 GB
- **Framework:** `nemo_toolkit`
- **WER:** ~8% average
- **Strengths:** Extreme speed (2000-3000x real-time); optimized for streaming. English-focused.

#### Option 5: Granite Speech 4.1 2B
- **Model:** `ibm-granite/granite-speech-4.1-2b`
- **VRAM:** ~4-8 GB
- **Framework:** `transformers`
- **WER:** ~5.3% average
- **Strengths:** Current SOTA accuracy; LLM-integrated (can summarize/extract from audio).

### [ ] Cloud Options

#### Option 6: Gemini 3.5 Flash (Audio)
- **Model String:** `gemini/gemini-3.5-flash` (via LiteLLM)
- **VRAM:** 0 (cloud)
- **Strengths:** Native audio understanding; can transcribe + reason about content simultaneously.

#### Option 7: Deepgram Nova-3
- **Model String:** `deepgram/nova-3` (via Deepgram SDK)
- **VRAM:** 0 (cloud)
- **Strengths:** Production-grade; real-time streaming; very low WER (~5%).

### [ ] JSON Schema Contract (All ASR Models)
- **Input:** Raw WAV/MP3 audio file bytes.
- **Output:**
  ```json
  {
    "text": "Full transcript...",
    "segments": [{"start": 0.0, "end": 2.5, "text": "Hello world", "confidence": 0.95}],
    "emotion": "happy|sad|neutral|angry",
    "audio_events": ["laughter", "applause"],
    "language": "en"
  }
  ```
  Note: `emotion` and `audio_events` fields are only populated by SenseVoice-Small. Other models return `null` for these fields.

---

## 5. Embedding Models — Available Options

Selection criteria: **MTEB/MMTEB Leaderboard**, **CCKM Benchmark** (2026), modality support, VRAM usage.

### [ ] Local Options

#### Option 1: jina-clip-v2 ⭐ Recommended Default
- **Model:** `jinaai/jina-clip-v2` (~900M parameters)
- **VRAM:** ~1 GB
- **Vector Dim:** 1024 (native); supports Matryoshka truncation down to 64
- **Framework:** `sentence-transformers` or `transformers`
- **Modalities:** Text + Image (joint embedding space)
- **Strengths:** Open-weight; excellent multilingual; Matryoshka flexibility.

#### Option 2: nomic-embed-vision-v2
- **Model:** `nomic-ai/nomic-embed-vision-v2`
- **VRAM:** ~500 MB
- **Vector Dim:** 768
- **Framework:** `sentence-transformers`
- **Modalities:** Text + Image
- **Strengths:** Ultra-lightweight; good accuracy for its size.

#### Option 3: Qwen3-Embedding-0.6B
- **Model:** `Qwen/Qwen3-Embedding-0.6B` (600M parameters)
- **VRAM:** ~1.5 GB
- **Vector Dim:** 1024
- **Framework:** `transformers`
- **Modalities:** Text only
- **Strengths:** SOTA for its size class on text benchmarks. Text-only (no image support).

### [ ] Cloud Options

#### Option 4: Gemini Embedding 2 ⭐ Recommended Cloud Default
- **Model String:** `gemini/gemini-embedding-exp-03-07` (via Google AI)
- **VRAM:** 0 (cloud)
- **Vector Dim:** up to 3072 (configurable)
- **Modalities:** Text + Image + Audio + Video + PDF
- **Strengths:** Best multimodal embedding; free tier (10M tokens/min); handles all modalities natively.
- **Free Tier:** Google AI Studio (10,000,000 tokens per minute).

#### Option 5: Voyage Multimodal 3
- **Model String:** `voyage/voyage-multimodal-3` (via Voyage AI API)
- **VRAM:** 0 (cloud)
- **Vector Dim:** 1024
- **Modalities:** Text + Image
- **Strengths:** Strong retrieval accuracy.

#### Option 6: OpenAI text-embedding-3-large
- **Model String:** `openai/text-embedding-3-large` (via OpenAI API)
- **VRAM:** 0 (cloud)
- **Vector Dim:** 3072 (supports Matryoshka truncation)
- **Modalities:** Text only
- **Strengths:** Industry standard; widely supported.

### [ ] Vector Dimension Rules
- Qdrant collection `syntraflow_chunks_v1` dimension is determined by the **active** embedding model.
- Default: **1024** (jina-clip-v2 native).
- If switching models with different dimensions, a **re-indexing migration** is required.
- Document supported truncation dimensions per model.

---

## 6. Task Classifier / Router Models — Available Options

Selection criteria: Accuracy on routing/intent tasks, VRAM usage, latency requirements.

### [ ] Local Options

#### Option 1: Arch-Router-1.5B ⭐ Current Default
- **Model:** `katanemo/Arch-Router-1.5B-Q8_0.gguf`
- **VRAM:** ~1-2 GB
- **Framework:** `llama-cpp-python`
- **Strengths:** Purpose-built for task routing; GGUF optimized.
- **Output:** JSON with `complexity` (simple/medium/complex) and `required_agents` list.

#### Option 2: Qwen3-4B (GGUF Q4_K_M)
- **Model:** `Qwen/Qwen3-4B-GGUF` (Q4_K_M quantization)
- **VRAM:** ~2-3 GB
- **Framework:** `llama-cpp-python`
- **Strengths:** Best accuracy/efficiency balance among SLMs; fine-tunable with LoRA.

#### Option 3: Phi-4-Mini (GGUF Q4_K_M)
- **Model:** `microsoft/phi-4-mini-instruct-GGUF`
- **VRAM:** ~2-3 GB
- **Framework:** `llama-cpp-python`
- **Strengths:** Edge-optimized; strong reasoning; Microsoft ecosystem.

#### Option 4: Gemma 3 4B (GGUF Q4_K_M)
- **Model:** `google/gemma-3-4b-it-GGUF`
- **VRAM:** ~2-3 GB
- **Framework:** `llama-cpp-python`
- **Strengths:** Fast; multilingual; Google ecosystem.

#### Option 5: Semantic Router (Zero-VRAM)
- **Model:** None (uses the active embedding model)
- **VRAM:** 0 additional (reuses embedding model)
- **Framework:** Cosine similarity computation
- **Strengths:** Zero additional VRAM; extremely fast; no model loading.
- **How it works:** Compute cosine similarity between the user query embedding and pre-defined route description embeddings. Routes to the nearest match.
- **Best For:** VRAM-constrained environments where a separate classifier cannot be loaded.

### [ ] Cloud Options

#### Option 6: Gemini 3.5 Flash (Structured Output)
- **Model String:** `gemini/gemini-3.5-flash` (via LiteLLM)
- **VRAM:** 0 (cloud)
- **Strengths:** JSON structured output; high accuracy; understands nuanced intent.

### [ ] Rule-Based Fallback (Always Available)
- **Framework:** Regex / keyword matching
- **VRAM:** 0
- **Activation:** Automatically engaged if the primary classifier fails or times out.
- **Implementation:** Check if prompt contains keywords like "code", "search", "retrieve", "summarize".

### [ ] JSON Schema Contract (All Classifier Models)
- **Input:** `{"prompt": "User query text"}`
- **Output:**
  ```json
  {
    "complexity": "simple|medium|complex",
    "required_agents": ["retrieval", "coding", "web_search"],
    "confidence": 0.92
  }
  ```

---

## 7. LLM Completion Providers — Available Options

Selection criteria: **Frontier model benchmarks** (July 2026), free-tier availability, latency, context window.

### [ ] Primary Provider: Google AI Studio
- **Model:** `gemini/gemini-3.5-flash` — ⭐ Recommended primary
  - Free tier: ~1500 RPD
  - Context: 1M+ tokens
  - Strengths: Multimodal; fast; generous free tier
- **Model:** `gemini/gemini-3.1-pro`
  - Free tier: Lower limits
  - Context: 2M+ tokens
  - Strengths: Deeper reasoning; largest context window

### [ ] Fallback Provider: Groq
- **Model:** `groq/llama-3.3-70b-versatile`
  - Free tier: 30 RPM, 1000+ RPD
  - Strengths: Fastest inference (LPU hardware); great for real-time chat
- **Model:** `groq/qwen-qwq-32b`
  - Free tier: 30 RPM
  - Strengths: Strong reasoning at speed

### [ ] Fallback Provider: OpenRouter (Aggregator)
- **Model:** `openrouter/google/gemini-3.5-flash:free`
  - Free tier: 20 RPM, 200 RPD (1000 RPD after one-time $10 credit)
- **Model:** `openrouter/qwen/qwen3-235b:free`
  - Free tier: 20 RPM
  - Strengths: Open-weight; strong coding/math
- **Model:** `openrouter/meta-llama/llama-4-scout:free`
  - Free tier: 20 RPM
  - Strengths: General-purpose; Meta ecosystem

### [ ] Fallback Provider: Cerebras
- **Model:** `cerebras/llama-3.3-70b`
  - Free tier: High volume
  - Strengths: Good for long-context batch processing

### [ ] Local Option: Ollama
- **Model:** `ollama/qwen3:8b`
  - VRAM: ~4-6 GB
  - Strengths: Fully offline; unlimited usage; no API key needed
- **Model:** `ollama/llama3.3:8b`
  - VRAM: ~4-6 GB

### [ ] Default Fallback Chain Configuration
```python
COMPLETION_FALLBACKS = [
    "gemini/gemini-3.5-flash",                   # 1. Primary (Google AI Studio)
    "groq/llama-3.3-70b-versatile",              # 2. Fast fallback (Groq LPU)
    "openrouter/google/gemini-3.5-flash:free",   # 3. Aggregator fallback
    "openrouter/qwen/qwen3-235b:free",           # 4. Open-weight fallback
    "openrouter/meta-llama/llama-4-scout:free",  # 5. Last resort cloud
]
```

### [ ] Capability-Aware Truncation
- If the fallback chain resolves to a model with a smaller context window, automatically truncate the context payload.
- Truncation should be in **tokens** (not characters), using `tiktoken` or LiteLLM's built-in token counter.
- Default truncation limits by tier:
  - Frontier models (Gemini 3.x): No truncation needed (1M+ context)
  - Mid-tier models (70B class): Truncate to 32,000 tokens
  - Small free-tier models: Truncate to 8,000 tokens

### [ ] Provider API Key Requirements
```env
GOOGLE_API_KEY=          # Google AI Studio (Gemini direct)
OPENROUTER_API_KEY=      # OpenRouter aggregator
GROQ_API_KEY=            # Groq (NEW — add to settings)
CEREBRAS_API_KEY=        # Cerebras (NEW — add to settings)
OPENAI_API_KEY=          # OpenAI (for DeepEval judge model)
```

---

## 8. Model VRAM Budget Profiles

Pre-configured profiles for different hardware setups:

### [ ] Profile: Ultra-Low (8 GB VRAM — e.g., RTX 3060/4060)
| Role | Model | VRAM |
|------|-------|------|
| OCR | Gemini 3.5 Flash (cloud) | 0 |
| ASR | SenseVoice-Small | 250 MB |
| Embedding | nomic-embed-vision-v2 | 500 MB |
| Classifier | Semantic Router | 0 |
| Completion | Gemini (cloud) | 0 |
| **Total** | | **~750 MB** |

### [ ] Profile: Standard (12-16 GB VRAM — e.g., RTX 4070/4080)
| Role | Model | VRAM |
|------|-------|------|
| OCR | GLM-OCR (FP16) | 2 GB |
| ASR | SenseVoice-Small | 250 MB |
| Embedding | jina-clip-v2 | 1 GB |
| Classifier | Arch-Router-1.5B (GGUF) | 2 GB |
| Completion | Gemini (cloud) | 0 |
| **Total** | | **~5.25 GB** |

### [ ] Profile: High-End (24+ GB VRAM — e.g., RTX 3090/4090)
| Role | Model | VRAM |
|------|-------|------|
| OCR | PaddleOCR-VL (FP16) | 3 GB |
| ASR | Granite Speech 4.1 2B | 6 GB |
| Embedding | jina-clip-v2 | 1 GB |
| Classifier | Qwen3-4B (GGUF Q4) | 3 GB |
| Completion | Ollama qwen3:8b (local) | 6 GB |
| **Total** | | **~19 GB** |

Note: The VRAM Manager's lazy loading and LRU eviction means not all models need to be loaded simultaneously. These profiles represent maximum concurrent usage.
