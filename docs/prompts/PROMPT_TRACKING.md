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
| 6 | 2 | 6.1 | Main Streamlit app (uses 6.2–6.4). |
| 6 | 3 | 6.5, 6.6, 6.7, 6.8 | After 6.1; recording, docs, polish, social. |

---

## Phase 0: Preparation & Research (Days 1–3)

| ID   | Prompt | File | Status | Notes |
|------|--------|------|--------|------|
| 0.1  | Generate pyproject.toml | [phase-0-1-pyproject-toml.md](phase-0-1-pyproject-toml.md) | Pending | |
| 0.2  | Generate Ollama setup script | [phase-0-2-ollama-setup-script.md](phase-0-2-ollama-setup-script.md) | Pending | |
| 0.3  | Generate model benchmark script | [phase-0-3-model-benchmark-script.md](phase-0-3-model-benchmark-script.md) | Pending | |
| 0.4  | Generate CrewAI reference document | [phase-0-4-crewai-reference-document.md](phase-0-4-crewai-reference-document.md) | Pending | |
| 0.5  | Generate architecture design document | [phase-0-5-architecture-design-document.md](phase-0-5-architecture-design-document.md) | Pending | |

---

## Phase 1: Repository Setup & Environment (Days 4–6)

| ID   | Prompt | File | Status | Notes |
|------|--------|------|--------|------|
| 1.1  | Generate project scaffold | [phase-1-1-project-scaffold.md](phase-1-1-project-scaffold.md) | **Done** | Full `src/ai_team/`, tests (unit/integration/e2e), docs stubs, scripts placeholders, ui structure. |
| 1.2  | Generate settings module | [phase-1-2-settings-module.md](phase-1-2-settings-module.md) | Pending | |
| 1.3  | Generate Dockerfile and docker-compose | [phase-1-3-dockerfile-and-docker-compose.md](phase-1-3-dockerfile-and-docker-compose.md) | **Done** | Multi-stage Dockerfile, `.dockerignore`, docker-compose. |
| 1.4  | Generate CI/CD pipeline | [phase-1-4-cicd-pipeline.md](phase-1-4-cicd-pipeline.md) | Pending | |
| 1.5  | Generate initial documentation | [phase-1-5-initial-documentation.md](phase-1-5-initial-documentation.md) | Pending | |

---

## Phase 2: Agent Definition, Tools & Guardrails (Days 7–14)

| ID   | Prompt | File | Status | Notes |
|------|--------|------|--------|------|
| 2.1  | Generate Base Agent class | [phase-2-1-base-agent-class.md](phase-2-1-base-agent-class.md) | Pending | |
| 2.2  | Generate Manager Agent | [phase-2-2-manager-agent.md](phase-2-2-manager-agent.md) | Pending | |
| 2.3  | Generate Product Owner Agent | [phase-2-3-product-owner-agent.md](phase-2-3-product-owner-agent.md) | Pending | |
| 2.4  | Generate Architect Agent | [phase-2-4-architect-agent.md](phase-2-4-architect-agent.md) | Pending | |
| 2.5  | Generate Developer Agents (Backend, Frontend, Fullstack) | [phase-2-5-developer-agents-backend-frontend-fullstack.md](phase-2-5-developer-agents-backend-frontend-fullstack.md) | Pending | |
| 2.6  | Generate DevOps and Cloud Agents | [phase-2-6-devops-and-cloud-agents.md](phase-2-6-devops-and-cloud-agents.md) | Pending | |
| 2.7  | Generate QA Agent | [phase-2-7-qa-agent.md](phase-2-7-qa-agent.md) | Pending | |
| 2.8  | Generate secure file tools | [phase-2-8-secure-file-tools.md](phase-2-8-secure-file-tools.md) | Pending | |
| 2.9  | Generate code execution sandbox tools | [phase-2-9-code-execution-sandbox-tools.md](phase-2-9-code-execution-sandbox-tools.md) | Pending | |
| 2.10 | Generate Git tools | [phase-2-10-git-tools.md](phase-2-10-git-tools.md) | Pending | |
| 2.11 | Generate test runner tools | [phase-2-11-test-runner-tools.md](phase-2-11-test-runner-tools.md) | Pending | |
| 2.12 | Generate behavioral guardrails module | [phase-2-12-behavioral-guardrails-module.md](phase-2-12-behavioral-guardrails-module.md) | Pending | |
| 2.13 | Generate security guardrails module | [phase-2-13-security-guardrails-module.md](phase-2-13-security-guardrails-module.md) | Pending | |
| 2.14 | Generate quality guardrails module | [phase-2-14-quality-guardrails-module.md](phase-2-14-quality-guardrails-module.md) | Pending | |

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
| 6.1  | Generate Streamlit UI | [phase-6-1-streamlit-ui.md](phase-6-1-streamlit-ui.md) | Pending | |
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
| 0     | 0 | 5 | 5 |
| 1     | 2 | 3 | 5 |
| 2     | 0 | 14 | 14 |
| 3     | 0 | 13 | 13 |
| 4     | 0 | 7 | 7 |
| 5     | 0 | 9 | 9 |
| 6     | 0 | 8 | 8 |
| **Total** | **2** | **58** | **60** |

*Phase 4 combines tasks 4.1–4.3 into one prompt by design (60 prompts total). Update the Status and Notes columns as prompts are run.*
