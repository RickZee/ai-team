# AI-Team: LangGraph Re-implementation Plan

> Add a **LangGraph** orchestration backend alongside the existing CrewAI implementation. Both backends coexist in the repo behind a common interface, enabling side-by-side comparison and future extensibility to other frameworks.

---

## 0. Design Principle: Multi-Backend, Use-Case-Specific Teams

### 0.1 Both backends coexist

We are **not** deleting CrewAI. The repo will support multiple orchestration backends behind a shared interface:

```
ai-team --backend crewai  "Build a REST API"      # existing behavior
ai-team --backend langgraph "Build a REST API"     # new LangGraph backend
```

A `Backend` protocol defines the contract. Each backend implements it. Shared layers (tools, guardrails, models, config) are backend-agnostic.

### 0.2 Use-case-specific team composition

Not every project needs all 8 agents. A **team profile** defines which agents, tools, and subgraphs are active for a given use case:

| Profile | Agents included | Use case |
|---------|----------------|----------|
| `full` (default) | All 8 agents, all 4 subgraphs | Full software project end-to-end |
| `backend-api` | Manager, PO, Architect, Backend Dev, QA, DevOps | REST API / microservice (no frontend) |
| `frontend-app` | Manager, PO, Architect, Frontend Dev, QA, DevOps | SPA / static site (no backend) |
| `data-pipeline` | Manager, PO, Architect, Backend Dev, QA | ETL / data engineering (no deployment) |
| `prototype` | Architect, Fullstack Dev, QA | Quick prototype — skip planning formality |
| `infra-only` | Architect, DevOps, Cloud | IaC / CI-CD only — no app code |
| `custom` | User-defined via config | Any subset of agents and phases |

Team profiles are defined in `config/team_profiles.yaml` and selected via `--team <profile>` CLI flag. Each profile specifies:
- Which agents to instantiate
- Which phases/subgraphs to include (skip planning? skip deployment?)
- Which tools to attach per agent
- Model overrides (e.g., use a cheaper model for prototype runs)

This works identically across both backends.

### 0.3 Future backends

The multi-backend architecture is designed for easy addition of other frameworks later:

- **AutoGen** — Microsoft's multi-agent framework
- **Claude Agent SDK** — Anthropic's native agent orchestration
- **AWS Bedrock Agents** — managed agent service
- **Custom** — bare LLM calls with manual orchestration

Adding a new backend means implementing the `Backend` protocol and wiring it into the CLI/UI. Shared layers remain untouched.

---

## 1. Why LangGraph

| Dimension | CrewAI (current) | LangGraph (target) |
|-----------|-------------------|---------------------|
| **Orchestration** | CrewAI Flows (`@start`, `@listen`, `@router`) | StateGraph with explicit nodes and conditional edges |
| **Agent model** | CrewAI `Agent` with role/goal/backstory + `Crew` grouping | LangGraph `create_react_agent()` or custom tool-calling nodes per role |
| **State** | Pydantic `ProjectState` passed implicitly through flow | `TypedDict` / Pydantic `Annotated` state passed explicitly through graph |
| **Human-in-the-loop** | `awaiting_human_input` flag + polling | Native `interrupt()` / breakpoints with `Command(resume=...)` |
| **Memory** | ChromaDB + SQLite via CrewAI memory hooks | LangGraph checkpointer (Postgres/SQLite) + LangMem for long-term |
| **Subgraph composition** | Crews as monoliths | First-class subgraphs with their own state schemas |
| **Streaming** | Limited (callback-based) | Native streaming of tokens, tool calls, state updates |
| **Observability** | structlog + custom TUI | LangSmith integration + structlog |
| **Persistence** | Manual state save | Built-in checkpointing — pause, resume, time-travel, replay |

### Key benefits

- **Fine-grained control**: Each agent step is a graph node; you control exactly when and how tools are called, retried, or interrupted.
- **Deterministic routing**: Conditional edges are pure functions on state — easy to test without mocking LLMs.
- **Subgraph isolation**: Each crew becomes a subgraph with its own state schema and can be developed/tested independently.
- **Production-ready persistence**: Checkpointers enable crash recovery, long-running workflows, and state inspection.
- **Multi-agent patterns**: LangGraph has first-class support for supervisor, swarm, and hierarchical patterns.

---

## 2. Architecture Overview

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                        MAIN GRAPH (AITeamGraph)                              │
│                                                                              │
│  intake ──► planning_subgraph ──► development_subgraph ──► testing_subgraph  │
│                   │                      ▲                      │            │
│                   ▼                      │                      ▼            │
│             human_review          retry_development      deployment_subgraph │
│                                                                  │           │
│                                                              finalize        │
│                                                                              │
│  State: ProjectState (TypedDict with Annotated reducers)                     │
│  Checkpointer: PostgresSaver or SqliteSaver                                  │
│  Interrupt: at human_review, after planning, after testing                   │
└──────────────────────────────────────────────────────────────────────────────┘
         │                    │                    │                    │
         ▼                    ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐
│ PLANNING        │  │ DEVELOPMENT     │  │ TESTING         │  │ DEPLOYMENT   │
│ SUBGRAPH        │  │ SUBGRAPH        │  │ SUBGRAPH        │  │ SUBGRAPH     │
│                 │  │                 │  │                 │  │              │
│ supervisor  ─┐  │  │ supervisor  ─┐  │  │ qa_agent        │  │ devops_agent │
│   ├─ po_agent│  │  │   ├─ backend │  │  │   ├─ run_tests  │  │ cloud_agent  │
│   └─ arch_agt│  │  │   ├─ frontend│  │  │   ├─ coverage   │  │   ├─ docker  │
│              │  │  │   └─ fullstk │  │  │   └─ report     │  │   └─ ci/cd   │
│  Uses:       │  │  │              │  │  │                 │  │              │
│  Supervisor  │  │  │  Supervisor  │  │  │  ReAct agent    │  │  ReAct agent │
│  pattern     │  │  │  pattern     │  │  │                 │  │              │
└─────────────────┘  └─────────────────┘  └─────────────────┘  └──────────────┘
         │                    │                    │                    │
         └────────────────────┼────────────────────┼────────────────────┘
                              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           SHARED TOOL LAYER                                  │
│  file_tools · code_tools · git_tools · test_tools · architect_tools          │
│  (same tools as current, converted to @tool decorated functions)             │
└──────────────────────────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────────────────────────────────────────────────────┐
│  GUARDRAIL LAYER (validation nodes in each subgraph)                         │
│  behavioral_check · security_check · quality_check                           │
│  (pure functions on state — same logic, now as graph nodes or edge guards)   │
└──────────────────────────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────────────────────────────────────────────────────┐
│  PERSISTENCE & MEMORY                                                        │
│  Checkpointer (SqliteSaver / PostgresSaver) — state persistence & recovery   │
│  LangMem or custom — long-term cross-session memory                          │
│  LangSmith — tracing, observability, evaluation                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. State Design

