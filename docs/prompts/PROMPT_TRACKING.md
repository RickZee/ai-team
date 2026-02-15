# Prompt tracking

**Source:** [PROMPTS.md](PROMPTS.md) — Complete Cursor AI Prompts Reference

Status key: **Done** = completed; **Pending** = not yet done.

### Run in parallel

Prompts in the same parallel group have no dependency on each other and can be executed concurrently (e.g. in separate Cursor sessions or agents). Order between groups matters: run earlier groups first.

| Phase | Parallel group | IDs | Notes |
|-------|----------------|-----|--------|
| 0 | 1 | 0.1, 0.2, 0.3, 0.4, 0.5 | All prep/research prompts are independent. |
| 1 | 1 | 1.1 | Run first (creates scaffold). |
| 1 | 2 | 1.2, 1.3, 1.4, 1.5 | After 1.1; independent files/modules. |
| 2 | 1 | 2.1 | Run first (Base Agent; others extend it). |
| 2 | 2 | 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11, 2.12, 2.13, 2.14 | After 2.1; agents, tools, and guardrails are independent. |
| 3 | 1 | 3.1, 3.2, 3.3, 3.4 | Task definitions; independent. |
| 3 | 2 | 3.5, 3.6, 3.7, 3.8, 3.9 | After 3.1–3.4; crews and state models. |
| 3 | 3 | 3.10 | Main flow (depends on crews + state). |
| 3 | 4 | 3.11, 3.12, 3.13 | After 3.10; routing, HiL, error handling. |
| 4 | 1 | 4.1–4.3 | Memory config first. |
| 4 | 2 | 4.4, 4.5, 4.6, 4.7 | After 4.1–4.3; knowledge, reasoning, models, callbacks. |
| 4 | 3 | 4.8 | After 4.4–4.7; integration tests. |
| 5 | 1 | 5.1, 5.2, 5.3, 5.4, 5.5 | Test suites; independent. |
| 5 | 2 | 5.6, 5.7, 5.8 | Demo projects; independent. |
| 5 | 3 | 5.9 | After 5.6–5.8 optional; iteration script. |
| 6 | 1 | 6.2, 6.3, 6.4 | UI components; independent. |
| 6 | 2 | 6.1 | Main Gradio app (uses 6.2–6.4). |
| 6 | 3 | 6.5, 6.6, 6.7, 6.8 | After 6.1; recording, docs, polish, social. |

---

## Phase 0: Preparation & Research (Days 1–3)

| ID   | Prompt | File | Status | Notes |
|------|--------|------|--------|------|
| 0.1  | Generate pyproject.toml | [phase-0-1-pyproject-toml.md](phase-0-1-pyproject-toml.md) | **Done** | Poetry pyproject.toml with requested deps, dev deps (black, ruff, mypy, pytest-cov), scripts `ai-team` and `ai-team-ui`. Added `ai_team.ui` stub and Gradio launcher. |
| 0.2  | Generate Ollama setup script | [phase-0-2-ollama-setup-script.md](phase-0-2-ollama-setup-script.md) | **Done** | `scripts/setup_ollama.sh`: install/start Ollama, pull qwen3, qwen2.5-coder, deepseek-r1, deepseek-coder-v2; `--small` for :14b; VRAM estimates, verify test, .env with role assignments, summary table. Bash 3.2–compatible (no associative arrays). |
| 0.3  | Generate model benchmark script | [phase-0-3-model-benchmark-script.md](phase-0-3-model-benchmark-script.md) | **Done** | `scripts/test_models.py` benchmarks code gen, reasoning, instruction-following, latency, throughput; outputs JSON + Rich table; recommendation mapping by agent role. Uses langchain-ollama. |
| 0.4  | Generate CrewAI reference document | [phase-0-4-crewai-reference-document.md](phase-0-4-crewai-reference-document.md) | **Done** | Created docs/CREWAI_REFERENCE.md; covers agents, tasks, crews, flows, memory, guardrails, tools, callbacks/hooks with code snippets. Memory section notes unified API (LanceDB default); legacy ChromaDB/SQLite refs noted. |
| 0.5  | Generate architecture design document | [phase-0-5-architecture-design-document.md](phase-0-5-architecture-design-document.md) | **Done** | docs/ARCHITECTURE.md created with overview diagram, component layers, data flow, state machine, tech stack, directory mapping, integration guide, ADRs 001–003. |

