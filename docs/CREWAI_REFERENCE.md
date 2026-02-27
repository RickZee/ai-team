# CrewAI Quick Reference

Concise reference for CrewAI agents, tasks, crews, flows, memory, guardrails, tools, and callbacks. Use with CrewAI 0.80+ and crewai-tools.

---

## 1. Agent configuration

**YAML vs Python:** Define agents in `config/agents.yaml` and reference via `@agent` + `config=self.agents_config['key']`, or build agents in Python.

**Key parameters:**

| Parameter            | Type     | Description                                      |
|----------------------|----------|--------------------------------------------------|
| `role`               | `str`    | Agent's function and domain (e.g. "Senior Researcher") |
| `goal`               | `str`    | Purpose and success criteria                     |
| `backstory`          | `str`    | Experience and perspective                       |
| `tools`              | `List`   | Tools the agent can use                           |
| `memory`             | `bool`/`Memory` | Use crew memory or scoped memory          |
| `verbose`            | `bool`   | Log agent reasoning (default `False`)            |
| `allow_delegation`   | `bool`   | Allow delegating to other agents (default `True`) |
| `max_iter`           | `int`    | Max reasoning iterations per task                |
| `llm`                | `str`/`BaseLLM` | Model or LLM instance                    |

**YAML (e.g. `config/agents.yaml`):**

```yaml
researcher:
  role: >
    Senior Data Researcher
  goal: >
    Uncover detailed profiles based on provided name and domain
  backstory: >
    Expert analyst with attention to detail.
```

**Python:**

```python
from crewai import Agent

researcher = Agent(
    role="Senior Data Researcher",
    goal="Uncover detailed profiles based on provided name and domain",
    backstory="Expert analyst with attention to detail.",
    tools=[search_tool],
    verbose=True,
    allow_delegation=False,
    max_iter=15,
)
```

**Using YAML config in code:**

```python
from crewai.project import CrewBase, agent

@CrewBase
class MyCrew:
    @agent
    def researcher(self) -> Agent:
        return Agent(config=self.agents_config['researcher'], tools=[search_tool])
```

---

## 2. Task configuration

**Key parameters:**

| Parameter              | Type              | Description |
|------------------------|-------------------|-------------|
| `description`          | `str`             | What the task entails |
| `expected_output`     | `str`             | What completion looks like |
| `agent`               | `BaseAgent`       | Agent responsible (required for sequential) |
| `context`             | `List[Task]`      | Tasks whose outputs are used as context |
| `output_pydantic`     | `Type[BaseModel]` | Pydantic model for structured output |
| `output_json`         | `Type[BaseModel]` | JSON output schema (Pydantic model) |
| `guardrail`           | `Callable`        | Single validation function |
| `guardrails`          | `List[Callable]`  | Multiple guardrails (overrides `guardrail`) |
| `guardrail_max_retries` | `int`           | Retries on guardrail failure (default 3) |
| `callback`            | callable          | Run after task completion |
| `output_file`         | `str`             | Path to write output |
| `markdown`            | `bool`            | Format output as Markdown |
| `async_execution`     | `bool`            | Run task asynchronously |
| `human_input`         | `bool`            | Human reviews final answer |

**YAML (e.g. `config/tasks.yaml`):**

```yaml
research_task:
  description: >
    Conduct thorough research about {topic}.
  expected_output: >
    A list of 10 bullet points of the most relevant information about {topic}.
  agent: researcher
```

**Python with context and output_pydantic:**

```python
from crewai import Task
from pydantic import BaseModel

class Report(BaseModel):
    title: str
    sections: list[str]

research_task = Task(
    description="Research the latest developments in AI",
    expected_output="A list of recent AI developments",
    agent=researcher,
)

report_task = Task(
    description="Turn the research into a structured report",
    expected_output="A report with title and sections",
    agent=writer,
    context=[research_task],
    output_pydantic=Report,
)
```

**Variables in YAML** are filled by `crew.kickoff(inputs={'topic': 'AI Agents'})`.

---

## 3. Crew composition

**Process types:**

- **Sequential:** Tasks run in definition order. Each task needs an assigned `agent`.
- **Hierarchical:** A manager agent delegates and validates; set `process=Process.hierarchical` and optionally `manager_llm`, `manager_agent`.

**Key parameters:**

