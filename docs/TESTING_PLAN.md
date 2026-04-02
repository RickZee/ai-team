# Testing Implementation Plan

> Comprehensive plan to close test coverage gaps across the ai-team project.

---

## Current State

### What Exists

- **~530 test functions** across **80 files** in `tests/unit/`, `tests/integration/`, `tests/guardrails/`, `tests/e2e/`, `tests/performance/`
- Good infrastructure: `conftest.py` per layer, `StubChatModel` for LangGraph, `mock_ollama_llm` for CrewAI, `AI_TEAM_USE_REAL_LLM` gating, proper pytest markers
- Strong coverage in: guardrails (security, behavioral, quality — including adversarial), LangGraph routing/graph compilation, flow error handling, human feedback, monitor, cost estimation, token tracking
- The `test_main_graph_full_mocked_e2e.py` is a high-value full-graph traversal test

### What's Missing

| Category | Untested Modules | Risk |
|----------|-----------------|------|
| **UI — TUI** | `ui/tui/app.py`, `ui/tui/widgets.py` | Medium — user-facing, default entry point mismatch was already a bug |
| **UI — Web** | `ui/web/server.py`, entire React frontend | Medium — no API endpoint tests, no component tests |
| **Tools** | `git_tools.py`, `architect_tools.py`, `code_tools.py`, `developer_tools.py`, `manager_tools.py`, `qa_tools.py`, `infrastructure.py` | High — tools are the hands of every agent |
| **Backends** | `backends/registry.py`, `crewai_backend/backend.py`, `langgraph_backend/backend.py`, Claude SDK (`orchestrator.py`, `recovery.py`, `streaming.py`, `workspace.py`) | High — the entire Backend protocol layer |
| **Agents** | `architect.py`, `backend_developer.py`, `frontend_developer.py`, `fullstack_developer.py`, `manager.py` | Medium — factory functions, prompt loading |
| **Memory** | `memory_config.py` (LongTermStore, ShortTermStore, EntityStore, MemoryManager) | High — cross-run learning depends on this |
| **RAG** | `rag/pipeline.py`, `rag/config.py`, `rag/vector_store.py` | Medium — knowledge retrieval |
| **Flows** | `flows/state.py` (ProjectState validation), `flows/main_flow.py` (beyond recursion limit) | Medium — state transitions |
| **Models** | `models/architecture.py`, `models/development.py`, `models/requirements.py`, `models/outputs.py`, `models/qa_models.py` | Low — Pydantic validation |
| **Scripts** | `extract_lessons.py`, `ingest_knowledge.py`, `capture_demo.py`, `compare_backends.py` (end-to-end) | Low — CLI wrappers |
| **Config** | `config/llm_factory.py` | Medium — model instantiation for all backends |

---

## Design Principles

1. **Test what breaks in production first.** Tools, backends, and memory are the highest-risk gaps.
2. **No real LLM calls in CI.** All LLM-dependent paths use stubs/mocks. Real-LLM tests gated behind `AI_TEAM_USE_REAL_LLM`.
3. **No real filesystem side effects in unit tests.** Use `tmp_path` fixtures. Git tests use temporary repos.
4. **Textual and FastAPI have test frameworks — use them.** Textual has `pilot` for TUI testing. FastAPI has `TestClient`. Use both.
5. **Every new test file must follow existing conventions.** Naming: `test_{module}.py`. Use existing conftest fixtures. Add markers where appropriate.
6. **Adversarial tests for security-sensitive code.** Git tools (path traversal), file tools (escape attempts), backend registry (unknown backend injection).

---

## Phase 1: Critical Infrastructure (Week 1)

The tools, memory stores, and backend protocol are the foundation everything else depends on.

### 1A. Tool Tests