---

## Phase 1: Repository Setup & Environment (Days 4–6)

| ID   | Prompt | File | Status | Notes |
|------|--------|------|--------|------|
| 1.1  | Generate project scaffold | [phase-1-1-project-scaffold.md](phase-1-1-project-scaffold.md) | **Done** | Full `src/ai_team/` (config, agents, crews, flows, tools, guardrails, memory, utils) with `__init__.py` + docstrings; tests (unit/integration/e2e) with conftest.py; docs ARCHITECTURE, AGENTS, GUARDRAILS, FLOWS, TOOLS, MEMORY; scripts (setup_ollama.sh, test_models.py, run_demo.py); ui app.py + components/ + pages/; demos 01_hello_world, 02_todo_app (input.json, expected_output.json); .env.example, py.typed; .gitignore includes Docker. |
| 1.2  | Generate settings module | [phase-1-2-settings-module.md](phase-1-2-settings-module.md) | **Done** | Pydantic Settings in `src/ai_team/config/settings.py`: OllamaSettings (base_url, per-role models, default_model, request_timeout, max_retries, check_health()), GuardrailSettings (max_retries per type, thresholds, dangerous_patterns, pii_patterns, enable flags), MemorySettings (chromadb_path, sqlite_path, embedding_model, collection_name, memory_enabled), LoggingSettings (log_level, log_format, log_file), ProjectSettings (output_dir, workspace_dir, max_iterations, default_timeout). Loads from .env; Settings.from_yaml(path) for YAML; validate_ollama_connection() on root. |
| 1.3  | Generate Dockerfile and docker-compose | [phase-1-3-dockerfile-and-docker-compose.md](phase-1-3-dockerfile-and-docker-compose.md) | **Done** | Multi-stage Dockerfile (Python 3.11-slim, Poetry, non-root user `aiteam`, port 7860, healthcheck, entrypoint `poetry run ai-team-ui`), `.dockerignore`, docker-compose (app + ollama, shared network, .env, ./output and ollama_models volumes; GPU block optional for non-NVIDIA hosts). |
| 1.4  | Generate CI/CD pipeline | [phase-1-4-cicd-pipeline.md](phase-1-4-cicd-pipeline.md) | **Done** | `.github/workflows/ci.yml`: triggers on push to main/develop and PRs; matrix Python 3.11/3.12; jobs lint (ruff, mypy), test (pytest unit + coverage artifact), integration-test (main only), security (bandit, pip-audit); Poetry cache; test result artifacts; badge and branch-protection comments. `.github/workflows/release.yml`: on tag v*; build/push image to GHCR; GitHub Release with generated changelog. |
| 1.5  | Generate initial documentation | [phase-1-5-initial-documentation.md](phase-1-5-initial-documentation.md) | **Done** | README.md (badges, features, architecture ASCII, quick start, config, demos, testing, structure, contributing, license). CONTRIBUTING.md (dev setup, black/ruff/mypy, PR process, commit convention, adding agents/tools/guardrails). docs/GETTING_STARTED.md (prerequisites, installation, first run, troubleshooting: Ollama, model not found, VRAM). |

---

## Phase 2: Agent Definition, Tools & Guardrails (Days 7–14)