### 3.1 Main Graph State

```python
from typing import Annotated, TypedDict, Optional
from langgraph.graph import add_messages
from pydantic import BaseModel

class ProjectState(TypedDict):
    """Top-level state flowing through the main graph."""
    # Input
    project_description: str
    project_id: str

    # Phase tracking
    current_phase: str  # "intake" | "planning" | "development" | "testing" | "deployment" | "complete" | "error"
    phase_history: Annotated[list[dict], operator.add]  # append-only reducer

    # Planning outputs
    requirements: Optional[dict]       # RequirementsDocument as dict
    architecture: Optional[dict]       # ArchitectureDocument as dict

    # Development outputs
    generated_files: Annotated[list[dict], operator.add]  # CodeFile dicts, append-only

    # Testing outputs
    test_results: Optional[dict]       # TestRunResult as dict

    # Deployment outputs
    deployment_config: Optional[dict]  # DeploymentConfig as dict

    # Error tracking
    errors: Annotated[list[dict], operator.add]
    retry_count: int
    max_retries: int

    # Human-in-the-loop
    human_feedback: Optional[str]

    # Messages (for agent reasoning traces)
    messages: Annotated[list, add_messages]
```

### 3.2 Subgraph States

Each subgraph has its own internal state that maps to/from the main state:

```python
class PlanningState(TypedDict):
    project_description: str
    messages: Annotated[list, add_messages]
    requirements: Optional[dict]
    architecture: Optional[dict]
    current_agent: str  # "product_owner" | "architect"

class DevelopmentState(TypedDict):
    requirements: dict
    architecture: dict
    messages: Annotated[list, add_messages]
    generated_files: Annotated[list[dict], operator.add]
    current_agent: str  # "backend" | "frontend" | "fullstack"

class TestingState(TypedDict):
    generated_files: list[dict]
    messages: Annotated[list, add_messages]
    test_results: Optional[dict]

class DeploymentState(TypedDict):
    generated_files: list[dict]
    test_results: dict
    messages: Annotated[list, add_messages]
    deployment_config: Optional[dict]
```

---

## 4. Multi-Agent Patterns

### 4.1 Planning & Development: Supervisor Pattern

Use `langgraph.prebuilt.create_react_agent()` for each specialist agent, then compose them under a **supervisor** node that decides which agent to invoke next.

```text
Supervisor (Manager LLM) receives the task → decides → routes to:
  ├── product_owner_agent (requirements generation)
  ├── architect_agent (architecture design)
  └── __end__ (when planning is complete)
```

The supervisor is a tool-calling LLM node whose "tools" are `transfer_to_product_owner`, `transfer_to_architect`, and `complete_planning`. This follows the LangGraph supervisor/swarm pattern.

### 4.2 Testing & Deployment: Single ReAct Agent

These are simpler — a single agent with tools:

- **QA Agent**: `run_tests`, `analyze_coverage`, `generate_test_report` tools
- **DevOps Agent**: `generate_dockerfile`, `generate_ci_pipeline`, `generate_k8s_config` tools

### 4.3 Guardrails as Validation Nodes

Instead of CrewAI task guardrails, insert **validation nodes** after each agent node:

```text
agent_node ──► guardrail_node ──► (pass) ──► next_node
                    │
                    └── (fail, retries left) ──► agent_node (retry)
                    └── (fail, no retries) ──► error_handler
```

Each guardrail node is a pure function that reads state, runs behavioral/security/quality checks, and returns updated state with pass/fail.

---

## 5. Detailed Component Specs

### 5.1 LLM Configuration

Reuse the existing `config/models.py` OpenRouter model mapping. LangGraph uses `ChatOpenAI` (via LiteLLM or direct OpenRouter endpoint):

```python
from langchain_openai import ChatOpenAI

def get_llm(role: str, env: str = "dev") -> ChatOpenAI:
    model_id = ENV_MODELS[env][role]
    return ChatOpenAI(
        model=model_id,
        openai_api_base="https://openrouter.ai/api/v1",
        openai_api_key=os.environ["OPENROUTER_API_KEY"],
        max_tokens=8192,
    )
```

### 5.2 Tools

Reuse all existing tools from `src/ai_team/tools/`. They're already `@tool` decorated or easily convertible. The security wrappers stay the same. Convert any CrewAI-specific tool interface to LangChain `@tool`:

```python
from langchain_core.tools import tool

@tool
def read_file(file_path: str) -> str:
    """Read a file from the workspace directory securely."""
    validated_path = validate_path(file_path)
    return validated_path.read_text()
```

### 5.3 Checkpointing & Persistence

```python
from langgraph.checkpoint.sqlite import SqliteSaver

checkpointer = SqliteSaver.from_conn_string("./data/langgraph_checkpoints.db")
graph = main_graph.compile(checkpointer=checkpointer)
```

This gives: crash recovery, state inspection, time-travel debugging, and the ability to resume interrupted runs.

### 5.4 Human-in-the-Loop

Use LangGraph's native `interrupt()`:

```python
from langgraph.types import interrupt, Command

def human_review_node(state: ProjectState) -> ProjectState:
    """Pause execution and wait for human feedback."""
    feedback = interrupt(
        "Review planning output. Approve or provide feedback.",
    )
    return {"human_feedback": feedback}
```

Resume with:

```python
graph.invoke(Command(resume="Looks good, proceed"), config={"thread_id": thread_id})
```

### 5.5 Streaming & Observability

```python
# Stream all events
for event in graph.stream(initial_state, config=config, stream_mode="updates"):
    # event contains node name + state delta
    update_tui(event)

# Or stream tokens
for event in graph.stream(initial_state, config=config, stream_mode="messages"):
    # event is an (AIMessageChunk, metadata) tuple
    print(event[0].content, end="")
```

Integrate with the existing Rich TUI (`monitor.py`) by consuming the stream events.

### 5.6 Error Handling

Replace `flows/error_handling.py` with:

- **Conditional edges** that route to error-handling nodes based on state
- **Retry logic** via loops in the graph (conditional edge back to the agent node)
- **Circuit breaker** as a guardrail node that checks `retry_count >= max_retries`

---

## 6. Directory Structure (Target)

Both backends live side-by-side. Shared layers are backend-agnostic.