| Task | File to Create | Module Under Test | Test Count | Effort |
|------|---------------|-------------------|------------|--------|
| [x] - **T1.1** Git tools: init, add, commit, branch, diff, log, status | `tests/unit/tools/test_git_tools.py` | `tools/git_tools.py` | ~25 | 4h |
| [x] - **T1.2** Git tools: protected branch enforcement, naming convention, adversarial paths | `tests/unit/tools/test_git_tools.py` (cont.) | `tools/git_tools.py` | ~10 | 2h |
| [x] - **T1.3** Code tools: code generation, review, sandbox execution | `tests/unit/tools/test_code_tools.py` | `tools/code_tools.py` | ~12 | 2h |
| [x] - **T1.4** Architect tools: architecture analysis, diagram generation | `tests/unit/tools/test_architect_tools.py` | `tools/architect_tools.py` | ~8 | 1.5h |
| [x] - **T1.5** Developer tools: common tools, backend-specific, frontend-specific, fullstack | `tests/unit/tools/test_developer_tools.py` | `tools/developer_tools.py` | ~15 | 2h |
| [x] - **T1.6** Manager tools: task delegation scoring, timeline, blocker resolution | `tests/unit/tools/test_manager_tools.py` | `tools/manager_tools.py` | ~12 | 2h |
| [x] - **T1.7** QA tools: test runner, lint checker, coverage parser | `tests/unit/tools/test_qa_tools.py` | `tools/qa_tools.py` | ~10 | 2h |
| [x] - **T1.8** Infrastructure tools: DevOps tools, Cloud tools | `tests/unit/tools/test_infrastructure_tools.py` | `tools/infrastructure.py` | ~10 | 1.5h |
| [x] - **T1.9** RAG search tool | `tests/unit/tools/test_rag_search.py` | `tools/rag_search.py` | ~5 | 1h |

**T1.1 and T1.2 — Git tools details:**

```python
# tests/unit/tools/test_git_tools.py

class TestGitInit:
    def test_init_creates_repo(self, tmp_path): ...
    def test_init_idempotent_on_existing_repo(self, tmp_path): ...
    def test_init_raises_on_file_not_directory(self, tmp_path): ...

class TestGitBranch:
    def test_creates_and_checkouts_feature_branch(self, tmp_path): ...
    def test_rejects_protected_branch_names(self, tmp_path): ...
    def test_rejects_invalid_branch_format(self, tmp_path): ...
    def test_accepts_all_valid_prefixes(self, tmp_path): ...  # feature/, fix/, chore/, docs/, refactor/, test/, build/

class TestGitCommit:
    def test_commits_staged_changes(self, tmp_path): ...
    def test_blocks_commit_on_main(self, tmp_path): ...
    def test_blocks_commit_on_master(self, tmp_path): ...
    def test_requires_conventional_format(self, tmp_path): ...
    def test_returns_short_sha(self, tmp_path): ...

class TestGitAdd:
    def test_stages_files(self, tmp_path): ...
    def test_rejects_files_outside_repo(self, tmp_path): ...
    def test_rejects_nonexistent_files(self, tmp_path): ...

class TestGitStatus:
    def test_reports_staged_unstaged_untracked(self, tmp_path): ...
    def test_clean_repo(self, tmp_path): ...

class TestGitDiff:
    def test_shows_staged_and_working_tree(self, tmp_path): ...
    def test_no_changes(self, tmp_path): ...

class TestGitLog:
    def test_returns_commit_info_list(self, tmp_path): ...
    def test_limits_results(self, tmp_path): ...

class TestGitAdversarial:
    def test_path_traversal_rejected(self, tmp_path): ...
    def test_symlink_outside_repo_rejected(self, tmp_path): ...
    def test_branch_name_injection(self, tmp_path): ...
```

All tests use `tmp_path` fixture. A `git_repo` fixture initializes a temp repo with an initial commit on a `feature/test` branch (since main is protected).

### 1B. Memory Store Tests

| Task | File to Create | Module Under Test | Test Count | Effort |
|------|---------------|-------------------|------------|--------|
| [x] - **T1.10** LongTermStore: CRUD, retention, patterns, metrics | `tests/unit/memory/test_long_term_store.py` | `memory/memory_config.py` | ~20 | 3h |
| [x] - **T1.11** EntityStore: upsert, relationships, deletion | `tests/unit/memory/test_entity_store.py` | `memory/memory_config.py` | ~12 | 2h |
| [x] - **T1.12** ShortTermStore: add, search, delete (mock ChromaDB) | `tests/unit/memory/test_short_term_store.py` | `memory/memory_config.py` | ~8 | 1.5h |
| [x] - **T1.13** MemoryManager: initialize, store/retrieve dispatch, cleanup, export | `tests/unit/memory/test_memory_manager_full.py` | `memory/memory_config.py` | ~15 | 2h |
| [ ] - **T1.14** Lessons: record_run_failures, extract_lessons, load_role_lessons, dedup, infra backlog | `tests/unit/memory/test_lessons_comprehensive.py` | `memory/lessons.py` | ~20 | 3h |