| ID   | Prompt | File | Status | Notes |
|------|--------|------|--------|------|
| 2.1  | Generate Base Agent class | [phase-2-1-base-agent-class.md](phase-2-1-base-agent-class.md) | **Done** | Implemented in `src/ai_team/agents/base.py`: BaseAgent extends CrewAI Agent with YAML/settings config, Ollama LLM (role→model mapping), structlog, memory hooks (before_task/after_task), guardrail-wrapped tools, tenacity retry on LLM, token usage tracking, create_agent(role_name) factory, attach_tools(), health_check(). Unit tests in `tests/unit/agents/test_base.py`. CrewAI Agent is Pydantic; custom attributes set via object.__setattr__ after super().__init__. |
| 2.2  | Generate Manager Agent | [phase-2-2-manager-agent.md](phase-2-2-manager-agent.md) | **Done** | YAML in config/agents.yaml (manager). Python in agents/manager.py + tools/manager_tools.py. Tools: task_delegation, timeline_management, blocker_resolution, status_reporting. Delegation by capability/workload; human escalation threshold; ProjectState integration via status_reporting/timeline_management. |
| 2.3  | Generate Product Owner Agent | [phase-2-3-product-owner-agent.md](phase-2-3-product-owner-agent.md) | **Done** | YAML updated in config/agents.yaml. Implemented in agents/product_owner.py (extends BaseAgent via create_agent), tools in tools/product_owner.py (requirements_parser, user_story_generator, acceptance_criteria_writer, priority_scorer). RequirementsDocument and related Pydantic models in models/requirements.py. Self-validation and guardrail (reject vague/contradictory) in product_owner + tools. Templates in agents/product_owner_templates.py (API, web app, CLI, data pipeline). |
| 2.4  | Generate Architect Agent | [phase-2-4-architect-agent.md](phase-2-4-architect-agent.md) | **Done** | agents/architect.py + create_architect_agent(); ArchitectureDocument in models/architecture.py; architect tools in tools/architect_tools.py; validate_architecture_against_requirements() guardrail. |
| 2.5  | Generate Developer Agents (Backend, Frontend, Fullstack) | [phase-2-5-developer-agents-backend-frontend-fullstack.md](phase-2-5-developer-agents-backend-frontend-fullstack.md) | **Done** | `developer_base.py` (DeveloperBase + validate_generated_code, context_instruction), `developer_tools.py` (stub tools), `backend_developer.py`, `frontend_developer.py`, `fullstack_developer.py`; YAML + fullstack in settings; guardrail integration on generated code. |
| 2.6  | Generate DevOps and Cloud Agents | [phase-2-6-devops-and-cloud-agents.md](phase-2-6-devops-and-cloud-agents.md) | **Done** | `agents/devops_engineer.py` (DevOpsEngineer) and `agents/cloud_engineer.py` (CloudEngineer) use create_agent with YAML config (allow_delegation: false, max_iter: 10). Tools in `tools/infrastructure.py`: DevOps — dockerfile_generator, compose_generator, ci_pipeline_generator, k8s_manifest_generator, monitoring_config_generator; Cloud — terraform_generator, cloudformation_generator, iam_policy_generator, cost_estimator, network_designer. SecurityGuardrails.validate_iac_security() added for Dockerfile, docker-compose, K8s, Terraform, CloudFormation, IAM; all generated IaC validated before return. |
| 2.7  | Generate QA Agent | [phase-2-7-qa-agent.md](phase-2-7-qa-agent.md) | **Done** | agents/qa_engineer.py + tools/qa_tools.py; TestResult and QA models in models/qa_models.py; config/agents.yaml qa_engineer; quality gates (min coverage 80%, zero critical bugs); feedback_for_developers for retry to devs. Guardrail: >80% coverage. |
| 2.8  | Generate secure file tools | [phase-2-8-secure-file-tools.md](phase-2-8-secure-file-tools.md) | **Done** | Implemented in `src/ai_team/tools/file_tools.py`: read_file, write_file, list_directory, create_directory, delete_file with path traversal prevention, whitelist (workspace/output), dangerous pattern and optional PII scanning, max_file_size_kb, audit logging. Both raw functions and @tool-decorated versions; tests in `tests/unit/tools/test_file_tools.py` including adversarial paths. |
| 2.9  | Generate code execution sandbox tools | [phase-2-9-code-execution-sandbox-tools.md](phase-2-9-code-execution-sandbox-tools.md) | **Done** | `src/ai_team/tools/code_tools.py`: execute_python (import guard, resource limits on Unix, timeout), execute_shell (whitelist/blocklist), lint_code (ruff/eslint), format_code (black/prettier). ExecutionResult and LintResult Pydantic models; CrewAI BaseTool wrappers and get_code_tools(). Audit logging, temp dir cleanup. |
| 2.10 | Generate Git tools | [phase-2-10-git-tools.md](phase-2-10-git-tools.md) | **Done** | `src/ai_team/tools/git_tools.py`: git_init, git_add, git_commit, git_branch, git_diff, git_log, git_status, generate_commit_message, create_pr_description. Pydantic CommitInfo, GitStatus. GitPython; LLM (Ollama) for commit message and PR description. Safety: no commits on main/master, branch naming type/name. |
| 2.11 | Generate test runner tools | [phase-2-11-test-runner-tools.md](phase-2-11-test-runner-tools.md) | **Done** | Implemented in `src/ai_team/tools/test_tools.py`: run_pytest (with coverage + retry 2x on failure), run_specific_test (single test + traceback, retry 2x), generate_coverage_report (HTML/JSON, uncovered lines, suggestions), run_lint (ruff + mypy, severity aggregation), validate_test_quality (assertions, names, hardcoded values, setup/teardown, edge cases). Pydantic models: TestRunResult, TestResult, CoverageReport, LintReport, TestQualityReport; CrewAI BaseTool wrappers and get_test_tools(). |
| 2.12 | Generate behavioral guardrails module | [phase-2-12-behavioral-guardrails-module.md](phase-2-12-behavioral-guardrails-module.md) | **Done** | `src/ai_team/guardrails/behavioral.py`: GuardrailResult, role_adherence, scope_control, delegation, output_format, iteration_limit; CrewAI helpers (guardrail_to_crewai_callable, make_*). Unit tests in `tests/unit/guardrails/test_behavioral.py`. |
| 2.13 | Generate security guardrails module | [phase-2-13-security-guardrails-module.md](phase-2-13-security-guardrails-module.md) | **Done** | Implemented in `src/ai_team/guardrails/security.py`: GuardrailResult; code_safety_guardrail (configurable patterns, severity levels); pii_redaction_guardrail (detection + redacted text); secret_detection_guardrail; prompt_injection_guardrail (sensitivity); path_security_guardrail (traversal, symlinks, system dirs). CrewAI adapters (crewai_*_guardrail) and SECURITY_TASK_GUARDRAILS. Unit tests in `tests/unit/guardrails/test_security.py` with adversarial cases. Legacy SecurityGuardrails in __init__.py retained for compatibility. |
| 2.14 | Generate quality guardrails module | [phase-2-14-quality-guardrails-module.md](phase-2-14-quality-guardrails-module.md) | **Done** | Implemented in `src/ai_team/guardrails/quality.py`: GuardrailResult, code_quality_guardrail, coverage_guardrail (alias test_coverage_guardrail), documentation_guardrail, architecture_compliance_guardrail, dependency_guardrail. Uses settings for min coverage and code quality score. Unit tests in `tests/unit/guardrails/test_quality.py`. |

