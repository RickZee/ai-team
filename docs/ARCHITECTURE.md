# Architecture

This document describes the AI Team system architecture: flows, crews, agents, tools, guardrails, and memory. It aligns with the CrewAI-based design and the `AITeamFlow` orchestrator.

---

## 1. System Overview Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           FLOW LAYER (Orchestration)                             │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │  AITeamFlow                                                                  │ │
│  │  • @start() → intake_request                                                  │ │
│  │  • @router() → route_after_intake | route_after_planning | ...               │ │
│  │  • @listen("run_planning") | "run_development" | "run_testing" | ...         │ │
│  │  • ProjectState (Pydantic) — phase, requirements, files, test_results, ...   │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
┌─────────────────────────┐ ┌─────────────────────────┐ ┌─────────────────────────┐
│     CREW LAYER          │ │     CREW LAYER          │ │     CREW LAYER          │
│  PlanningCrew          │ │  DevelopmentCrew        │ │  TestingCrew            │
│  • Manager (coordinator)│ │  • Manager (coordinator)│ │  • QA Engineer          │
│  • Product Owner        │ │  • Backend / Frontend   │ │  • Test tools           │
│  • Architect            │ │  • Fullstack (optional)│ │  • Coverage / reports    │
│  • Requirements + Arch  │ │  • Code + File + Git    │ │                         │
└───────────┬─────────────┘ └───────────┬─────────────┘ └───────────┬─────────────┘
            │                           │                           │
            ▼                           ▼                           ▼
