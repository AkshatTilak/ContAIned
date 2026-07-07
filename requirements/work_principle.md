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

### Clarity & Collaboration
- If a requirement, contract, or design decision is ambiguous or doesn't make sense, **stop and ask the user for clarification** before making assumptions.
- If you introduce improvements, configurations, or setup flags while executing a task, immediately **update the project-level and submodule-level READMEs** to track these changes for other developers.