```text
ai-team/
├── src/ai_team/
│   ├── config/
│   │   ├── settings.py           # KEEP: env, guardrails, memory settings
│   │   ├── models.py             # KEEP: OpenRouter model mapping per role/env
│   │   ├── llm_factory.py        # KEEP: LLM construction
│   │   ├── cost_estimator.py     # KEEP
│   │   ├── team_profiles.yaml    # NEW: use-case team profiles (full, backend-api, prototype, etc.)
│   │   └── agents.yaml           # KEEP: agent role/goal/backstory definitions
│   │
│   ├── core/                     # NEW: backend-agnostic protocol & team profile loader
│   │   ├── __init__.py
│   │   ├── backend.py            # Backend protocol: run(description, profile, ...) → ProjectResult
│   │   ├── team_profile.py       # TeamProfile loader: parse team_profiles.yaml, resolve agents/phases
│   │   └── result.py             # ProjectResult: unified output model for any backend
│   │
│   ├── backends/                 # NEW: one subpackage per orchestration framework
│   │   ├── __init__.py
│   │   ├── crewai_backend/       # MOVE existing crews/ + flows/ here (unchanged logic)
│   │   │   ├── __init__.py
│   │   │   ├── backend.py        # CrewAIBackend(Backend) — wraps existing AITeamFlow
│   │   │   ├── crews/            # Existing planning_crew.py, development_crew.py, etc.
│   │   │   ├── flows/            # Existing main_flow.py, state.py, routing.py, etc.
│   │   │   └── agents/           # Existing agent classes (base.py, manager.py, etc.)
│   │   │
│   │   └── langgraph_backend/    # NEW: LangGraph implementation
│   │       ├── __init__.py
│   │       ├── backend.py        # LangGraphBackend(Backend) — compile graph, invoke
│   │       ├── graphs/
│   │       │   ├── __init__.py
│   │       │   ├── main_graph.py # Top-level StateGraph composition
│   │       │   ├── planning.py   # Planning subgraph (supervisor + PO + architect)
│   │       │   ├── development.py
│   │       │   ├── testing.py
│   │       │   ├── deployment.py
│   │       │   ├── state.py      # All state TypedDicts
│   │       │   └── routing.py    # Conditional edge functions
│   │       └── agents/
│   │           ├── prompts.py    # System prompts per role
│   │           └── tools.py      # Tool lists per role
│   │
│   ├── tools/                    # SHARED: backend-agnostic tools
│   │   ├── file_tools.py         # Dual-decorated: works with both crewai and langchain @tool
│   │   ├── code_tools.py
│   │   ├── git_tools.py
│   │   ├── test_tools.py
│   │   └── ...
│   │
│   ├── guardrails/               # SHARED: same validation logic
│   ├── models/                   # SHARED: Pydantic output models
│   ├── memory/                   # SHARED: memory config (each backend may use differently)
│   ├── utils/                    # SHARED: logging, etc.
│   ├── ui/                       # SHARED: Gradio UI (calls Backend protocol)
│   ├── monitor.py                # SHARED: Rich TUI (adapter per backend for event consumption)
│   └── main.py                   # UPDATED: --backend {crewai,langgraph} --team {profile} dispatch
│
├── tests/
│   ├── unit/
│   ├── integration/
│   │   ├── test_crewai_backend/  # Existing CrewAI tests (moved)
│   │   └── test_langgraph_backend/ # New LangGraph tests
│   ├── e2e/
│   └── comparison/               # NEW: run same demo through both backends, compare results
│
├── demos/                        # KEEP
├── docs/                         # UPDATE
└── scripts/
    └── compare_backends.py       # NEW: run a demo through both, produce comparison report
```

### Backend protocol

```python
# src/ai_team/core/backend.py
from typing import Protocol, AsyncIterator
from ai_team.core.result import ProjectResult
from ai_team.core.team_profile import TeamProfile

class Backend(Protocol):
    name: str

    def run(
        self,
        description: str,
        profile: TeamProfile,
        env: str = "dev",
        **kwargs,
    ) -> ProjectResult:
        """Execute full pipeline, return result."""
        ...

    def stream(
        self,
        description: str,
        profile: TeamProfile,
        env: str = "dev",
        **kwargs,
    ) -> AsyncIterator[dict]:
        """Stream progress events."""
        ...
```

### What changes vs. what stays

| Component | Action | Notes |
|-----------|--------|-------|
| `config/` | **Keep + extend** | Add `team_profiles.yaml` |
| `core/` | **New** | Backend protocol, team profiles, unified result |
| `backends/crewai_backend/` | **Move** | Existing `agents/`, `crews/`, `flows/` relocated here |
| `backends/langgraph_backend/` | **New** | LangGraph graphs, prompts, tools mapping |
| `tools/` | **Adapt** | Make backend-agnostic (dual decorators or adapter) |
| `guardrails/` | **Keep** | Same logic, called by either backend |
| `models/` | **Keep** | Unchanged |
| `memory/` | **Keep** | Each backend wires it differently |
| `ui/` | **Adapt** | Call `Backend.stream()` instead of framework-specific API |
| `monitor.py` | **Adapt** | Backend-specific event adapters |
| `main.py` | **Update** | Dispatch to selected backend |
| `tests/` | **Extend** | Add LangGraph tests + comparison suite |

---

## 7. Implementation Tasks

### Phase 0: Setup, Core Protocol & Team Profiles (5 tasks)

- [ ] **T0.1** Add LangGraph dependencies to `pyproject.toml` as **additional** dependencies (keep CrewAI):
  - `langgraph >= 0.4.0`
  - `langchain-openai >= 0.3.0`
  - `langchain-core >= 0.3.0`
  - `langgraph-checkpoint-sqlite >= 2.0.0` (or postgres)
  - Keep all existing deps (`crewai`, `crewai-tools`, etc.)

- [ ] **T0.2** Create `src/ai_team/core/backend.py` — `Backend` protocol with `run()` and `stream()` methods, plus `ProjectResult` unified output model.

- [ ] **T0.3** Create `src/ai_team/core/team_profile.py` — `TeamProfile` dataclass/Pydantic model with: profile name, included agents list, included phases list, tool overrides, model overrides. Loader that reads `config/team_profiles.yaml`.

- [ ] **T0.4** Create `config/team_profiles.yaml` with profiles: `full`, `backend-api`, `frontend-app`, `data-pipeline`, `prototype`, `infra-only`. Each profile lists agents and phases to include.

- [ ] **T0.5** Create `src/ai_team/backends/crewai_backend/backend.py` — wrap the existing `AITeamFlow` behind the `Backend` protocol. Move existing `agents/`, `crews/`, `flows/` under `backends/crewai_backend/` (update imports). Verify existing tests still pass.

### Phase 1: State & Graph Skeleton (4 tasks)