┌─────────────────────────┐ ┌─────────────────────────┐ ┌─────────────────────────┐
│     CREW LAYER          │ │     AGENT LAYER         │ │     AGENT LAYER         │
│  DeploymentCrew         │ │  • Manager              │ │  • Backend Developer    │
│  • DevOps Engineer      │ │  • Product Owner        │ │  • Frontend Developer   │
│  • Cloud Engineer       │ │  • Architect            │ │  • QA Engineer          │
│  • Docker / IaC / CI-CD │ │  • Cloud Engineer       │ │  • DevOps Engineer      │
└───────────┬─────────────┘ │  • (Fullstack optional) │ │  (7–8 specialized)      │
            │               └───────────┬─────────────┘ └───────────┬─────────────┘
            │                           │                           │
            └───────────────────────────┼───────────────────────────┘
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           TOOL LAYER (with security wrappers)                    │
│  File: read_file, write_file, list_dir (path validation)                         │
│  Code: code_generation, code_review, sandbox execution                            │
│  Git:  status, commit, branch, diff                                               │
│  Test: run_tests, coverage_report                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
┌───────────────────────────────────────┼───────────────────────────────────────────┐
│  GUARDRAIL LAYER                      │  MEMORY LAYER                              │
│  • Behavioral (role, scope, reasoning)│  • Short-term (ChromaDB) — session context │
│  • Security (code safety, PII,        │  • Long-term (SQLite) — cross-session      │
│    secrets, prompt injection, paths)  │  • Entity memory — entities & relations    │
│  • Quality (word count, JSON, syntax, │  • Knowledge sources for RAG               │
│    no placeholders, LLM guardrails)   │                                             │
└───────────────────────────────────────┴───────────────────────────────────────────┘
```

---

## 2. Component Descriptions

### 2.1 Flow Layer

| Component | Description |
|-----------|-------------|
| **AITeamFlow** | Main CrewAI `Flow[ProjectState]` orchestrator. Drives the lifecycle: intake → planning → development → testing → deployment → finalize. Uses `@start()`, `@listen()`, and `@router()` for event-driven routing. |
| **ProjectState** | Pydantic model holding all flow state: `project_id`, `user_request`, `current_phase`, `requirements`, `architecture`, `generated_files`, `test_results`, `deployment_config`, `errors`, `human_feedback`, `awaiting_human_input`, etc. |
| **Routing logic** | After each crew step, routers decide the next step (e.g. `run_development`, `request_clarification`, `handle_fatal_error`, `retry_development`, `escalate_test_failures`). Supports human-in-the-loop and error recovery. |

### 2.2 Crew Layer

| Crew | Purpose | Key agents |
|------|---------|------------|
| **PlanningCrew** | Turn user request into requirements and architecture. | Manager (coordinator), Product Owner, Architect. Hierarchical process. |
| **DevelopmentCrew** | Generate and write code per architecture. | Manager (coordinator), Backend/Frontend/Fullstack developers. Hierarchical process. |
| **TestingCrew** | Run tests, collect coverage, validate acceptance. | QA Engineer; uses test-runner and code tools. |
| **DeploymentCrew** | Produce deployment and CI/CD artifacts. | DevOps Engineer, Cloud Engineer; Docker, K8s, Terraform, CI configs. |

### 2.3 Agent Layer (7–8 specialized agents)

| Agent | Responsibility |
|-------|----------------|
| **Manager** | Coordinate crew, break down work, resolve blockers, escalate to human when needed. Uses task delegation and status reporting. |
| **Product Owner** | Requirements and user stories; acceptance criteria; MoSCoW prioritization. Output: `RequirementsDocument`. |
| **Architect** | System design, technology choices, interfaces, ADRs. Output: `ArchitectureDocument`. Can delegate to Cloud/DevOps. |
| **Backend Developer** | APIs, services, DB schemas, backend code (Python/Node/Go). |
| **Frontend Developer** | UI components, state, styling (React/Vue, etc.). |
| **Cloud Engineer** | IaC (Terraform/CloudFormation), cost/security/reliability. |
| **DevOps Engineer** | CI/CD, Docker, K8s, monitoring, observability. |
| **QA Engineer** | Test strategy, automation, coverage, quality checks. |

Agents are defined in `config/agents.yaml` (role, goal, backstory, verbose, allow_delegation, max_iter, memory) and mapped to Ollama models in settings.

### 2.4 Tool Layer

| Category | Examples | Security |
|----------|----------|----------|
| **File** | read_file, write_file, list_dir | Path validation (allowed dirs), no path traversal. |
| **Code** | code_generation, code_review, sandbox execution | Sandboxed execution; guardrails on generated code. |
| **Git** | status, commit, branch, diff | Scoped to workspace; no force-push to protected branches by policy. |
| **Test** | run_tests, coverage_report | Timeout and resource limits. |

Tools are wrapped with guardrail checks where applicable (e.g. SecurityGuardrails.validate_file_path, validate_code_safety).

### 2.5 Guardrail Layer

| Type | Purpose |
|------|---------|
| **Behavioral** | Role adherence (e.g. QA only writes tests), scope control (no unbounded expansion), require reasoning in long outputs. |
| **Security** | Code safety (no unsafe exec/subprocess/eval), no secrets in output, PII redaction, prompt-injection detection, file-path validation. |
| **Quality** | Word count bounds, JSON validity, Python syntax, no TODO/FIXME/NotImplementedError placeholders; optional LLM guardrails (hallucination, code review). |

Configured via `GuardrailConfig` in settings; full chain built by `create_full_guardrail_chain()`.

### 2.6 Memory Layer

| Type | Storage | Use |
|------|---------|-----|
| **Short-term** | ChromaDB | Session/conversation context; recent tasks and outputs. |
| **Long-term** | SQLite | Cross-session recall; summarization and retrieval. |
| **Entity** | Entity memory | Persistent entities and relationships for consistency across phases. |

Configured via `MemoryConfig` (Chroma persist dir, SQLite path, limits). Used by agents via CrewAI memory hooks and knowledge sources.

---

## 3. Data Flow Diagram

```
  User Request
       │
       ▼
┌──────────────┐     invalid / rejected      ┌─────────────────────┐
│   INTAKE     │ ──────────────────────────►│ request_clarification│
│  (validate) │                             │ or handle_fatal_error│
└──────┬───────┘                             └─────────────────────┘
       │ success
       ▼
┌──────────────┐     needs_clarification      ┌─────────────────────┐
│  PLANNING    │ ──────────────────────────►│ request_clarification│
│ (req + arch) │                             └─────────────────────┘
└──────┬───────┘
       │ success
       ▼
┌──────────────┐     tests_failed & retries  ┌─────────────────────┐
│ DEVELOPMENT  │ ◄──────────────────────────│ retry_development   │
│ (code gen)  │ ──────────────────────────►│ (feedback loop)     │
└──────┬───────┘     success                 └─────────────────────┘
       │
       ▼
┌──────────────┐     tests_failed (max)      ┌─────────────────────┐
│   TESTING    │ ──────────────────────────►│ escalate_test_      │
│ (QA + runs)  │                             │ failures → human     │
└──────┬───────┘                             └─────────────────────┘
       │ success
       ▼