**T1.10 — LongTermStore details:**

```python
# tests/unit/memory/test_long_term_store.py
# All tests use sqlite_path=":memory:" for isolation

class TestLongTermStoreConversations:
    def test_add_and_retrieve_conversation(self): ...
    def test_filter_by_project_id(self): ...
    def test_limit_respected(self): ...

class TestLongTermStoreMetrics:
    def test_add_metric(self): ...
    def test_get_metrics_summary_aggregation(self): ...
    def test_multiple_roles_and_models(self): ...

class TestLongTermStorePatterns:
    def test_add_and_get_patterns(self): ...
    def test_filter_by_pattern_type(self): ...
    def test_ordering_by_created_at(self): ...

class TestLongTermStoreRetention:
    def test_apply_retention_deletes_old_rows(self): ...
    def test_apply_retention_preserves_recent(self): ...
    def test_apply_retention_across_all_tables(self): ...

class TestLongTermStoreSchema:
    def test_idempotent_schema_init(self): ...
    def test_shared_memory_connection(self): ...
```

### 1C. Backend Protocol Tests

| Task | File to Create | Module Under Test | Test Count | Effort |
|------|---------------|-------------------|------------|--------|
| [x] - **T1.15** Backend registry: discover, instantiate, unknown backend error | `tests/unit/backends/test_registry.py` | `backends/registry.py` | ~8 | 1.5h |
| [x] - **T1.16** CrewAI backend: run() with mocked flow, error handling, result mapping | `tests/unit/backends/test_crewai_backend.py` | `backends/crewai_backend/backend.py` | ~10 | 2h |
| [x] - **T1.17** LangGraph backend: run() with mocked graph, stream(), checkpoint wiring | `tests/unit/backends/test_langgraph_backend.py` | `backends/langgraph_backend/backend.py` | ~12 | 2.5h |
| [x] - **T1.18** Claude SDK backend: workspace setup, orchestrator mock, artifact collection | `tests/unit/backends/test_claude_sdk_backend.py` | `backends/claude_agent_sdk_backend/` | ~10 | 2h |

**Phase 1 total: ~34.5 hours, ~212 tests**

---

## Phase 2: State, Flows & Agents (Week 2)

### 2A. State & Model Validation

| Task | File to Create | Module Under Test | Test Count | Effort |
|------|---------------|-------------------|------------|--------|
| [x] - **T2.1** ProjectState: field defaults, phase lifecycle helpers, retry logic, serialization | `tests/unit/flows/test_project_state.py` | `flows/state.py` | ~15 | 2h |
| [ ] - **T2.2** LangGraphProjectState: TypedDict + reducer behavior with add_messages | `tests/unit/backends/langgraph_backend/test_state_schema.py` | `backends/langgraph_backend/graphs/state.py` | ~8 | 1.5h |
| [ ] - **T2.3** Pydantic models: CodeFile, DeploymentConfig, RequirementsDocument, ArchitectureDocument, QAModels | `tests/unit/models/test_pydantic_models.py` | `models/*.py` | ~20 | 2h |
| [ ] - **T2.4** ComparisonReport: to_markdown (2-backend and 3-backend), snapshot_from_project_result edge cases | `tests/unit/models/test_comparison_report_extended.py` | `models/comparison_report.py` | ~10 | 1.5h |

### 2B. Agent Factory Tests

| Task | File to Create | Module Under Test | Test Count | Effort |
|------|---------------|-------------------|------------|--------|
| [ ] - **T2.5** Architect agent: factory, tool wiring, lesson injection | `tests/unit/agents/test_architect.py` | `agents/architect.py` | ~6 | 1h |
| [ ] - **T2.6** Backend developer: factory, tool wiring | `tests/unit/agents/test_backend_developer.py` | `agents/backend_developer.py` | ~6 | 1h |
| [ ] - **T2.7** Frontend developer: factory, tool wiring | `tests/unit/agents/test_frontend_developer.py` | `agents/frontend_developer.py` | ~6 | 1h |
| [ ] - **T2.8** Fullstack developer: factory, tool wiring | `tests/unit/agents/test_fullstack_developer.py` | `agents/fullstack_developer.py` | ~6 | 1h |
| [ ] - **T2.9** Manager agent: factory, escalation threshold, delegation | `tests/unit/agents/test_manager.py` | `agents/manager.py` | ~8 | 1.5h |
| [ ] - **T2.10** All agents: lesson injection via load_agent_config_with_lessons | `tests/unit/agents/test_lesson_injection.py` | `agents/base.py` | ~8 | 1.5h |