- [ ] **T1.1** Create `src/ai_team/backends/langgraph_backend/graphs/state.py` — define `ProjectState`, `PlanningState`, `DevelopmentState`, `TestingState`, `DeploymentState` TypedDicts with Annotated reducers
- [ ] **T1.2** Create `src/ai_team/backends/langgraph_backend/graphs/routing.py` — pure functions for all conditional edges:
  - `route_after_intake(state) -> Literal["planning", "error"]`
  - `route_after_planning(state) -> Literal["development", "human_review", "error"]`
  - `route_after_development(state) -> Literal["testing", "error"]`
  - `route_after_testing(state) -> Literal["deployment", "retry_development", "human_review", "error"]`
  - `route_after_deployment(state) -> Literal["complete", "error"]`
- [ ] **T1.3** Create `src/ai_team/backends/langgraph_backend/graphs/main_graph.py` — top-level StateGraph with placeholder nodes (just pass state through) and all edges wired. Compile with SqliteSaver. Verify the graph runs end-to-end with dummy state.
- [ ] **T1.4** Write unit tests for all routing functions (pure function tests, no LLM needed).

### Phase 2: Agent Prompts & Tool Conversion (4 tasks)

- [ ] **T2.1** Create `src/ai_team/backends/langgraph_backend/agents/prompts.py` — extract system prompts from `config/agents.yaml` for each role (Manager, PO, Architect, Backend Dev, Frontend Dev, Fullstack Dev, DevOps, Cloud, QA). Each prompt defines role, goal, backstory, and behavioral constraints.
- [ ] **T2.2** Create `src/ai_team/backends/langgraph_backend/agents/tools.py` — define tool lists per role (which tools each agent can access).
- [ ] **T2.3** Convert all tools in `src/ai_team/tools/` from CrewAI `@tool` to `langchain_core.tools.tool`. Keep all security wrappers and validation logic unchanged.
- [ ] **T2.4** Write unit tests for tool conversion — verify each tool runs with mock inputs.

### Phase 3: Subgraph Implementation (5 tasks)

- [ ] **T3.1** Implement `src/ai_team/backends/langgraph_backend/graphs/planning.py`:
  - Create `product_owner_agent` using `create_react_agent(llm, tools, prompt)`
  - Create `architect_agent` using `create_react_agent(llm, tools, prompt)`
  - Create supervisor node (Manager LLM) that routes between PO and Architect using handoff tools
  - Wire as: `supervisor → {po_agent, architect_agent} → supervisor → ... → END`
  - Add guardrail validation node after completion
  - Return `PlanningState` with requirements and architecture

- [ ] **T3.2** Implement `src/ai_team/backends/langgraph_backend/graphs/development.py`:
  - Create `backend_agent`, `frontend_agent`, `fullstack_agent` using `create_react_agent()`
  - Create supervisor node (Manager LLM) that routes work to appropriate developer
  - Wire supervisor pattern
  - Add guardrail validation node (security + quality checks on generated code)

- [ ] **T3.3** Implement `src/ai_team/backends/langgraph_backend/graphs/testing.py`:
  - Single `qa_agent` using `create_react_agent()` with test tools
  - Add guardrail node for test result validation
  - Return `TestingState` with test results

- [ ] **T3.4** Implement `src/ai_team/backends/langgraph_backend/graphs/deployment.py`:
  - `devops_agent` and `cloud_agent` using `create_react_agent()`
  - Can be sequential (devops → cloud) or supervisor pattern
  - Add guardrail node for deployment config validation

- [ ] **T3.5** Write integration tests for each subgraph with mocked LLMs (use `FakeListChatModel` or similar).

### Phase 4: Main Graph Assembly (3 tasks)

- [ ] **T4.1** Replace placeholder nodes in `main_graph.py` with actual subgraph invocations. Wire state mapping between main graph state and subgraph states.
- [ ] **T4.2** Implement `human_review_node` using `interrupt()`. Add conditional edges for human-in-the-loop at planning review and test failure escalation.
- [ ] **T4.3** Implement error handling: error nodes that capture exceptions, update state with error details, and route to retry or terminal error state.

### Phase 5: Guardrails as Graph Nodes (3 tasks)

- [ ] **T5.1** Create guardrail wrapper nodes:
  - `behavioral_guardrail_node(state)` — validates role adherence, scope
  - `security_guardrail_node(state)` — validates code safety, secrets, PII
  - `quality_guardrail_node(state)` — validates output completeness, syntax, no placeholders
  - Each returns state with `guardrail_result` field; conditional edge routes to retry or next

- [ ] **T5.2** Insert guardrail nodes into each subgraph after agent output nodes.

- [ ] **T5.3** Write adversarial guardrail tests (same test cases as existing `test_guardrails_adversarial.py`).

### Phase 6: Persistence, Memory & RAG (5 tasks)

- [ ] **T6.1** Configure checkpointer in `main.py`:
  - `SqliteSaver` for dev, `PostgresSaver` for prod
  - Thread ID management (per project run)
  - State inspection utilities (for debugging)

- [ ] **T6.2** Create `src/ai_team/rag/` shared RAG layer:
  - `pipeline.py` — `RAGPipeline` class: ingest, retrieve, rerank (backend-agnostic)
  - `vector_store.py` — factory for ChromaDB (dev) / pgvector (prod) / LanceDB (CI)
  - `ingestion.py` — chunking strategies: by file, by function, by section for markdown
  - `config.py` — `RAGConfig` Pydantic settings: vector store type, embedding model, chunk size, top_k

- [ ] **T6.3** Create `src/ai_team/knowledge/` static knowledge files:
  - `best_practices/python.md`, `best_practices/security.md`, `best_practices/testing.md`
  - `architecture_patterns/microservices.md`, `architecture_patterns/monolith.md`
  - `framework_guides/flask.md`, `framework_guides/react.md`
  - `infrastructure/docker.md`, `infrastructure/ci_cd.md`
  - Ingest script: `scripts/ingest_knowledge.py`

- [ ] **T6.4** Wire RAG into both backends:
  - LangGraph: `search_knowledge` tool + automatic context injection node
  - CrewAI: `Knowledge` sources with `TextFileKnowledgeSource`
  - Per-agent scoped retrieval (filter by role + knowledge type)
  - Per-profile knowledge selection (from `team_profiles.yaml` `rag:` section)

- [ ] **T6.5** Implement long-term memory (optional):
  - Use LangMem or custom solution for cross-session knowledge
  - Store successful patterns, architecture decisions, etc.
  - Retrieve via semantic search in planning/development phases

### Phase 7: MCP Server Integration (4 tasks)

- [ ] **T7.1** Create `src/ai_team/mcp/` shared MCP client layer:
  - `client.py` — `MCPClientManager` class: load server configs from `team_profiles.yaml`, connect via appropriate transport (stdio/HTTP/SSE), expose tools as backend-agnostic list
  - `config.py` — `MCPServerConfig` Pydantic model: server name, transport type, command/url, env var interpolation, per-agent access scoping