| Parameter      | Description |
|----------------|-------------|
| `agents`       | List of agents |
| `tasks`        | List of tasks |
| `process`      | `Process.sequential` or `Process.hierarchical` |
| `manager_llm`  | LLM for manager (hierarchical) — Crew-level override; no per-agent slot here |
| `manager_agent`| Custom manager agent (hierarchical) |
| `memory`      | `True` for default memory, or `Memory(...)` instance |
| `planning`     | `True` to add step-by-step planning before iterations |
| `planning_llm` | LLM for planning — Crew-level override (CrewAI default gpt-4o-mini if unset) |
| `verbose`     | Log crew execution |

**Why only manager and planning?** CrewAI’s `Crew` only exposes these two LLM overrides at the crew level. Every **agent** already has its own `llm` (set in the Agent constructor). So task execution uses each task’s assigned agent’s LLM; the crew-level slots are only for the hierarchical manager and the optional planning step, which are not tied to a single task agent.

**In this project:** We keep LLM choice consistent with config. Each agent gets its LLM from `create_llm_for_role(role_name, openrouter)` in `BaseAgent` (see `config/models.py` and `config/llm_factory.py`). For `manager_llm` and `planning_llm` we pass the same config-derived LLM from the manager/architect agent (e.g. `manager_llm=getattr(architect, "llm", None)` in the development crew, `planning_llm=getattr(manager, "llm", None)` in the planning crew), so manager and planning use our role-based config rather than CrewAI defaults.

**Example:**

```python
from crewai import Crew, Process

crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, report_task],
    process=Process.sequential,
    memory=True,
    planning=True,
    verbose=True,
)
result = crew.kickoff(inputs={'topic': 'AI Agents'})
```

**Hierarchical:**

```python
crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, report_task],
    process=Process.hierarchical,
    manager_llm="gpt-4o",
    verbose=True,
)
```

---

## 4. Flows

Flows are event-driven workflows: entry points (`@start`), listeners (`@listen`), and routers (`@router`). State is a Pydantic `BaseModel`; use `@human_feedback` for human-in-the-loop.

**Decorators:**

- **@start()** — Entry point. Optionally pass a callable condition.
- **@listen(method_or_emit)** — Run when a method finishes or when a router emits a given outcome.
- **@router(method)** — Decide next step from method result; return a string that matches a `@listen("outcome")`.
- **@human_feedback(...)** — Pause, show output, collect feedback; optionally `emit` outcomes for routing.

**State:** Subclass `Flow[YourState]` and define state as a Pydantic `BaseModel`. Access as `self.state`.

**Minimal flow:**

```python
from crewai import Flow
from crewai.flow.flow import start, listen, router
from pydantic import BaseModel, Field

class MyState(BaseModel):
    value: str = ""

class MyFlow(Flow[MyState]):
    @start()
    def begin(self) -> dict:
        self.state.value = "started"
        return {"status": "ok"}

    @router(begin)
    def after_begin(self, result: dict) -> str:
        return "next_step" if result.get("status") == "ok" else "error"

    @listen("next_step")
    def next_step(self) -> str:
        return f"Done: {self.state.value}"
```

**Human feedback (no routing):**

```python
from crewai.flow.human_feedback import human_feedback

@start()
@human_feedback(message="Please review this content:")
def generate_content(self):
    return "AI-generated content for review."

@listen(generate_content)
def process_feedback(self, result):
    # result is HumanFeedbackResult: result.output, result.feedback
    print(f"Feedback: {result.feedback}")
```

**Human feedback with routing (emit):**

```python
@start()
@human_feedback(
    message="Approve this content?",
    emit=["approved", "rejected", "needs_revision"],
    llm="gpt-4o-mini",
    default_outcome="needs_revision",
)
def review_content(self):
    return "Draft content..."

@listen("approved")
def publish(self, result):
    print("Published!", result.feedback)

@listen("rejected")
def discard(self, result):
    print("Rejected:", result.feedback)
```

**Run:** `flow = MyFlow(); result = flow.kickoff()` (or pass initial state).

---

## 5. Memory (unified API)

CrewAI provides a **unified Memory API** — a single `Memory` class that replaces separate short-term, long-term, and entity memory types. The LLM analyzes content on save (scope, categories, importance) and recall uses composite scoring (semantic + recency + importance).

**Storage:** Default backend is **LanceDB**. Data lives under `./.crewai/memory`, or `$CREWAI_STORAGE_DIR/memory` if set. Pass `storage="path/to/dir"` or a custom `StorageBackend` instance for a different backend. LanceDB is serialized with a shared lock so multiple `Memory` instances (e.g. agent + crew) can share the same path.

**Usage patterns:**