### 2C. Flow Tests

| Task | File to Create | Module Under Test | Test Count | Effort |
|------|---------------|-------------------|------------|--------|
| [ ] - **T2.11** Main flow: phase transitions (happy path, mocked crews) | `tests/unit/flows/test_main_flow_phases.py` | `flows/main_flow.py` | ~12 | 3h |
| [ ] - **T2.12** Flow routing: all conditional routes including retry, escalation, human review | `tests/unit/flows/test_routing_unit.py` | `flows/routing.py` | ~10 | 2h |
| [ ] - **T2.13** LangGraph prompts: build_system_prompt with lessons, RAG context | `tests/unit/backends/langgraph_backend/test_prompts.py` | `backends/langgraph_backend/agents/prompts.py` | ~8 | 1.5h |

### 2D. Config Tests

| Task | File to Create | Module Under Test | Test Count | Effort |
|------|---------------|-------------------|------------|--------|
| [x] - **T2.14** LLM factory: model creation, environment selection, fallback | `tests/unit/config/test_llm_factory.py` | `config/llm_factory.py` | ~10 | 2h |

**Phase 2 total: ~22 hours, ~133 tests**

---

## Phase 3: UI Tests (Week 3)

### 3A. Textual TUI Tests

Textual provides [`App.run_test()`](https://textual.textualize.io/guide/testing/) which returns a `Pilot` for simulating user interaction without a real terminal.

| Task | File to Create | Module Under Test | Test Count | Effort |
|------|---------------|-------------------|------------|--------|
| [x] - **T3.1** TUI app: startup, tab navigation, quit binding | `tests/unit/ui/test_tui_app.py` | `ui/tui/app.py` | ~8 | 2h |
| [x] - **T3.2** TUI: backend selector defaults to crewai (or AI_TEAM_BACKEND env) | `tests/unit/ui/test_tui_app.py` (cont.) | `ui/tui/app.py` | ~4 | 1h |
| [ ] - **T3.3** TUI: Run tab form validation, submission fires worker | `tests/unit/ui/test_tui_app.py` (cont.) | `ui/tui/app.py` | ~6 | 2h |
| [x] - **T3.4** TUI widgets: PhasePipeline, AgentTable, MetricsPanel, GuardrailsLog render | `tests/unit/ui/test_tui_widgets.py` | `ui/tui/widgets.py` | ~10 | 2.5h |
| [ ] - **T3.5** TUI: demo mode runs without error | `tests/unit/ui/test_tui_app.py` (cont.) | `ui/tui/app.py` | ~2 | 30m |

**T3.1–T3.2 — TUI test approach:**

```python
# tests/unit/ui/test_tui_app.py
import os
import pytest
from ai_team.ui.tui.app import AITeamTUI

class TestTUIStartup:
    async def test_app_starts_and_shows_header(self):
        app = AITeamTUI()
        async with app.run_test() as pilot:
            assert app.query_one("Header")

    async def test_tab_navigation(self):
        app = AITeamTUI()
        async with app.run_test() as pilot:
            await pilot.press("r")  # switch to Run tab
            await pilot.press("d")  # switch to Dashboard tab

class TestTUIBackendDefault:
    async def test_defaults_to_crewai(self):
        app = AITeamTUI()
        async with app.run_test() as pilot:
            select = app.query_one("#backend-select", Select)
            assert select.value == "crewai"

    async def test_respects_env_override(self, monkeypatch):
        monkeypatch.setenv("AI_TEAM_BACKEND", "langgraph")
        app = AITeamTUI()
        async with app.run_test() as pilot:
            select = app.query_one("#backend-select", Select)
            assert select.value == "langgraph"
```

### 3B. FastAPI Web Server Tests

FastAPI provides `TestClient` (sync, no server startup needed).

| Task | File to Create | Module Under Test | Test Count | Effort |
|------|---------------|-------------------|------------|--------|
| [x] - **T3.6** API endpoints: GET /api/profiles, GET /api/backends | `tests/unit/ui/test_web_server.py` | `ui/web/server.py` | ~6 | 1.5h |
| [x] - **T3.7** API endpoints: POST /api/estimate, POST /api/demo | `tests/unit/ui/test_web_server.py` (cont.) | `ui/web/server.py` | ~6 | 1.5h |
| [x] - **T3.8** WebSocket: /ws/run connection, message format, error handling | `tests/unit/ui/test_web_websocket.py` | `ui/web/server.py` | ~8 | 2.5h |
| [x] - **T3.9** Backend default consistency: web server defaults match CLI | `tests/unit/ui/test_web_server.py` (cont.) | `ui/web/server.py` | ~3 | 30m |

### 3C. React Frontend Tests (optional but recommended)

| Task | File to Create | Module Under Test | Test Count | Effort |
|------|---------------|-------------------|------------|--------|
| [ ] - **T3.10** Setup Vitest + React Testing Library | `ui/web/frontend/vitest.config.ts`, `package.json` scripts | — | — | 2h |
| [ ] - **T3.11** Dashboard page: renders, connects to WebSocket mock | `ui/web/frontend/src/pages/__tests__/Dashboard.test.tsx` | `Dashboard.tsx` | ~5 | 2h |
| [ ] - **T3.12** Run page: form defaults, backend selector, submission | `ui/web/frontend/src/pages/__tests__/Run.test.tsx` | `Run.tsx` | ~6 | 2h |
| [ ] - **T3.13** Compare page: renders comparison table | `ui/web/frontend/src/pages/__tests__/Compare.test.tsx` | `Compare.tsx` | ~4 | 1.5h |

**Phase 3 total: ~21.5 hours, ~68 tests**

---

## Phase 4: RAG, LangGraph Internals & Claude SDK (Week 4)

### 4A. RAG Pipeline

| Task | File to Create | Module Under Test | Test Count | Effort |
|------|---------------|-------------------|------------|--------|
| [ ] - **T4.1** RAG pipeline: ingest_chunks, retrieve, format_context (mocked ChromaDB) | `tests/unit/rag/test_pipeline.py` | `rag/pipeline.py` | ~12 | 2h |
| [ ] - **T4.2** RAG config: enabled/disabled, collection name | `tests/unit/rag/test_rag_config.py` | `rag/config.py` | ~5 | 1h |
| [ ] - **T4.3** RAG vector store: abstraction layer | `tests/unit/rag/test_vector_store.py` | `rag/vector_store.py` | ~5 | 1h |

### 4B. LangGraph Internals

| Task | File to Create | Module Under Test | Test Count | Effort |
|------|---------------|-------------------|------------|--------|
| [ ] - **T4.4** LangGraph chat: model creation per role, temperature, callbacks | `tests/unit/backends/langgraph_backend/test_langgraph_chat.py` | `backends/langgraph_backend/graphs/langgraph_chat.py` | ~8 | 1.5h |
| [ ] - **T4.5** LangGraph guardrail hooks: post-model hook writes to state, retry routing | `tests/unit/backends/langgraph_backend/test_guardrail_hooks.py` | `backends/langgraph_backend/graphs/guardrail_hooks.py` | ~8 | 1.5h |
| [ ] - **T4.6** Subgraph runners: snapshot_workspace_files, planning output parsing | `tests/unit/backends/langgraph_backend/test_subgraph_runners.py` | `backends/langgraph_backend/graphs/subgraph_runners.py` | ~10 | 2h |
| [ ] - **T4.7** State inspection utilities | `tests/unit/backends/langgraph_backend/test_state_inspection.py` | `backends/langgraph_backend/state_inspection.py` | ~5 | 1h |

### 4C. Claude Agent SDK Backend

| Task | File to Create | Module Under Test | Test Count | Effort |
|------|---------------|-------------------|------------|--------|
| [ ] - **T4.8** Orchestrator: phase routing, subagent dispatch (mocked SDK) | `tests/unit/backends/test_claude_orchestrator.py` | `backends/claude_agent_sdk_backend/orchestrator.py` | ~10 | 2.5h |
| [ ] - **T4.9** Recovery: checkpoint restore, error recovery strategies | `tests/unit/backends/test_claude_recovery.py` | `backends/claude_agent_sdk_backend/recovery.py` | ~8 | 2h |
| [ ] - **T4.10** Streaming: event parsing, progress extraction | `tests/unit/backends/test_claude_streaming.py` | `backends/claude_agent_sdk_backend/streaming.py` | ~8 | 1.5h |
| [ ] - **T4.11** Workspace: snapshot, file tracking, artifact collection | `tests/unit/backends/test_claude_workspace.py` | `backends/claude_agent_sdk_backend/workspace.py` | ~8 | 1.5h |
| [ ] - **T4.12** Claude prompts: build_system_prompt, role-specific prompts | `tests/unit/backends/test_claude_prompts.py` | `backends/claude_agent_sdk_backend/agents/prompts.py` | ~6 | 1h |

**Phase 4 total: ~17.5 hours, ~93 tests**

---

## Phase 5: Integration & E2E Expansion (Week 5)

### 5A. Cross-Layer Integration

| Task | File to Create | Module Under Test | Test Count | Effort |
|------|---------------|-------------------|------------|--------|
| [ ] - **T5.1** Lessons end-to-end: run → record_run_failures → extract_lessons → load_role_lessons → verify prompt injection | `tests/integration/test_self_improvement_loop.py` | `memory/lessons.py`, `agents/base.py`, `backends/langgraph_backend/agents/prompts.py` | ~8 | 3h |
| [ ] - **T5.2** Backend comparison end-to-end: run both backends on demo, verify ComparisonReport fields | `tests/integration/test_backend_comparison_e2e.py` | `utils/backend_comparison.py`, `models/comparison_report.py` | ~5 | 2h |
| [ ] - **T5.3** Memory integration: MemoryManager → LongTermStore → lessons → prompt injection chain | `tests/integration/test_memory_lessons_chain.py` | `memory/`, `agents/` | ~6 | 2h |
| [x] - **T5.4** Git tools integration: init → branch → write files → add → commit → log → status (real git, temp dir) | `tests/integration/test_git_workflow.py` | `tools/git_tools.py` | ~8 | 2h |
| [ ] - **T5.5** RAG integration: ingest → retrieve → format → verify relevance (mocked embeddings) | `tests/integration/test_rag_pipeline.py` | `rag/pipeline.py` | ~5 | 1.5h |
| [ ] - **T5.6** File tools + workspace isolation: per-project path scoping, traversal rejection | `tests/integration/test_workspace_isolation.py` | `tools/file_tools.py` | ~6 | 1.5h |

### 5B. E2E Tests

| Task | File to Create | Module Under Test | Test Count | Effort |
|------|---------------|-------------------|------------|--------|
| [ ] - **T5.7** E2E: full LangGraph pipeline with stub model (planning → dev → testing → deployment) | `tests/e2e/test_e2e_langgraph.py` | Full LangGraph pipeline | ~3 | 3h |
| [ ] - **T5.8** E2E: full CrewAI pipeline with mocked LLM (planning → dev → testing) | `tests/e2e/test_e2e_crewai.py` | Full CrewAI pipeline | ~3 | 3h |
| [ ] - **T5.9** E2E: CLI invocation (subprocess) — `ai-team run --backend langgraph --skip-estimate` | `tests/e2e/test_e2e_cli.py` | `main.py`, CLI args | ~4 | 2h |

### 5C. Adversarial & Security Tests

| Task | File to Create | Module Under Test | Test Count | Effort |
|------|---------------|-------------------|------------|--------|
| [x] - **T5.10** File tools adversarial: symlink escape, `..` traversal, sensitive filename rejection, max depth | `tests/unit/tools/test_file_tools_adversarial.py` | `tools/file_tools.py` | ~12 | 2h |
| [x] - **T5.11** Git tools adversarial: branch name injection, commit message injection, path escape | `tests/unit/tools/test_git_tools_adversarial.py` | `tools/git_tools.py` | ~8 | 1.5h |
| [x] - **T5.12** Backend registry adversarial: unknown backend, None input, empty string | `tests/unit/backends/test_registry_adversarial.py` | `backends/registry.py` | ~5 | 1h |

**Phase 5 total: ~24.5 hours, ~73 tests**

---

## Phase 6: Scripts, Reports & Remaining Gaps (Week 6)

| Task | File to Create | Module Under Test | Test Count | Effort |
|------|---------------|-------------------|------------|--------|
| [ ] - **T6.1** extract_lessons CLI: argparse, threshold flag, output | `tests/unit/scripts/test_extract_lessons_cli.py` | `scripts/extract_lessons.py` | ~5 | 1h |
| [ ] - **T6.2** ingest_knowledge CLI: argparse, directory validation | `tests/unit/scripts/test_ingest_knowledge.py` | `scripts/ingest_knowledge.py` | ~4 | 1h |
| [ ] - **T6.3** compare_backends CLI: argparse, demo loading, output formats | `tests/unit/scripts/test_compare_backends_cli.py` | `scripts/compare_backends.py` | ~5 | 1h |
| [ ] - **T6.4** Manager self-improvement report: build, render markdown, narrative skip | `tests/unit/reports/test_manager_report_extended.py` | `reports/manager_self_improvement.py` | ~8 | 1.5h |
| [ ] - **T6.5** LLM wrapper: retry, timeout, fallback | `tests/unit/utils/test_llm_wrapper.py` | `utils/llm_wrapper.py` | ~6 | 1h |
| [ ] - **T6.6** Reasoning utils: extraction, validation | `tests/unit/utils/test_reasoning.py` | `utils/reasoning.py` | ~5 | 1h |
| [ ] - **T6.7** CrewAI markdown sources: loading, formatting | `tests/unit/memory/test_crewai_markdown_sources.py` | `memory/crewai_markdown_sources.py` | ~4 | 1h |
| [ ] - **T6.8** Crew unit tests: planning_crew, dev_crew, testing_crew, deployment_crew task generation | `tests/unit/crews/test_crew_construction.py` | `crews/*.py` | ~12 | 2h |
| [ ] - **T6.9** Task definitions: planning, development, testing, deployment task factory functions | `tests/unit/tasks/test_task_definitions.py` | `tasks/*.py` | ~10 | 1.5h |

**Phase 6 total: ~12 hours, ~59 tests**

---

## Summary

| Phase | Week | Tests | Effort | Focus |
|-------|------|-------|--------|-------|
| 1. Critical Infrastructure | 1 | ~212 | ~34.5h | Tools, memory stores, backend protocol |
| 2. State, Flows & Agents | 2 | ~133 | ~22h | State validation, agent factories, flow phases |
| 3. UI Tests | 3 | ~68 | ~21.5h | Textual TUI (pilot), FastAPI (TestClient), React (Vitest) |
| 4. RAG, LangGraph & Claude SDK | 4 | ~93 | ~17.5h | RAG pipeline, LangGraph internals, Claude SDK modules |
| 5. Integration & E2E | 5 | ~73 | ~24.5h | Cross-layer chains, full pipeline E2E, adversarial |
| 6. Scripts & Remaining | 6 | ~59 | ~12h | CLI scripts, reports, crews, tasks |
| **Total** | **6 weeks** | **~638** | **~132h** | **From ~530 to ~1,168 tests** |

### New Test Files Summary

```
tests/
├── unit/
│   ├── tools/
│   │   ├── test_git_tools.py                    # T1.1, T1.2
│   │   ├── test_code_tools.py                   # T1.3
│   │   ├── test_architect_tools.py              # T1.4
│   │   ├── test_developer_tools.py              # T1.5
│   │   ├── test_manager_tools.py                # T1.6
│   │   ├── test_qa_tools.py                     # T1.7
│   │   ├── test_infrastructure_tools.py         # T1.8
│   │   ├── test_rag_search.py                   # T1.9
│   │   ├── test_file_tools_adversarial.py       # T5.10
│   │   └── test_git_tools_adversarial.py        # T5.11
│   ├── memory/
│   │   ├── test_long_term_store.py              # T1.10
│   │   ├── test_entity_store.py                 # T1.11
│   │   ├── test_short_term_store.py             # T1.12
│   │   ├── test_memory_manager_full.py          # T1.13
│   │   ├── test_lessons_comprehensive.py        # T1.14
│   │   └── test_crewai_markdown_sources.py      # T6.7
│   ├── backends/
│   │   ├── test_registry.py                     # T1.15
│   │   ├── test_registry_adversarial.py         # T5.12
│   │   ├── test_crewai_backend.py               # T1.16
│   │   ├── test_langgraph_backend.py            # T1.17
│   │   ├── test_claude_sdk_backend.py           # T1.18
│   │   ├── test_claude_orchestrator.py          # T4.8
│   │   ├── test_claude_recovery.py              # T4.9
│   │   ├── test_claude_streaming.py             # T4.10
│   │   ├── test_claude_workspace.py             # T4.11
│   │   ├── test_claude_prompts.py               # T4.12
│   │   └── langgraph_backend/
│   │       ├── test_state_schema.py             # T2.2
│   │       ├── test_langgraph_chat.py           # T4.4
│   │       ├── test_guardrail_hooks.py          # T4.5
│   │       ├── test_subgraph_runners.py         # T4.6
│   │       ├── test_state_inspection.py         # T4.7
│   │       └── test_prompts.py                  # T2.13
│   ├── flows/
│   │   ├── test_project_state.py                # T2.1
│   │   ├── test_main_flow_phases.py             # T2.11
│   │   └── test_routing_unit.py                 # T2.12
│   ├── models/
│   │   ├── test_pydantic_models.py              # T2.3
│   │   └── test_comparison_report_extended.py   # T2.4
│   ├── agents/
│   │   ├── test_architect.py                    # T2.5
│   │   ├── test_backend_developer.py            # T2.6
│   │   ├── test_frontend_developer.py           # T2.7
│   │   ├── test_fullstack_developer.py          # T2.8
│   │   ├── test_manager.py                      # T2.9
│   │   └── test_lesson_injection.py             # T2.10
│   ├── config/
│   │   └── test_llm_factory.py                  # T2.14
│   ├── rag/
│   │   ├── test_pipeline.py                     # T4.1
│   │   ├── test_rag_config.py                   # T4.2
│   │   └── test_vector_store.py                 # T4.3
│   ├── ui/
│   │   ├── test_tui_app.py                      # T3.1–T3.5
│   │   ├── test_tui_widgets.py                  # T3.4
│   │   ├── test_web_server.py                   # T3.6, T3.7, T3.9
│   │   └── test_web_websocket.py                # T3.8
│   ├── crews/
│   │   └── test_crew_construction.py            # T6.8
│   ├── tasks/
│   │   └── test_task_definitions.py             # T6.9
│   ├── utils/
│   │   ├── test_llm_wrapper.py                  # T6.5
│   │   └── test_reasoning.py                    # T6.6
│   ├── reports/
│   │   └── test_manager_report_extended.py      # T6.4
│   └── scripts/
│       ├── test_extract_lessons_cli.py          # T6.1
│       ├── test_ingest_knowledge.py             # T6.2
│       └── test_compare_backends_cli.py         # T6.3
├── integration/
│   ├── test_self_improvement_loop.py            # T5.1
│   ├── test_backend_comparison_e2e.py           # T5.2
│   ├── test_memory_lessons_chain.py             # T5.3
│   ├── test_git_workflow.py                     # T5.4
│   ├── test_rag_pipeline.py                     # T5.5
│   └── test_workspace_isolation.py              # T5.6
├── e2e/
│   ├── test_e2e_langgraph.py                    # T5.7
│   ├── test_e2e_crewai.py                       # T5.8
│   └── test_e2e_cli.py                          # T5.9
└── ui/web/frontend/src/pages/__tests__/
    ├── Dashboard.test.tsx                        # T3.11
    ├── Run.test.tsx                              # T3.12
    └── Compare.test.tsx                          # T3.13
```

### Fixtures to Add

| Fixture | conftest.py | Purpose |
|---------|-------------|---------|
| `git_repo` | `tests/unit/tools/conftest.py` | Temp git repo with initial commit on `feature/test` branch |
| `memory_store` | `tests/unit/memory/conftest.py` | In-memory `LongTermStore` (`:memory:` SQLite) |
| `entity_store` | `tests/unit/memory/conftest.py` | In-memory `EntityStore` |
| `mock_chromadb` | `tests/unit/memory/conftest.py` | Mocked ChromaDB client for ShortTermStore |
| `project_workspace` | `tests/integration/conftest.py` | Temp directory with initialized git repo + sample files |
| `web_client` | `tests/unit/ui/conftest.py` | FastAPI `TestClient` instance |
| `tui_app` | `tests/unit/ui/conftest.py` | `AITeamTUI` instance for Textual pilot testing |

### Coverage Target

| Metric | Current | After Plan |
|--------|---------|------------|
| Test count | ~530 | ~1,168 |
| Source modules with zero tests | ~65 | ~5 (historical/deprecated only) |
| Tool modules tested | 1 of 9 | 9 of 9 |
| Backend modules tested | partial | all 3 backends + registry |
| UI tested | 0 | TUI + web API + React components |
| Guardrails | strong | strong + adversarial expansion |