- [ ] **T7.2** Wire MCP into LangGraph backend:
  - Use `langchain-mcp-adapters` `MultiServerMCPClient`
  - Merge MCP tools with direct `@tool` functions per agent
  - Add `langchain-mcp-adapters` to dependencies

- [ ] **T7.3** Wire MCP into CrewAI backend:
  - Use `crewai-tools[mcp]` adapter
  - Map `team_profiles.yaml` MCP config to CrewAI's `mcps` agent field
  - Add `crewai-tools[mcp]` extra to dependencies

- [ ] **T7.4** Build custom `ai-team-mcp-server`:
  - Expose tools: `project_status`, `get_requirements`, `get_architecture`, `get_generated_files`, `get_test_results`, `provide_feedback`
  - Expose resources: `project_state`, `team_profile`, `run_history`
  - Expose prompts: `code_review`, `architecture_review`, `test_strategy`
  - Transport: stdio for local, HTTP for remote/IDE integration

### Phase 8: UI, CLI & Monitoring (3 tasks)

- [ ] **T8.1** Update `main.py` CLI:
  - Compile graph with checkpointer
  - `graph.invoke()` for full run, `graph.stream()` for progress
  - Support `--resume <thread_id>` to resume interrupted runs
  - Keep `--env`, `--skip-estimate`, `--output` flags

- [ ] **T8.2** Update Gradio UI (`ui/app.py`):
  - Wire to `graph.stream()` for real-time progress
  - Add human-in-the-loop UI: show interrupt message, accept feedback, resume with `Command(resume=...)`

- [ ] **T8.3** Update Rich TUI (`monitor.py`):
  - Consume LangGraph stream events (node starts/finishes, state updates)
  - Map to existing TUI panels (phase progress, agent activity, guardrail results)

### Phase 9: Testing, Comparison & Demos (5 tasks)

- [ ] **T9.1** Write full integration test suite for LangGraph backend:
  - Test each subgraph independently with mocked LLMs
  - Test main graph end-to-end with mocked LLMs
  - Test routing logic (all conditional edge paths)
  - Test human-in-the-loop flow (interrupt + resume)
  - Test error recovery (retry loops, error states)

- [ ] **T9.2** Write backend comparison test suite (`tests/comparison/`):
  - Run the same demo input through both CrewAI and LangGraph backends
  - Compare: output quality (file count, test pass rate), cost (tokens used), latency, error rate
  - Produce a structured comparison report (JSON + markdown)

- [ ] **T9.3** Create `scripts/compare_backends.py`:
  - CLI: `python scripts/compare_backends.py demos/01_hello_world --env dev`
  - Runs demo through both backends, outputs side-by-side comparison table
  - Supports `--team <profile>` to test use-case-specific configurations

- [ ] **T9.4** Run demos against real OpenRouter:
  - `demos/01_hello_world` — minimal Flask API (both backends)
  - `demos/02_todo_app` — full-stack TODO app (both backends)
  - Test at least 2 team profiles (`full` and `backend-api`)

- [ ] **T9.5** Update all documentation:
  - `README.md` — document multi-backend support, `--backend` and `--team` flags
  - `docs/ARCHITECTURE.md` — updated diagrams showing backend abstraction
  - `docs/FLOWS.md` — graph topology for LangGraph backend
  - `docs/AGENTS.md` — agent prompt and tool documentation
  - ADR: "Why we added LangGraph as an alternative backend"
  - ADR: "Multi-backend architecture and team profiles"

---

## 8. MCP Servers: Per-Team Tool Providers

### 8.1 Why MCP

Currently, tools are hardcoded Python functions bound directly to agents. This works but has limitations:
- Adding a new tool means changing code and redeploying
- Tools can't be shared with external clients (IDE extensions, other agents)
- No standard discovery mechanism — each agent's tool list is manually curated

**Model Context Protocol (MCP)** standardizes how agents discover and invoke tools. An MCP server exposes three primitives:

| Primitive | Purpose | Example |
|-----------|---------|---------|
| **Tools** | Executable actions (model-controlled) | `github_issue_create`, `file_write`, `run_tests` |
| **Resources** | Read-only contextual data | File contents, documentation, config |
| **Prompts** | Predefined instruction templates | Coding standards, review checklists |

### 8.2 Architecture: MCP as a Tool Layer

MCP servers slot in as an **alternative/supplementary tool provider** alongside direct `@tool` functions. Both work simultaneously — agents get tools from both sources.

```text
┌─────────────────────────────────────────────────────────────────┐
│                    AGENT (any backend)                           │
│                                                                 │
│  Tools available:                                               │
│    ├── Direct @tool functions (existing: file_tools, etc.)      │
│    └── MCP-provided tools (from configured MCP servers)         │
└─────────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
┌─────────────────┐          ┌─────────────────────────────────┐
│ Direct tools    │          │ MCP Client (MultiServerMCPClient)│
│ (Python @tool)  │          │                                  │
│ - read_file     │          │  ┌─────────┐  ┌──────────┐     │
│ - write_file    │          │  │ GitHub   │  │Filesystem│     │
│ - run_tests     │          │  │ MCP Srv  │  │ MCP Srv  │     │
│ - ...           │          │  └─────────┘  └──────────┘     │
└─────────────────┘          │  ┌─────────┐  ┌──────────┐     │
                             │  │ Docker   │  │ DB Query │     │
                             │  │ MCP Srv  │  │ MCP Srv  │     │
                             │  └─────────┘  └──────────┘     │
                             └─────────────────────────────────┘
```

### 8.3 MCP Servers per Team Profile

Each team profile can specify which MCP servers to connect. This is configured in `config/team_profiles.yaml`:

```yaml
profiles:
  full:
    agents: [manager, product_owner, architect, backend, frontend, fullstack, devops, cloud, qa]
    mcp_servers:
      github:
        transport: http
        url: "${GITHUB_MCP_URL}"
        headers:
          Authorization: "Bearer ${GITHUB_TOKEN}"
      filesystem:
        transport: stdio
        command: "npx"
        args: ["-y", "@modelcontextprotocol/server-filesystem", "${PROJECT_WORKSPACE}"]
      docker:
        transport: stdio
        command: "npx"
        args: ["-y", "docker-mcp-server"]

  backend-api:
    agents: [manager, product_owner, architect, backend, qa, devops]
    mcp_servers:
      github: { inherit: full }
      filesystem: { inherit: full }
      postgres:
        transport: stdio
        command: "npx"
        args: ["-y", "@modelcontextprotocol/server-postgres", "${DATABASE_URL}"]

  prototype:
    agents: [architect, fullstack, qa]
    mcp_servers:
      filesystem: { inherit: full }
      # Minimal — no GitHub, no Docker, fast iteration

  infra-only:
    agents: [architect, devops, cloud]
    mcp_servers:
      github: { inherit: full }
      docker: { inherit: full }
      # Could add: terraform-mcp-server, aws-mcp-server
```