┌──────────────┐
│  DEPLOYMENT  │ ─── success ──► finalize_project ──► COMPLETE
│ (Docker, CI) │ ─── error ────► handle_deployment_error
└──────────────┘
```

State is carried in **ProjectState** through the flow; each crew reads/writes the relevant fields (e.g. PlanningCrew → `requirements`, `architecture`; DevelopmentCrew → `generated_files`; TestingCrew → `test_results`).

---

## 4. State Machine (ProjectState Transitions)

```
                    ┌─────────────┐
                    │   INTAKE    │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
       ┌──────────┐ ┌─────────────┐ ┌──────────────┐
       │ PLANNING │ │ AWAITING_    │ │   FAILED     │
       └────┬─────┘ │ HUMAN       │ └──────────────┘
            │       └─────────────┘
            ▼
       ┌──────────────┐
       │ DEVELOPMENT  │◄────────── retry (from TESTING)
       └──────┬───────┘
              │
              ▼
       ┌──────────────┐
       │   TESTING    │──────► AWAITING_HUMAN (escalate)
       └──────┬───────┘
              │
              ▼
       ┌──────────────┐
       │  DEPLOYMENT  │
       └──────┬───────┘
              │
              ▼
       ┌──────────────┐
       │   COMPLETE   │
       └──────────────┘