---

## Phase 3: Task & Flow Design (Days 15–21)

| ID   | Prompt | File | Status | Notes |
|------|--------|------|--------|------|
| 3.1  | Generate Planning Tasks | [phase-3-1-planning-tasks.md](phase-3-1-planning-tasks.md) | Pending | |
| 3.2  | Generate Development Tasks | [phase-3-2-development-tasks.md](phase-3-2-development-tasks.md) | Pending | |
| 3.3  | Generate Testing Tasks | [phase-3-3-testing-tasks.md](phase-3-3-testing-tasks.md) | Pending | |
| 3.4  | Generate Deployment Tasks | [phase-3-4-deployment-tasks.md](phase-3-4-deployment-tasks.md) | Pending | |
| 3.5  | Generate Planning Crew | [phase-3-5-planning-crew.md](phase-3-5-planning-crew.md) | Pending | |
| 3.6  | Generate Development Crew | [phase-3-6-development-crew.md](phase-3-6-development-crew.md) | Pending | |
| 3.7  | Generate Testing Crew | [phase-3-7-testing-crew.md](phase-3-7-testing-crew.md) | Pending | |
| 3.8  | Generate Deployment Crew | [phase-3-8-deployment-crew.md](phase-3-8-deployment-crew.md) | Pending | |
| 3.9  | Generate State Models | [phase-3-9-state-models.md](phase-3-9-state-models.md) | Pending | |
| 3.10 | Generate Main Flow | [phase-3-10-main-flow.md](phase-3-10-main-flow.md) | Pending | |
| 3.11 | Generate conditional routing | [phase-3-11-conditional-routing.md](phase-3-11-conditional-routing.md) | Pending | |
| 3.12 | Generate Human-in-the-Loop | [phase-3-12-human-in-the-loop.md](phase-3-12-human-in-the-loop.md) | Pending | |
| 3.13 | Generate Error Handling | [phase-3-13-error-handling.md](phase-3-13-error-handling.md) | Pending | |

---

## Phase 4: Memory, Reasoning & Integration (Days 22–28)

