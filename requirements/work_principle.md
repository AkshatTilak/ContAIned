# Standard Operating Procedure: How to Select and Implement Tasks (`work_on_task.md`)

This document outlines the strict protocol and guidelines for developers and AI agents when selecting, executing, integrating, and documenting tasks within the Akshat AI Platform Monorepo.

---

## 1. Task Selection Limits
- **Max Active Load:** You may select and work on **no more than 3 tasks** simultaneously.
- **Dependency First:** Prioritize fundamental core/infra tasks (e.g., shared clients in `common/`, docker-compose services) before working on upstream submodules (SyntraFlow, GuardRoute, EvalOps).

---

## 2. Core Execution Principles

### Complete & Integrated Delivery
- Every task must be completed **fully and end-to-end**.
- Implementation is not complete until it is fully integrated across all submodules.
- Update any associated documentation, settings keys, and configuration overrides as part of the task completion.

### DRY (Don't Repeat Yourself) & Modularity
- **Never implement duplicate code.** If another project or submodule does something similar, refactor it into a shared utility in the `common/` package.
- Keep components focused, modular, and reusable. Avoid ad-hoc utility implementations inside submodules if they belong in a centralized library.

---

## 3. Scope Management & Tracking

### Out-of-Scope Issues
- If you run into an issue, bug, or design choice that is **beyond the scope of the current task**:
  1. Do **NOT** attempt to resolve it silently as part of your active work.
  2. Instead, locate the original requirement file (e.g., `requirements/system.md`, `requirements/common.md`) that covers that domain.
  3. Create a **new task check-box item** in that original file to track the issue separately.
  4. Continue focusing solely on your original task.

### Status Tracking &original Requirements Updates
- Always update the status of checklist items in the original requirement markdown files:
  - Mark selected active tasks as in-progress using `[/]`.
  - Mark completed tasks as `[x]`.
  - Leave unstarted tasks as `[ ]`.

---

## 4. Quality, Design, & Maintainability

### Standard Practices
- Follow standard pythonic designs, explicit typing, and Pydantic validation structures.
- Ensure proper logging and transaction tracing is integrated via the `common.observability` framework.
- Write tests (EvalOps benchmarks, safety checks, or unit tests) alongside any new code features.
- **Docker for Testing:** If needed, use Docker and containers for whatever tests are needed (e.g. databases, message brokers, or integration environment setups).
- **Dependency Verification:** Always verify `pyproject.toml` when checking off tasks that mention adding new dependencies. Ensure packages are actually moved or added to the correct block (`dependencies` vs `optional-dependencies`).

### Clarity & Collaboration
- If a requirement, contract, or design decision is ambiguous or doesn't make sense, **stop and ask the user for clarification** before making assumptions.
- If you introduce improvements, configurations, or setup flags while executing a task, immediately **update the project-level and submodule-level READMEs** to track these changes for other developers.
- If you need valid environment variables, API keys, or custom configuration parameters in `.env` to properly test and execute any part of the base project or project submodules, explicitly prompt or ask the user to provide these values.


### Documentation & Version Verification
- **Check Documentation Online:** Before modifying or adding code, check the official online documentation to ensure proper implementation details, best practices, and compatibility with the specific library versions defined in [pyproject.toml](file:///c:/Akshat/ContAIned/pyproject.toml).
- **Official Documentation Sources:** Refer to these resources for packages listed in [pyproject.toml](file:///c:/Akshat/ContAIned/pyproject.toml):
  - **Hugging Face & ML:** [Hugging Face Docs](https://huggingface.co/docs), [Transformers Docs](https://huggingface.co/docs/transformers/index), [Sentence Transformers](https://sbert.net/)
  - **LLM Orchestration & Clients:** [LangChain Docs](https://python.langchain.com/v0.3/docs/introduction/), [LangGraph Docs](https://langchain-ai.github.io/langgraph/), [LiteLLM Docs](https://docs.litellm.ai/)
  - **API & Data Validation:** [FastAPI Docs](https://fastapi.tiangolo.com/), [Pydantic v2 Docs](https://docs.pydantic.dev/latest/)
  - **Database & Storage:** [SQLAlchemy v2 Docs](https://docs.sqlalchemy.org/en/20/), [Qdrant Docs](https://qdrant.tech/documentation/), [Neo4j Python Driver](https://neo4j.com/docs/python-manual/current/)
  - **Evaluation & MLOps:** [DeepEval Docs](https://docs.confident-ai.com/), [Ragas Docs](https://docs.ragas.io/en/stable/), [MLflow Docs](https://mlflow.org/docs/latest/index.html)
  - **Other Integrations:** [Model Context Protocol (MCP)](https://modelcontextprotocol.io/), [Llama.cpp Python](https://abetlen.github.io/llama-cpp-python/), [Confluent Kafka Python](https://docs.confluent.io/platform/current/clients/confluent-kafka-python/html/index.html)