```

- **INTAKE** → PLANNING (valid), AWAITING_HUMAN (clarification), FAILED (rejected).
- **PLANNING** → DEVELOPMENT (success), AWAITING_HUMAN (clarification), FAILED (error).
- **DEVELOPMENT** → TESTING (success), FAILED (error).
- **TESTING** → DEPLOYMENT (all passed), DEVELOPMENT (retry), AWAITING_HUMAN (escalate after max retries), FAILED (error).
- **DEPLOYMENT** → COMPLETE (success), FAILED (error).

`phase_history` on ProjectState records each transition with timestamp and reason.

---

## 5. Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Orchestration | **CrewAI Flows** | Flow, routers, state; event-driven pipeline. |
| LLM | **Ollama** | Local models (e.g. qwen3, deepseek-r1, qwen2.5-coder) per agent. |
| State & schemas | **Pydantic** | ProjectState, RequirementsDocument, ArchitectureDocument, CodeFile, TestResult, DeploymentConfig. |
| Short-term memory | **ChromaDB** | Vector store for recent context. |
| Long-term memory | **SQLite** | Persistent memory store. |
| UI | **Gradio** | Demo UI for project input, progress, and output. |
| Config | **pydantic-settings** | Settings, Ollama, guardrails, memory from env. |
| Logging | **structlog** | Structured logs for flow and agents. |

---

## 6. Directory Structure Mapping

```
ai-team/
├── src/ai_team/
│   ├── config/           # Flow/Crew/Agent config
│   │   ├── settings.py   # Settings, Ollama, guardrails, memory
│   │   └── agents.yaml   # Agent definitions (role, goal, backstory)
│   ├── agents/           # Agent implementations (BaseAgent, Manager, PO, Architect, …)
│   ├── crews/            # PlanningCrew, DevelopmentCrew, TestingCrew, DeploymentCrew
│   ├── flows/            # Flow layer
│   │   └── main_flow.py  # AITeamFlow, ProjectState, run_ai_team()
│   ├── tools/            # File, Code, Git, Test tools (with security wrappers)
│   ├── guardrails/       # Guardrail layer
│   │   └── __init__.py   # Behavioral, Security, Quality + create_full_guardrail_chain
│   ├── memory/           # Short-term, long-term, entity memory config & access
│   └── utils/            # Shared helpers
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── docs/                 # ARCHITECTURE.md, AGENTS.md, GUARDRAILS.md, FLOWS.md, TOOLS.md, MEMORY.md
├── scripts/              # setup_ollama.sh, test_models.py, run_demo.py
├── ui/                   # Gradio app (app.py, components/, pages/)
└── demos/                # Demo projects (input.json, expected_output.json)
```

---

## 7. Integration Points and Extension Guide

- **Adding an agent**  
  - Add entry in `config/agents.yaml` and (if needed) a model in `OllamaModelConfig` in `config/settings.py`.  
  - Implement the agent in `agents/` (extend BaseAgent), attach tools, then add to the appropriate crew in `crews/`.

- **Adding a crew**  
  - Create a new crew class in `crews/`, assign manager and member agents, define tasks.  
  - In `flows/main_flow.py`, add a `@listen("run_<crew>")` method and wire routing in the appropriate `@router(...)`.

- **Adding a tool**  
  - Implement in `tools/` (CrewAI `@tool` or BaseTool).  
  - Apply path/safety checks (reuse SecurityGuardrails where relevant).  
  - Attach the tool to the right agents in `agents/`.

- **Adding a guardrail**  
  - Add validation in `guardrails/` (Behavioral, Security, or Quality).  
  - Optionally add to `create_full_guardrail_chain()` or call from task/agent callbacks.

- **Changing state shape**  
  - Extend `ProjectState` or nested models in `flows/main_flow.py`.  
  - Update crew tasks and routers that read/write those fields.

- **Human-in-the-loop**  
  - Use `awaiting_human_input` and `human_feedback` on ProjectState; route to `request_clarification` or `escalate_*` and resume from `AWAITING_HUMAN` when feedback is provided (e.g. via Gradio or API).

---

## 8. Architecture Decision Records (ADRs)

### ADR-001: Why CrewAI Flows over LangGraph

**Status:** Accepted  

**Context:** We need an orchestrator that coordinates multiple crews (planning, development, testing, deployment) with shared state, conditional routing, and human-in-the-loop.

**Decision:** Use **CrewAI Flows** as the main orchestration layer.

**Rationale:**

- **Native crew integration:** Flows are designed to trigger and consume CrewAI crews; state can be passed via a single Pydantic model (ProjectState).
- **Declarative routing:** `@router()` and `@listen()` make phase transitions and branches explicit (e.g. retry development vs escalate).
- **Simpler mental model:** Event-driven flow with a single state object is easier to reason about and test than a generic graph.
- **Ecosystem fit:** Agents, tasks, tools, and memory are already CrewAI concepts; one stack reduces integration cost.

**Consequences:** We depend on CrewAI’s Flow API and lifecycle. If we need very custom graph semantics later, we can still wrap or replace the flow implementation while keeping the same state and crew contracts.

---

### ADR-002: Why Ollama over Cloud APIs

**Status:** Accepted  

**Context:** Agents need an LLM backend; we want to support local development, demos, and optional air-gapped or low-cost deployment.

**Decision:** Use **Ollama** as the default LLM provider (with optional cloud fallback via configuration).

**Rationale:**

- **Local-first:** No API keys or network dependency for core runs; easier onboarding and demos.
- **Cost and privacy:** No per-token cost; data stays on the host when using local models.
- **Model choice:** Different models per role (e.g. reasoning for Architect, coding for Backend) via `OllamaModelConfig`.
- **Maturity:** Ollama is widely used for local LLM runs and integrates cleanly with CrewAI/LiteLLM.

**Consequences:** We need to document hardware requirements (e.g. VRAM) and provide setup scripts (e.g. `setup_ollama.sh`). Cloud can be supported later via the same LiteLLM/CrewAI abstraction if we add an alternate provider in settings.

---

### ADR-003: Why Hierarchical Process for Planning and Development Crews

**Status:** Accepted  

**Context:** Planning and development involve multiple agents (e.g. Manager, Product Owner, Architect; Manager, Backend, Frontend). We need coordination and delegation without ad hoc handoffs.

**Decision:** Use a **hierarchical process** for PlanningCrew and DevelopmentCrew, with the **Manager** as `manager_agent`.

**Rationale:**

- **Single coordinator:** The Manager assigns tasks, resolves conflicts, and escalates to human when needed, which matches the “engineering manager” role in the design.
- **Structured delegation:** CrewAI’s hierarchical process provides a clear pattern: manager decides “who does what” and aggregates results, reducing duplicate or conflicting work.
- **Scalability:** Adding more specialists (e.g. another developer type) only requires adding an agent and tasks; the Manager’s role stays the same.
- **Traceability:** Manager’s decisions and status updates can be logged and reflected in ProjectState for observability.

**Consequences:** The Manager agent must be capable of task decomposition and routing; it should use tools like task_delegation and status_reporting. Testing and Deployment crews can remain simpler (e.g. single primary agent or small flat crew) since they have fewer concurrent roles.

---

*End of ARCHITECTURE.md*