### 8.4 MCP Servers per Agent

Within a team, each agent only sees the MCP servers relevant to its role. This is configured in `config/agents.yaml` or `team_profiles.yaml`:

| Agent | MCP Servers | Rationale |
|-------|-------------|-----------|
| **Manager** | github (read-only) | Track issues, PRs — no write access |
| **Product Owner** | github (issues) | Create/read issues and user stories |
| **Architect** | github, filesystem | Read codebase, review PRs |
| **Backend Dev** | filesystem, postgres | Write code, query DB schema |
| **Frontend Dev** | filesystem | Write code |
| **DevOps** | github, docker, filesystem | CI/CD, containers, config |
| **Cloud** | docker, filesystem | Infrastructure as code |
| **QA** | filesystem | Read code, write tests |

Security: agents get **scoped access** — the Manager can't write files, the QA agent can't push to GitHub. This is enforced by which MCP servers are connected to each agent and what permissions those servers expose.

### 8.5 Integration with Both Backends

**LangGraph backend** — use `langchain-mcp-adapters`:

```python
from langchain_mcp_adapters import MultiServerMCPClient

async def get_agent_tools(role: str, profile: TeamProfile):
    """Combine direct tools + MCP tools for an agent."""
    direct_tools = get_direct_tools(role)  # existing @tool functions

    mcp_config = profile.get_mcp_servers_for_role(role)
    if mcp_config:
        async with MultiServerMCPClient(mcp_config) as client:
            mcp_tools = client.get_tools()
            return direct_tools + mcp_tools

    return direct_tools
```

**CrewAI backend** — use `crewai-tools[mcp]`:

```python
# In agents.yaml or programmatically
agent = Agent(
    role="Backend Developer",
    tools=[...direct_tools...],
    mcps=[
        {"server_name": "filesystem", "transport": "stdio", ...},
        {"server_name": "postgres", "transport": "stdio", ...},
    ],
)
```

Both backends consume the same `team_profiles.yaml` MCP configuration.

### 8.6 Recommended MCP Servers for Software Development

| Server | Source | Transport | Use in AI-Team |
|--------|--------|-----------|----------------|
| **GitHub** | `github/github-mcp-server` | HTTP | Issues, PRs, code search, repo management |
| **Filesystem** | `@modelcontextprotocol/server-filesystem` | stdio | Secure file read/write with access controls |
| **Git** | `@modelcontextprotocol/server-git` | stdio | Git operations (commit, diff, branch) |
| **Postgres** | `@modelcontextprotocol/server-postgres` | stdio | DB schema inspection, query execution |
| **Docker** | Community `docker-mcp-server` | stdio | Container management, image builds |
| **Sequential Thinking** | `@modelcontextprotocol/server-sequential-thinking` | stdio | Structured reasoning for Architect/PO |
| **Memory** | `@modelcontextprotocol/server-memory` | stdio | Knowledge graph for cross-session memory |
| **Fetch** | `@modelcontextprotocol/server-fetch` | stdio | Web content fetching for research |

### 8.7 Custom MCP Server: AI-Team Project Server

For deeper integration, build a **custom MCP server** that wraps AI-Team's own capabilities:

```text
ai-team-mcp-server
├── Tools:
│   ├── project_status      — get current phase, progress, errors
│   ├── get_requirements    — fetch generated requirements doc
│   ├── get_architecture    — fetch generated architecture doc
│   ├── get_generated_files — list/read generated code files
│   ├── get_test_results    — fetch test run results
│   └── provide_feedback    — submit human-in-the-loop feedback
├── Resources:
│   ├── project_state       — current ProjectState as JSON
│   ├── team_profile        — active team profile config
│   └── run_history         — past run summaries
└── Prompts:
    ├── code_review         — standardized code review template
    ├── architecture_review — architecture review checklist
    └── test_strategy       — test strategy generation template
```

This allows external tools (IDE extensions, Slack bots, dashboards) to interact with running AI-Team projects via MCP.

---

## 9. RAG: Knowledge-Augmented Agents

### 9.1 Why RAG for AI-Team

Agents currently rely solely on their LLM's training data and the immediate project context. RAG (Retrieval-Augmented Generation) gives agents access to:

- **Codebase knowledge** — existing code patterns, conventions, dependencies
- **Best practices** — coding standards, security guidelines, architectural patterns
- **Project history** — past decisions, successful patterns, known pitfalls
- **External docs** — framework documentation, API references, RFCs

Without RAG, agents reinvent solutions that already exist in the codebase or make decisions that contradict established project conventions.

### 9.2 Architecture: RAG as a Shared Layer

Like MCP, RAG is **backend-agnostic** — both CrewAI and LangGraph backends use the same knowledge stores and retrieval pipeline.

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                           RAG LAYER (shared)                                 │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────────────────┐ │
│  │ Knowledge Store  │  │ Knowledge Store  │  │ Knowledge Store              │ │
│  │ (Static)         │  │ (Project)        │  │ (Session)                    │ │
│  │                  │  │                  │  │                              │ │
│  │ • Best practices │  │ • Codebase index │  │ • Current run context        │ │
│  │ • Framework docs │  │ • Git history    │  │ • Agent outputs so far       │ │
│  │ • Security rules │  │ • Past decisions │  │ • Feedback received          │ │
│  │ • Arch patterns  │  │ • Past runs      │  │ • Errors & retries           │ │
│  └────────┬────────┘  └────────┬────────┘  └─────────────┬────────────────┘ │
│           │                    │                          │                   │
│           └────────────────────┼──────────────────────────┘                   │
│                                ▼                                              │
│                    ┌───────────────────────┐                                  │
│                    │   Retrieval Pipeline   │                                  │
│                    │   (embed → search →    │                                  │
│                    │    rerank → format)    │                                  │
│                    └───────────┬───────────┘                                  │
│                                │                                              │
└────────────────────────────────┼──────────────────────────────────────────────┘
                                 ▼
                    Injected into agent prompt as context