| ID   | Prompt | File | Status | Notes |
|------|--------|------|--------|------|
| 4.1–4.3 | Generate unified memory configuration | [phase-4-1-4-3-unified-memory-configuration.md](phase-4-1-4-3-unified-memory-configuration.md) | Pending | |
| 4.4  | Generate Knowledge Base | [phase-4-4-knowledge-base.md](phase-4-4-knowledge-base.md) | Pending | |
| 4.5  | Generate Reasoning Enhancement | [phase-4-5-reasoning-enhancement.md](phase-4-5-reasoning-enhancement.md) | Pending | |
| 4.6  | Generate structured output models | [phase-4-6-structured-output-models.md](phase-4-6-structured-output-models.md) | Pending | |
| 4.7  | Generate callback system | [phase-4-7-callback-system.md](phase-4-7-callback-system.md) | Pending | |
| 4.8  | Generate Integration Testing | [phase-4-8-integration-testing.md](phase-4-8-integration-testing.md) | Pending | |

---

## Phase 5: Testing, Iteration & Guardrail Validation (Days 29–35)

| ID   | Prompt | File | Status | Notes |
|------|--------|------|--------|------|
| 5.1  | Generate Unit Tests | [phase-5-1-unit-tests.md](phase-5-1-unit-tests.md) | Pending | |
| 5.2  | Generate Integration Tests | [phase-5-2-integration-tests.md](phase-5-2-integration-tests.md) | Pending | |
| 5.3  | Generate guardrail test suite | [phase-5-3-guardrail-test-suite.md](phase-5-3-guardrail-test-suite.md) | Pending | |
| 5.4  | Generate E2E Tests | [phase-5-4-e2e-tests.md](phase-5-4-e2e-tests.md) | Pending | |
| 5.5  | Generate Performance Tests | [phase-5-5-performance-tests.md](phase-5-5-performance-tests.md) | Pending | |
| 5.6  | Generate Demo Project 1 — Hello World Flask API | [phase-5-6-demo-project-1-hello-world-flask-api.md](phase-5-6-demo-project-1-hello-world-flask-api.md) | Pending | |
| 5.7  | Generate Demo Project 2 — TODO App (Full-Stack) | [phase-5-7-demo-project-2-todo-app-full-stack.md](phase-5-7-demo-project-2-todo-app-full-stack.md) | Pending | |
| 5.8  | Generate Demo Project 3 — Data Pipeline | [phase-5-8-demo-project-3-data-pipeline.md](phase-5-8-demo-project-3-data-pipeline.md) | Pending | |
| 5.9  | Generate Iteration and Fix Script | [phase-5-9-iteration-and-fix-script.md](phase-5-9-iteration-and-fix-script.md) | Pending | |

---

## Phase 6: UI, Deployment & Showcase (Days 36–42)

| ID   | Prompt | File | Status | Notes |
|------|--------|------|--------|------|
| 6.1  | Generate Gradio UI | [phase-6-1-gradio-ui.md](phase-6-1-gradio-ui.md) | Pending | |
| 6.2  | Generate Project Input Component | [phase-6-2-project-input-component.md](phase-6-2-project-input-component.md) | Pending | |
| 6.3  | Generate Progress Display Component | [phase-6-3-progress-display-component.md](phase-6-3-progress-display-component.md) | Pending | |
| 6.4  | Generate Output Display Component | [phase-6-4-output-display-component.md](phase-6-4-output-display-component.md) | Pending | |
| 6.5  | Generate demo recording scripts | [phase-6-5-demo-recording-scripts.md](phase-6-5-demo-recording-scripts.md) | Pending | |
| 6.6  | Generate comprehensive documentation | [phase-6-6-comprehensive-documentation.md](phase-6-6-comprehensive-documentation.md) | Pending | |
| 6.7  | Generate GitHub polish | [phase-6-7-github-polish.md](phase-6-7-github-polish.md) | Pending | |
| 6.8  | Generate LinkedIn/social announcement | [phase-6-8-linkedinsocial-announcement.md](phase-6-8-linkedinsocial-announcement.md) | Pending | |

---

## Summary

| Phase | Done | Pending | Total |
|-------|------|--------|-------|
| 0     | 5 | 0 | 5 |
| 1     | 3 | 2 | 5 |
| 2     | 5 | 9 | 14 |
| 3     | 0 | 13 | 13 |
| 4     | 0 | 7 | 7 |
| 5     | 0 | 9 | 9 |
| 6     | 0 | 8 | 8 |
| **Total** | **13** | **47** | **60** |

*Phase 4 combines tasks 4.1–4.3 into one prompt by design (60 prompts total). Update the Status and Notes columns as prompts are run.*
