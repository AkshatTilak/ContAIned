# EvalOps QA Verification & Observability Requirements

EvalOps serves as the automated quality assurance system, running benchmarks, analyzing transaction logs from Kafka, and enforcing safety guardrails. It runs as a test/CI tool, not a permanent production service.

---

## 1. RAGAS Retrieval Quality Benchmarking
- [ ] **Context Recall Verification:**
  - Measure the overlap of retrieved document segments with target ground truth texts to verify that the RAG retriever is fetching relevant info.
- [ ] **Faithfulness Metric Check:**
  - Verify that the Synthesis Agent's final response remains grounded in the gathered context without introducing external hallucinations.
- [ ] **Semantic Similarity Scoring:**
  - Compute embeddings similarity scores comparing the synthesized output to the target query ground truths.
  - Use the active embedding model from the Model Registry (default: jina-clip-v2).

---

## 2. DeepEval Safety & Guardrails Assertions
Enforce test suites to run during Pull Requests to verify the safety profile of backend modifications:
- [ ] **DeepEval Judge Model Configuration:**
  - DeepEval defaults to using `gpt-4o` as the evaluation judge.
  - Configure to use the platform's primary LLM instead: `gemini/gemini-3.5-flash` (via LiteLLM integration).
  - Add `DEEPEVAL_MODEL` setting to `common/config/settings.py`.
  - Requires `OPENAI_API_KEY` or `GOOGLE_API_KEY` depending on judge model.
- [ ] **Toxicity Metric Check:**
  - Assert that toxicity metrics remain below 0.1 for typical user prompts.
- [ ] **Prompt Injection Scanner:**
  - Test the orchestrator against prompt injection payloads and verify that the system blocks attempts.
  - Maintain a `tests/fixtures/injection_payloads.json` file with test cases.
- [ ] **PII Leakage Detector:**
  - Verify that the orchestrator does not output personally identifiable information (PII) like phone numbers, API keys, or email addresses.

---

## 3. Router & Logic Benchmarking Scripts
- [ ] **`bench_gguf.py` Execution Runner:**
  - Evaluate the active classifier model (default: `Arch-Router-1.5B`) complexity F1-score against a test dataset.
  - Test dataset location: `tests/fixtures/grpo_eval_data.json`.
  - Test dataset schema:
    ```json
    [
      {"prompt": "What is 2+2?", "expected_complexity": "simple", "expected_agents": []},
      {"prompt": "Search for recent AI papers and summarize", "expected_complexity": "complex", "expected_agents": ["retrieval", "web_search"]}
    ]
    ```
  - Track cold-start load latencies (first request requiring a VRAM load) and subsequent warm latencies.
  - Assert that VRAM is successfully freed after the idle timeout threshold.
- [ ] **`bench_mmlu.py` Routing Checker:**
  - Run standardized logic benchmarks (GSM8k, HumanEval, MMLU subsets) against the orchestrator's synthesis node to assess logic quality.
  - Measure primary provider failure injection scenarios. Verify that Gemini rate-limit failures successfully trigger fallback chain without crashing the request.
- [ ] **`bench_models.py` Model Comparison (NEW):**
  - Run benchmarks across different model options from the Model Registry.
  - Compare accuracy, latency, and VRAM usage for each role (OCR, ASR, Embedding, Classifier).
  - Output comparison table for model selection decisions.

---

## 4. Asynchronous Kafka Consumers
- [ ] **Real-Time Log Stream Processing:**
  - Run background consumer daemons that subscribe to `guardroute-traces` and `syntraflow-ingestion-jobs` Kafka topics.
  - Process traces asynchronously, extracting latency stats, token counts, and completion text structures.
  - `confluent-kafka` must be added to the `evalops` optional dependency group (currently missing).
- [ ] **Automated Report Generation:**
  - Write metrics results to the PostgreSQL database table `evalops_reports` (note: follows `evalops_` prefix convention).
  - Table schema:
    ```sql
    CREATE TABLE evalops_reports (
        id              SERIAL PRIMARY KEY,
        run_id          UUID NOT NULL,
        benchmark_name  VARCHAR(100) NOT NULL,
        metric_name     VARCHAR(100) NOT NULL,
        metric_value    FLOAT NOT NULL,
        model_name      VARCHAR(200),
        timestamp       TIMESTAMP DEFAULT NOW(),
        metadata_json   JSONB
    );
    ```
  - Flag anomalies (such as responses with high toxicity or low faithfulness) for manual engineer auditing.

---

## 5. Trace Observability & Diagnostics
- [ ] **OpenTelemetry Integration:**
  - Configure the Gateway and Inference servers to export transaction spans to **Jaeger** (all-in-one deployment, single Docker container).
  - Jaeger UI available at `http://localhost:16686`.
  - OTLP gRPC endpoint at `http://localhost:4317`.
- [ ] **LangSmith Integration (LLM-Specific Tracing):**
  - Use LangSmith for LLM-specific observability (prompt debugging, token usage, model comparison).
  - Toggle via `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` in `.env`.
  - This complements (not replaces) Jaeger for general distributed tracing.
- [ ] **Waterfall Timeline Diagnostics:**
  - Map nested timeline spans showing detailed time allocations.
  - Highlight bottlenecks such as OCR parsing latency, embedding times, LiteLLM provider switchover durations, and VRAM cold-start loads.

---

## 6. CI/CD Integration
- [ ] **GitHub Actions Workflow (`.github/workflows/evalops.yml`):**
  - Trigger on: Pull Requests to `main` branch.
  - Steps:
    1. Install dependencies: `poetry install --all-extras`
    2. Lint: `ruff check .` and `mypy .`
    3. Safety tests: `pytest projects/evalops/tests/test_safety.py -v`
    4. Benchmark tests (optional, on label): `pytest projects/evalops/tests/test_benchmarks.py -v`
  - Report results as PR check annotations.
- [ ] **Test Data Management:**
  - Maintain test fixtures in `tests/fixtures/` directory.
  - Version control test datasets with the codebase.
  - Document JSON schemas for all test data files.

---

## 7. EvalOps as Optional Service
- [ ] EvalOps is a QA/CI tool, not a production-critical service.
- [ ] In docker-compose, EvalOps runner is behind the `test` profile (already implemented).
- [ ] Kafka consumers for EvalOps should only start when explicitly enabled (not on default gateway startup).
- [ ] Document that EvalOps requires: `poetry install --extras "evalops"`.

---

## 8. Missing Dependencies (pyproject.toml)
The `evalops` optional dependency group must include:
```toml
evalops = [
    "deepeval (>=4.0.5,<5.0.0)",
    "ragas (>=0.2.0,<1.0.0)",
    "confluent-kafka (>=2.4.0,<3.0.0)",   # NEW: for Kafka consumers
]
```