```

### 9.3 Knowledge Store Types

#### Static Knowledge (curated, versioned in repo)

Lives in `src/ai_team/knowledge/` as markdown/YAML files. Embedded at build time or first run.

| Knowledge Source | Content | Used by |
|-----------------|---------|---------|
| `best_practices/python.md` | PEP 8, type hints, error handling patterns | All developers |
| `best_practices/security.md` | OWASP top 10, input validation, secret management | All agents |
| `best_practices/testing.md` | Test pyramid, coverage targets, fixture patterns | QA |
| `architecture_patterns/` | Microservices, monolith, event-driven, CQRS | Architect |
| `framework_guides/flask.md` | Flask best practices, project structure | Backend Dev |
| `framework_guides/react.md` | React patterns, component design | Frontend Dev |
| `infrastructure/docker.md` | Dockerfile best practices, multi-stage builds | DevOps |
| `infrastructure/ci_cd.md` | GitHub Actions patterns, deployment strategies | DevOps |

#### Project Knowledge (built from the target project's codebase)

Indexed dynamically at the start of each run (or incrementally across runs).

| Source | What's indexed | How |
|--------|---------------|-----|
| **Codebase files** | All `.py`, `.js`, `.ts`, `.yaml`, `.md` in workspace | Chunked by file/function, embedded |
| **Git history** | Recent commits, PR descriptions, blame | Summarized, embedded |
| **Dependency manifests** | `requirements.txt`, `package.json`, `pyproject.toml` | Parsed, embedded as structured text |
| **Existing tests** | Test files, coverage reports | Chunked, embedded |

#### Session Knowledge (ephemeral, current run only)

Captured during execution, available to later phases in the same run.

| Source | Content | Available to |
|--------|---------|-------------|
| **Requirements output** | Generated RequirementsDocument | Development, Testing, Deployment |
| **Architecture output** | Generated ArchitectureDocument | Development, Testing, Deployment |
| **Generated code** | Files produced by Development | Testing, Deployment |
| **Test results** | Pass/fail, coverage, failure messages | Development (retry), Deployment |
| **Human feedback** | Feedback from HITL interrupts | All subsequent phases |

### 9.4 Retrieval Pipeline

```python
# src/ai_team/rag/pipeline.py
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

class RAGPipeline:
    """Backend-agnostic retrieval pipeline."""

    def __init__(self, vector_store, embeddings, reranker=None):
        self.vector_store = vector_store
        self.embeddings = embeddings
        self.reranker = reranker

    def retrieve(self, query: str, filters: dict = None, top_k: int = 5) -> list[Document]:
        """Retrieve relevant documents for a query."""
        # 1. Embed query
        # 2. Vector search with optional metadata filters
        # 3. Optional reranking (cross-encoder or LLM-based)
        # 4. Return top_k documents
        results = self.vector_store.similarity_search(query, k=top_k * 3, filter=filters)
        if self.reranker:
            results = self.reranker.rerank(query, results, top_k=top_k)
        return results[:top_k]

    def ingest(self, documents: list[Document], source_type: str):
        """Ingest documents into the vector store with metadata."""
        for doc in documents:
            doc.metadata["source_type"] = source_type
        self.vector_store.add_documents(documents)
```

### 9.5 RAG per Agent Role

Each agent gets a **scoped retrieval context** — the RAG pipeline filters by knowledge type and relevance to the agent's role:

| Agent | Static Knowledge | Project Knowledge | Session Knowledge |
|-------|-----------------|-------------------|-------------------|
| **Product Owner** | best_practices/requirements | existing user stories, README | — |
| **Architect** | architecture_patterns, framework_guides | codebase structure, dependencies | requirements |
| **Backend Dev** | best_practices/python, framework_guides/flask | existing backend code, tests | requirements, architecture |
| **Frontend Dev** | best_practices/javascript, framework_guides/react | existing frontend code | requirements, architecture |
| **QA** | best_practices/testing | existing tests, coverage | requirements, architecture, generated code |
| **DevOps** | infrastructure/docker, infrastructure/ci_cd | existing CI/CD, Dockerfiles | architecture, generated code |
| **Cloud** | infrastructure/aws, infrastructure/terraform | existing IaC | architecture, deployment config |

### 9.6 RAG per Team Profile

Team profiles control which knowledge stores are loaded:

```yaml
profiles:
  full:
    rag:
      static_sources: [best_practices, architecture_patterns, framework_guides, infrastructure]
      index_project: true
      session_memory: true

  backend-api:
    rag:
      static_sources: [best_practices/python, best_practices/security, framework_guides/flask, infrastructure]
      index_project: true
      session_memory: true

  prototype:
    rag:
      static_sources: [best_practices/python]  # minimal — speed over depth
      index_project: false                       # skip indexing for quick runs
      session_memory: true

  infra-only:
    rag:
      static_sources: [infrastructure, best_practices/security]
      index_project: true
      session_memory: true
```

### 9.7 Vector Store Strategy

| Store | When | Notes |
|-------|------|-------|
| **ChromaDB** | Dev/test, local runs | Zero-config, already a dependency |
| **LanceDB** | Lightweight alternative | Embedded, no server, good for CI |
| **Postgres + pgvector** | Production | Same DB as checkpointer, single infra |
| **Pinecone / Weaviate** | Scaled prod | Managed, if self-hosting isn't desired |

The `RAGPipeline` abstracts the vector store — swap implementations via config without changing agent code.

### 9.8 Integration with Both Backends

**LangGraph backend** — RAG as a tool or as prompt injection:

```python
# Option A: RAG as a tool (agent decides when to search)
@tool
def search_knowledge(query: str, source_type: str = "all") -> str:
    """Search project knowledge base for relevant context."""
    docs = rag_pipeline.retrieve(query, filters={"source_type": source_type})
    return "\n\n".join(doc.page_content for doc in docs)

# Option B: RAG as automatic context (injected before agent runs)
def planning_node_with_rag(state: PlanningState) -> PlanningState:
    context = rag_pipeline.retrieve(state["project_description"])
    enriched_prompt = f"Relevant context:\n{format_docs(context)}\n\nTask: {state['project_description']}"
    # Pass enriched_prompt to agent
    ...
```

**CrewAI backend** — use CrewAI's native knowledge sources:

```python
from crewai import Agent, Knowledge
from crewai.knowledge.source import TextFileKnowledgeSource

knowledge = Knowledge(
    sources=[
        TextFileKnowledgeSource(file_paths=["knowledge/best_practices/python.md"]),
        TextFileKnowledgeSource(file_paths=["knowledge/architecture_patterns/*.md"]),
    ],
    embedder_config=get_embedder_config(),
)

agent = Agent(
    role="Architect",
    knowledge=knowledge,
    ...
)
```

Both backends consume the same knowledge files from `src/ai_team/knowledge/`.

### 9.9 RAG + MCP: Combined Power

MCP servers can also **serve as RAG sources**. The MCP `resources` primitive is designed for exactly this:

```text
MCP Server (e.g., GitHub)
  ├── Tools: create_issue, merge_pr, ...
  └── Resources: repo README, recent PRs, issue descriptions
                  ↓
          Indexed into RAG vector store
                  ↓
          Available to agents as retrieved context