- **Standalone:** `memory = Memory()` then `memory.remember(...)`, `memory.recall(...)`.
- **With Crew:** `Crew(..., memory=True)` or `memory=Memory(...)`. When `memory=True`, the crew's `embedder` is passed through automatically.
- **With Agent:** `memory=memory.scope("/agent/researcher")` for private scope; use `memory.slice(scopes=[...], read_only=True)` for multi-scope read-only views.
- **In Flows:** `self.remember(...)`, `self.recall(...)`, `self.extract_memories(...)`.

**Core API:**

```python
from crewai import Memory

memory = Memory()

# Store (LLM infers scope/categories/importance when omitted)
memory.remember("We use PostgreSQL for the user database.")
memory.remember("Staging uses port 8080.", scope="/project/staging")

# Recall (composite scoring; depth="shallow" for fast vector-only, "deep" for LLM-guided)
matches = memory.recall("What database do we use?", limit=5)
for m in matches:
    print(f"[{m.score:.2f}] {m.record.content}")

# Scopes (hierarchical, like paths); use explicit scope when known
agent_memory = memory.scope("/agent/researcher")
agent_memory.remember("Found three relevant papers.")

# Extract atomic facts from raw text before storing
facts = memory.extract_memories(meeting_notes)
for fact in facts:
    memory.remember(fact)

# Tuning (defaults: recency 0.3, semantic 0.5, importance 0.2, half-life 30 days)
memory = Memory(
    recency_weight=0.4,
    semantic_weight=0.4,
    importance_weight=0.2,
    recency_half_life_days=14,
)
```

**Best practices:** Use explicit scopes when you know them (e.g. `scope="/project/alpha/decisions"`); let the LLM infer for freeform content. Keep scope depth shallow (2–3 levels). Use `/{entity_type}/{id}` patterns (e.g. `/project/alpha`, `/agent/researcher`, `/customer/acme`). For scripts/notebooks without a crew lifecycle, call `memory.drain_writes()` or `memory.close()` after `remember_many()` so pending saves complete.

**Entity / knowledge:** Use scopes and optional **Knowledge** sources for RAG. Memory supports consolidation (dedup/update on save when similarity > threshold) and `remember_many()` (non-blocking; recall automatically waits for pending writes).

**Embedder:** Pass `embedder={"provider": "openai", "config": {"model_name": "text-embedding-3-small"}}` or use Ollama/local provider. Crew passes its `embedder` when `memory=True`. Default is OpenAI when not set.

### LanceDB vs ChromaDB/SQLite (and refactor impact)

| Aspect | CrewAI default (LanceDB) | ChromaDB + SQLite (e.g. custom MemoryManager) |
|--------|--------------------------|-----------------------------------------------|
| **What it is** | Single vector store; one `Memory` API with scopes, composite scoring, LLM analysis, consolidation. | Often split: vector store (ChromaDB) for semantic RAG + relational store (SQLite) for conversations, metrics, entity graphs. |
| **When used** | Whenever `Crew(..., memory=True)` or `Memory()` is used — CrewAI uses LanceDB under `./.crewai/memory` (or `$CREWAI_STORAGE_DIR/memory`). | Custom app-level memory (e.g. per-project short-term, cross-session long-term, entity memory) if you implement it. |
| **Data model** | One store; “short vs long” is expressed via recency/importance in scoring, not separate DBs. | Explicit separation: short-term (vectors per project), long-term (tables), entity (tables). |

In this repo, crews use **CrewAI memory** (`memory=True`, `embedder=get_embedder_config()`), so **LanceDB is already in use** for crew-internal context. Any custom **MemoryManager** (ChromaDB + SQLite) is a separate, optional layer for app-level persistence (e.g. before_task/after_task wiring). You do **not** need to refactor existing code or unit/integration tests for LanceDB: CrewAI’s default is already LanceDB. Tests that target your custom MemoryManager are testing that layer; change them only if you decide to remove or replace that layer (e.g. migrate to CrewAI’s Memory API for app-level context too).

---

## 6. Guardrails

**Task guardrails** validate or transform task output before the next task. Two kinds:

1. **Function-based:** `(result: TaskOutput) -> Tuple[bool, Any]` — `(True, output)` or `(False, error_message)`.
2. **LLM-based:** String description; the agent’s LLM validates the output.

**Retry:** On `(False, message)` the agent is given the message and retried up to `guardrail_max_retries` (default 3).

**Single guardrail (function):**

```python
from crewai import TaskOutput

def validate_word_count(result: TaskOutput) -> tuple[bool, any]:
    n = len(result.raw.split())
    if n < 100:
        return (False, f"Too short: {n} words. Need at least 100.")
    if n > 500:
        return (False, f"Too long: {n} words. Max 500.")
    return (True, result.raw)

task = Task(
    description="Write a blog post about AI",
    expected_output="Blog post 100–500 words",
    agent=writer,
    guardrail=validate_word_count,
    guardrail_max_retries=3,
)
```