```

This means a GitHub MCP server doesn't just let agents *act* on GitHub — it also lets them *learn from* the repo's history and documentation.

---

## 10. Key Design Decisions

### D1: Supervisor vs. Swarm for multi-agent crews

**Decision**: Use **supervisor pattern** for Planning and Development crews.

**Rationale**: The Manager agent maps naturally to a supervisor that routes work. Supervisor gives deterministic control over agent ordering and prevents runaway delegation chains. Swarm (peer-to-peer handoffs) is better for conversational agents but harder to reason about for structured workflows.

### D2: Subgraphs vs. flat graph

**Decision**: Each crew is a **subgraph** with its own state schema.

**Rationale**: Isolation — each subgraph can be developed, tested, and reasoned about independently. State mapping at boundaries makes the data contract explicit. Also allows different checkpoint granularity per subgraph.

### D3: Guardrails as nodes vs. tool wrappers

**Decision**: Guardrails are **graph nodes** (not tool-level wrappers).

**Rationale**: Tool-level wrappers are still used for security (path validation, code safety), but the higher-level quality and behavioral guardrails work better as graph nodes because they operate on the full agent output, not individual tool calls. Graph nodes also make retry routing explicit via conditional edges.

### D4: Checkpointer choice

**Decision**: SqliteSaver for dev/test, PostgresSaver for prod.

**Rationale**: SQLite is zero-config for local development. Postgres for production supports concurrent access and scales to multi-user/multi-run scenarios.

### D5: Keep OpenRouter as LLM provider

**Decision**: Continue using OpenRouter with the same model-per-role mapping.

**Rationale**: The LLM provider is orthogonal to the orchestration framework. OpenRouter gives single-key access to multiple models. The existing model tiers (dev/test/prod) work unchanged.

### D6: MCP as supplementary, not replacement, tool layer

**Decision**: MCP servers **supplement** direct `@tool` functions; they don't replace them.

**Rationale**: Direct tools are simpler to develop, test, and debug. MCP adds value for external integrations (GitHub, Docker, databases) where a standardized server already exists, and for exposing AI-Team's own capabilities to external clients. Keeping both avoids hard dependency on MCP server availability for core functionality.

### D7: RAG with dual injection strategy (tool + automatic)

**Decision**: Offer RAG both as a **searchable tool** (agent-initiated) and as **automatic context injection** (pre-agent node).

**Rationale**: Some context is always relevant (e.g., architecture doc during development) — inject it automatically. Other context is situational (e.g., "how does this similar function work?") — let the agent search for it. Both patterns have well-established LangGraph and CrewAI integrations.

### D8: Static knowledge versioned in repo

**Decision**: Curated best-practices and framework guides live in `src/ai_team/knowledge/` as markdown files, checked into git.

**Rationale**: Version control gives traceability, review, and rollback. Markdown is human-readable and easy to update. Embedding happens at build/first-run time, so there's no runtime dependency on external doc sources for core knowledge.

---

## 11. Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| LangGraph API changes | Medium | Pin versions; follow LangGraph changelog |
| Supervisor pattern prompt engineering | High | Invest in supervisor prompt design; test routing exhaustively |
| State mapping between main/sub graphs | Medium | Keep state schemas simple; explicit mapping functions at boundaries |
| Tool compatibility | Low | LangChain `@tool` is stable; minimal changes from CrewAI tools |
| Loss of CrewAI hierarchical process semantics | Medium | Supervisor pattern replicates this; may need more prompt engineering for delegation |
| Checkpoint storage growth | Low | Implement TTL on checkpoints; periodic cleanup |
| MCP server availability | Medium | Direct tools as fallback; MCP is supplementary, not required |
| MCP security (DNS rebinding, auth) | Medium | HTTPS + auth headers for remote servers; stdio for local; validate Origins on SSE |
| RAG retrieval quality (irrelevant context) | Medium | Per-role filtering; reranking; tunable top_k; monitor retrieval precision |
| RAG embedding cost | Low | Embed static knowledge once at build time; incremental project indexing |
| Vector store migration | Low | Abstract behind `RAGPipeline`; swap stores via config |

---

## 12. Estimated Effort

| Phase | Tasks | Estimated complexity |
|-------|-------|---------------------|
| Phase 0: Setup, Core & Profiles | 5 | Medium — foundational, must be right |
| Phase 1: State & Skeleton | 4 | Medium |
| Phase 2: Prompts & Tools | 4 | Medium |
| Phase 3: Subgraphs | 5 | Large — core implementation |
| Phase 4: Main Graph | 3 | Medium |
| Phase 5: Guardrails | 3 | Medium |
| Phase 6: Persistence, Memory & RAG | 5 | Medium-Large — new shared layer |
| Phase 7: MCP Server Integration | 4 | Medium — new shared layer |
| Phase 8: UI/CLI | 3 | Medium |
| Phase 9: Testing, Comparison & Docs | 5 | Medium-Large |
| **Total** | **41 tasks** | |

Recommended execution order:
1. Phase 0 (critical — multi-backend skeleton + wrap existing CrewAI)
2. Phases 1-2 (LangGraph foundation)
3. Phases 3-4-5 (core LangGraph implementation)
4. Phase 6 (RAG — benefits both backends immediately)
5. Phase 7 (MCP — can run in parallel with Phase 8)
6. Phases 8-9 (UI/CLI polish + comparison)

Phases 3.1–3.4 can be parallelized. Phases 6 and 7 are independent and can be parallelized.

---

## 13. Dependencies & Versions

```toml
[tool.poetry.dependencies]
python = ">=3.11,<=3.13"
# Existing (CrewAI backend)
crewai = "^1.0.0"
crewai-tools = "^1.0.0"
langchain-community = "^0.3.0"
chromadb = ">=1.1.0,<1.2.0"
sqlalchemy = "^2.0.0"
litellm = "1.74.9"
# New (LangGraph backend)
langgraph = ">=0.4.0"
langchain-openai = ">=0.3.0"
langchain-core = ">=0.3.0"
langgraph-checkpoint-sqlite = ">=2.0.0"
langchain-mcp-adapters = ">=0.1.0"
# Optional for prod:
# langgraph-checkpoint-postgres = ">=2.0.0"
# RAG
langchain-chroma = ">=0.2.0"       # or langchain-lancedb for lightweight alternative
# Shared
pydantic = "^2.7.0"
pydantic-settings = ">=2.2.0"
python-dotenv = "^1.0.0"
gradio = "^4.0.0"
structlog = "^24.1.0"
rich = ">=13.0.0"
gitpython = "^3.1.0"
pyyaml = "^6.0.0"
httpx = "^0.27.0"
tenacity = "^8.2.0"
```

Both backends are installed. If dependency conflicts arise between CrewAI's pinned `litellm` and LangGraph's `langchain-openai`, consider making backends optional extras:

```toml
[tool.poetry.extras]
crewai = ["crewai", "crewai-tools", "litellm", "chromadb"]
langgraph = ["langgraph", "langchain-openai", "langgraph-checkpoint-sqlite"]
```