**LLM guardrail (string):**

```python
task = Task(
    description="Write a blog post about AI",
    expected_output="Blog post under 200 words",
    agent=writer,
    guardrail="The post must be under 200 words and contain no technical jargon.",
)
```

**Multiple guardrails:** Use `guardrails=[...]` (list of functions and/or strings). They run in order; each receives the previous step’s output.

---

## 7. Tools

**Ways to create tools:**

1. **@tool decorator** — Simple functions; docstring and type hints define schema.
2. **BaseTool subclass** — Full control; `args_schema` (Pydantic) and `_run` (and optionally async `_run`).

**@tool decorator:**

```python
from crewai.tools import tool

@tool("Short name of my tool")
def my_tool(question: str) -> str:
    """Clear description for what this tool is useful for."""
    return "Result from your custom tool"
```

**BaseTool with schema:**

```python
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type

class MyToolInput(BaseModel):
    argument: str = Field(..., description="Description of the argument.")

class MyCustomTool(BaseTool):
    name: str = "My tool name"
    description: str = "What this tool does."
    args_schema: Type[BaseModel] = MyToolInput

    def _run(self, argument: str) -> str:
        # Tool logic
        return "Tool result"
```

**Async tool:**

```python
from crewai.tools import tool

@tool("fetch_data_async")
async def fetch_data_async(query: str) -> str:
    """Asynchronously fetch data for the query."""
    await asyncio.sleep(1)
    return f"Data for {query}"
```

**Error handling:** Tools should catch exceptions and return clear error messages so the agent can retry or report. CrewAI tools support caching via optional `cache_function` on the tool.

**Use with agent:** `Agent(..., tools=[my_tool, MyCustomTool()])`. Task-level `tools=[...]` override agent tools for that task.

---

## 8. Callbacks and hooks

**Task-level callback:** Pass `callback` on the `Task`; it runs after that task completes.

**Execution hooks (LLM and tool calls):** Use decorators or programmatic registration for before/after LLM and tool calls (logging, validation, sanitization, approval).

**Decorator-based hooks:**

```python
from crewai.hooks import (
    before_llm_call,
    after_llm_call,
    before_tool_call,
    after_tool_call,
)

@before_llm_call
def limit_iterations(context):
    if context.iterations > 10:
        return False  # Block
    return None

@after_tool_call
def log_tool(context):
    print(f"Tool {context.tool_name} completed")
    return None
```

**Crew-scoped hooks:**

```python
from crewai import CrewBase
from crewai.hooks import before_llm_call_crew, after_tool_call_crew

@CrewBase
class MyCrew:
    @before_llm_call_crew
    def validate_inputs(self, context):
        # Only for this crew
        return None

    @after_tool_call_crew
    def log_results(self, context):
        print(f"Result: {context.tool_result[:50]}...")
        return None
```

**Programmatic registration:**

```python
from crewai.hooks import register_before_tool_call_hook, register_after_llm_call_hook

def my_hook(context):
    return None

register_before_tool_call_hook(my_hook)
```

**Task callback (post-task):**

```python
def on_task_done(task_output):
    print("Task finished:", task_output.raw)

task = Task(
    description="...",
    expected_output="...",
    agent=agent,
    callback=on_task_done,
)
```

**Hook return values:** Return `False` to block the LLM or tool call; return `None` (or allow execution) to continue. Modify context in-place (e.g. `context.messages`, `context.tool_input`) to change behavior.

---

## Summary table

| Concept       | Key entry points |
|---------------|------------------|
| Agents        | `Agent(role, goal, backstory, tools, ...)`, YAML + `@agent` |
| Tasks         | `Task(description, expected_output, agent, context, output_pydantic, guardrail)` |
| Crews         | `Crew(agents, tasks, process=Process.sequential|hierarchical, memory, planning)` |
| Flows         | `Flow[State]`, `@start`, `@listen`, `@router`, `@human_feedback` |
| Memory        | `Memory()`, `remember`/`recall`/`scope`, Crew `memory=True` |
| Guardrails    | Task `guardrail` / `guardrails`, `(TaskOutput) -> (bool, Any)` or string |
| Tools         | `@tool`, `BaseTool` + `args_schema` + `_run` |
| Callbacks     | Task `callback`, `@before_llm_call`, `@after_tool_call`, crew-scoped `_crew` hooks |

For full details and examples, see [CrewAI Documentation](https://docs.crewai.com).
