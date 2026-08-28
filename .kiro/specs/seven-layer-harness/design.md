# Design — Seven-Layer Harness

**Spec ID:** `seven-layer-harness`
**Requirements:** [`requirements.md`](./requirements.md)
**Tasks:** [`tasks.md`](./tasks.md)

---

## 1. Overview

### 1.1 The central architectural move

Today the story is "three backends, nine agents, compare frameworks." Tools,
guardrails, memory, smoke, and traces exist, but each backend reaches them
through a different door. CrewAI can skip the smoke loop. Writes can hit the
filesystem without a draft. Compaction has nothing pinned. The eval taxonomy
already proved that most failures are in that gap.

**This design makes the harness the product and the orchestrators the engines.**

```
        SWAPPABLE ENGINES                     SHARED HARNESS (the product)
        ─────────────────                     ────────────────────────────
        CrewAI ────────┐
        LangGraph ─────┼──►  ToolBus ──► observations, drafts, gates
        Claude SDK ────┘         │
                                 ├── ConstraintLoader (CONSTRAINTS.md pinned)
                                 ├── SmokeGate (every backend, retry)
                                 ├── GuardrailRouter (by risk_class)
                                 ├── ReceiptWriter (disk is source of truth)
                                 ├── TaskRouter (config table)
                                 └── LessonsLoop (file in, file out)
                                              │
                                              ▼
                                    taxonomy checks (FM-001…013)
```

Every design decision below follows from protecting that boundary: **if a
backend can go around the bus, the layer is decoration.**

### 1.2 Design principles

1. **One execution path.** `{tool, args}` in; `ToolObservation` out. Adapters wrap.
2. **Pin, then summarize.** The LLM is not the compaction function for constraints.
3. **Draft then commit.** First suggestion must not be live destructive.
4. **Cheap checks first.** Mechanical verification does not consume the planner.
5. **Disk over stream.** Receipts and traces are the source of truth (`FM-008`).
6. **Feedback writes files, not weights.** A lesson that cannot survive into the
   next run's `CONSTRAINTS.md` is a prompt tweak.
7. **Reuse what exists.** File tools, smoke gate, `TeamMonitor`, `output/runs/`,
   eval checks, `Backend` protocol, lessons store — wrap and lift, do not rewrite.

### 1.3 What gets reused, refactored, and added

| Existing | Fate |
| --- | --- |
| `src/ai_team/tools/file_tools.py` etc. | Implementations become bus handlers; `@tool` wrappers become adapters |
| `tools/langchain_adapter.py` | Calls `ToolBus.invoke`; keep CrewAI→LangChain conversion |
| SDK `hooks/security.py` + MCP server | PreToolUse routes native tools into the bus or denies; MCP handlers call the bus |
| `tools/smoke_tools.py` | Shared gate; CrewAI gains an inner retry node (R9) |
| `guardrails/*` | Mapped onto `risk_class`; evidence bundle from existing events |
| `memory/lessons.py` + `self_improvement_runtime.py` | Close the effectiveness loop (R18); write `LESSONS.md` |
| `core/results/writer.py` | Emit `receipt.json` / `receipt.md` into the existing bundle |
| `monitor.py` `TeamMonitor` | Source for evidence bundle; dashboard reads receipt |
| `evals/taxonomy/` + `evals/checks/` | Additive: `harness_layer`, FM-011…013, new checks |
| `config/models.py` + team profiles | Router table; `risk_class` on profiles |
| `docs/ARCHITECTURE.md` | Link out; do not duplicate |

---

## 2. Architecture

### 2.1 Layer diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│  L7  Feedback         lessons → CONSTRAINTS.md → next run → effectiveness│
├──────────────────────────────────────────────────────────────────────────┤
│  L6  Routing          task_type × env → model id (config table)          │
├──────────────────────────────────────────────────────────────────────────┤
│  L5  Observability    receipt.json  •  drift CLI  •  TeamMonitor (view)  │
├──────────────────────────────────────────────────────────────────────────┤
│  L4  Guardrails       risk_class → subset of catalog  •  evidence bundle │
├──────────────────────────────────────────────────────────────────────────┤
│  L3  Context          CONSTRAINTS.md (pin)  STATE.md  LESSONS.md         │
├──────────────────────────────────────────────────────────────────────────┤
│  L2  Verification     cheap (ruff/pytest/smoke)  /  strong (judge/arch)  │
├──────────────────────────────────────────────────────────────────────────┤
│  L1  ToolBus          schema → permission → execute|draft|gate → observ. │
├──────────────────────────────────────────────────────────────────────────┤
│  L0  Orchestrators    crewai | langgraph | claude-agent-sdk              │
└──────────────────────────────────────────────────────────────────────────┘
```

Eval checks sit **beside** L1–L7, consuming traces/receipts. They are not a
layer of the runtime; they are how we know a layer is real.

### 2.2 File layout

```
src/ai_team/
├── tools/
│   ├── bus.py                  # ToolBus.invoke, registry, observations
│   ├── kinds.py                # ToolKind, RiskClass, ToolSpec
│   ├── draft.py                # draft area + commit_write
│   ├── file_tools.py           # EXISTING — handlers registered on the bus
│   ├── code_tools.py           # EXISTING
│   ├── git_tools.py            # EXISTING; push/destroy classified irreversible
│   ├── smoke_tools.py          # EXISTING
│   └── langchain_adapter.py    # EXISTING — wrap invoke()
├── harness/                    # thin facades so backends import one place
│   ├── __init__.py
│   ├── context.py              # ConstraintLoader, StateWriter
│   ├── receipt.py              # ChangeReceipt model + writer
│   └── router.py               # task-type table lookup
├── memory/
│   ├── lessons.py              # EXISTING + effectiveness + LESSONS.md
│   └── self_improvement_runtime.py
├── guardrails/                 # EXISTING + risk_class dispatch
├── config/
│   ├── models.py               # EXISTING + router table
│   ├── team_profiles.yaml      # + risk_class
│   └── task_routes.yaml        # NEW — task_type × env → model
└── backends/                   # adapters only; no private write paths

evals/
├── taxonomy/failure_modes.yaml # + harness_layer, FM-011…013
└── checks/
    ├── context.py              # CHK-constraint-survival
    ├── tools_bus.py            # CHK-draft-commit (FM-012)
    └── feedback.py             # CHK-lesson-effectiveness

docs/HARNESS.md                 # NEW — layer index
```

`src/ai_team/harness/` is a facade, not a dump of all logic. Tools stay in
`tools/` because that matches current imports and the project dependency
direction (`utils → models → guardrails → tools → agents → …`). The facade
exists so backends import `ai_team.harness` instead of reaching into three
packages.

### 2.3 Dependency direction

Unchanged: **utils → models → guardrails → tools → agents → config → crews →
flows → main/ui.**

`harness/` may import tools, guardrails, memory, models. Backends import
`harness` + `tools.bus`. `harness` MUST NOT import backends or crews.

---

## 3. Data models

All models are Pydantic v2.

### 3.1 ToolBus

```python
ToolKind = Literal["read", "write", "irreversible"]
RiskClass = Literal["low", "write", "irreversible", "customer-visible"]
ObservationCode = Literal[
    "ok", "drafted", "gated", "schema_invalid",
    "permission_denied", "not_found", "validation_failed", "error",
]

class ToolSpec(BaseModel):
    name: str
    kind: ToolKind
    risk_class: RiskClass
    args_schema: type[BaseModel]
    handler: Callable[..., ToolObservation]  # not serialized
    allow_roles: list[str] | None = None     # None = all roles in profile

class ToolRequest(BaseModel):
    tool: str
    args: dict[str, Any]
    agent_role: str | None = None
    phase: str | None = None
    backend: str | None = None
    run_id: str | None = None

class ToolObservation(BaseModel):
    ok: bool
    code: ObservationCode
    summary: str = Field(..., max_length=2000)
    artifact_refs: list[str] = Field(default_factory=list)
    tool: str
    kind: ToolKind
    risk_class: RiskClass
    duration_ms: int
    detail: dict[str, Any] = Field(default_factory=dict)
```

Handlers return `ToolObservation`. They never return a raw `str` to the agent.

### 3.2 Draft commit

```python
class DraftRecord(BaseModel):
    draft_id: str
    intended_path: str          # relative to workspace
    sha256: str
    created_at: datetime
    agent_role: str | None
    phase: str | None

class CommitResult(BaseModel):
    ok: bool
    committed: list[str]
    rejected: list[str]
    observation: ToolObservation
```

Draft bytes live under `workspace/<id>/.harness/drafts/<draft_id>`. Live
workspace paths are untouched until `commit_write`. `.harness/` is gitignored
inside the generated project (or listed in the generated `.gitignore`) so it
is not shipped as app source.

### 3.3 Three-file contract

```python
class ConstraintItem(BaseModel):
    id: str                     # e.g. CST-canary, CST-no-schema-change
    text: str
    source: Literal["human", "harness", "lesson"]
    pinned: bool = True

class PhaseFacts(BaseModel):
    phase: str
    files_written: list[str]
    tests: dict[str, Any]
    smoke: dict[str, Any] | None
    errors: list[str]
    ended_at: datetime

class LessonRecord(BaseModel):
    lesson_id: str
    fm_id: str
    constraint: str
    evidence_span: str | None
    created_at: datetime
    ttl_runs: int = 20
    recurrence_window: int = 5
    recurrences: int = 0
    status: Literal["active", "effective", "ineffective", "escalated"]
```

File formats (harness-owned, markdown for humans, parseable by convention):

`CONSTRAINTS.md` — each item is an `## CST-…` heading plus body. Never rewritten
by a summarizer. Append-only except TTL expiry of lesson-sourced items.

`STATE.md` — YAML front matter or a fenced `json` facts block plus a short
bullet list. Last `N` (default 5) `PhaseFacts` only.

`LESSONS.md` — table generated from `LessonRecord`s; the SQLite store remains
authoritative.

### 3.4 Change receipt

```python
class ChangeReceipt(BaseModel):
    schema_version: int = 1
    run_id: str
    backend: str
    team_profile: str
    policy_version: str
    context_sources: list[str]          # paths + lesson ids
    tool_permission_set: list[str]
    routes: list[RouteRecord]           # phase / task_type / model_id
    tests: dict[str, Any]
    smoke: dict[str, Any]
    overrides: list[str]
    cost_usd: float | None
    cost_per_accepted_change: float | None
    failure_ids: list[str]
    accepted: bool
    output_hash: str | None
    rollback_ref: str | None            # git sha or snapshot id
    guardrail_evidence: GuardrailEvidence
    provenance: dict[str, Any]
```

Written next to existing `run.json`. Dashboard reads this file.

### 3.5 Task routes

```yaml
# src/ai_team/config/task_routes.yaml
version: "1"
routes:
  dev:
    classify: openrouter/openai/gpt-4.1-mini
    format: openrouter/openai/gpt-4.1-mini
    mechanical_check: deterministic   # sentinel: no LLM
    plan: openrouter/...              # from ENV_MODELS manager/architect
    judge: openrouter/...
    generate: openrouter/...          # role default
```

`deterministic` means "call ruff/pytest/smoke, not a model." Same-model
profiles override every non-deterministic type to one id and set
`same_model: true` on the receipt.

---

## 4. Component design

### 4.1 L1 — ToolBus (R4–R7)

```python
class ToolBus:
    def register(self, spec: ToolSpec) -> None: ...
    def invoke(self, request: ToolRequest) -> ToolObservation: ...
```

Pipeline inside `invoke`:

1. Lookup spec; unknown tool → `code: not_found`.
2. Validate `args` against `args_schema`; fail → `schema_invalid`.
3. Permission: role allowlist, profile tool overrides, `risk_class` vs
   irreversible policy.
4. Kind branch:
   - `read` → handler → `ok` / `error`
   - `write` → handler writes draft → `drafted`
   - `irreversible` → unless policy/human token present → `gated`
5. Cap `summary`; spill to artifact.
6. Audit log + spans (`tool_use` / `tool_result`).

**FM-001 invariant (R7).** A phase-end hook (shared, not backend-specific)
inspects: fenced code in the last assistant message vs ToolBus write
observations in that phase. Violation is a span `type=error` with
`payload.fm_id = FM-001`. Salvage, if enabled, calls `invoke` with
`agent_role="_harness"` so it is a bus write.

**Backend adapters**

| Backend | Mechanism |
| --- | --- |
| CrewAI | `@tool` functions call `get_bus().invoke(...)` and stringify `summary` for the framework |
| LangGraph | `langchain_adapter` builds `StructuredTool` whose `func` is `invoke` |
| Claude SDK MCP | MCP tool bodies call `invoke` |
| Claude SDK native | `PreToolUse`: map `Write`/`Bash` to bus tools or deny |

**Non-bypass test.** AST or wrap of `write_file`, `delete_file`,
`execute_shell`: if the call stack does not include `ToolBus.invoke`, fail.
Practical approach: handlers are module-private (`_write_file_impl`); public
names only go through the bus. Existing tests import impl via bus or a
`testing` hook.

### 4.2 L1 — Draft commit (R5, FM-012)

Write handler never truncates the live file. It writes
`.harness/drafts/<id>` and records `DraftRecord`. `commit_write` validates
paths (existing `validate_path`), scans content (existing security guardrail),
then `os.replace` into the workspace.

Irreversible catalog (initial):

- `delete_file`
- git push / force / delete-branch (if exposed)
- `docker compose down -v` / volume wipes
- overwrite of `requirements.txt`, `pyproject.toml`, lockfiles, `.env`

`CHK-draft-commit`: among `tool_result` spans with `kind=write` and
`code=ok` targeting a live workspace path, none may exist except
`commit_write` promotions and harness files. Fail if a `write_file`
observation has `code=ok` against `src/` directly.

### 4.3 L2 — Verification split and smoke node (R8–R10)

**Cheap path (no planner model):** ruff, compile, pytest, diff-in-scope,
`run_app_smoke`. Invoked from QA tools and from the smoke node.

**Strong path:** architecture compliance guardrail, salvage-after-smoke-fail
re-prompt (already exists on LangGraph + SDK).

**CrewAI smoke node.** Today CrewAI is covered only by `_run_post_run_quality_gates`.
Add a listen/router after testing in `AITeamFlow` (or `testing_crew` kickoff
tail): call `run_app_smoke`, on failure `retry_development` with the traceback
payload, bounded by existing `max_retries`. Reuse LangGraph's
`route_after_smoke` semantics, not a third policy.

**cost_per_accepted_change.** `ReceiptWriter` uses `CostRecord` + accepted
predicate (R10.2). Suite aggregation can live in evals later; v1 is per-run
on the receipt.

### 4.4 L3 — Context contract (R11–R12)

`ConstraintLoader.load(workspace) -> list[ConstraintItem]` reads
`docs/CONSTRAINTS.md` (create from template + intake canary on first run).

Injection: every backend's phase prompt builder prepends the full file.
Traces: `phase_start.payload.constraint_ids: [...]` and
`constraint_sha256`. `CHK-constraint-survival` compares intake ids to testing
and deployment `phase_start` payloads.

`StateWriter.write(phase, facts)` rewrites `docs/STATE.md` keeping last N
phases. Deterministic. No LLM.

Compaction of **other** context (transcript, retrieval) may still use a
summarizer; it MUST take the pin list as an input it cannot drop. If no
summarizer exists yet, do not add one in v1 — pinning is the fix; a bad
summarizer is how turn 40 migrates the table.

### 4.5 L4 — Guardrail risk scaling (R13–R14)

```python
GUARDRAIL_BY_RISK: dict[RiskClass, list[str]] = {
    "low": ["path_traversal", "secrets"],
    "write": ["path_traversal", "secrets", "scope", "code_quality"],
    "irreversible": ["*"],
    "customer-visible": ["*"],
}
```

Exact names map to existing functions in `behavioral.py` / `security.py` /
`quality.py`. Operational spend/timeout/circuit-breaker stay global (they are
not blast-radius of the *output*; they are run survival — `FM-007`).

Evidence bundle: filter `TeamMonitor` guardrail events + ToolBus permission
denials into `receipt.guardrail_evidence`.

### 4.6 L5 — Receipt and drift (R15–R16)

`ReceiptWriter.write(result, workspace, output_dir)` at the same call sites
as today's results writer (including abort/kill). SDK path must use it.

Dashboard: add a "Receipt" view that fetches `GET /api/runs/<id>/receipt`
reading the file. Do not compute cost from the live event buffer.

Drift CLI: `evals/drift.py` reads `evals/traces/` or `output/runs/*/receipt.json`.
Windows: last 7 days vs prior 7, or last N vs previous N. Metrics: FM hit
rate, smoke pass, files written, cost, cost_per_accepted_change. Warn-only in
v1 (no CI gate).

### 4.7 L6 — Task router (R17)

`harness/router.py::resolve(task_type, env, profile) -> Route`.
Call sites: LangGraph `create_chat_model_for_role` can stay for **role**
defaults; new cheap verifiers call `resolve("mechanical_check", ...)`.
v1 wires `mechanical_check`, `plan`, `generate`. Others alias to `generate`
with `logger.warning("task_route_unwired")`.

Receipt gets one `RouteRecord` per LLM call or per phase (phase is enough
for v1 if per-call is too invasive). Prefer per-call when the token tracker
already fires.

### 4.8 L7 — Lessons loop (R18)

Extend `memory/lessons.py`:

1. On smoke/check fail → `LessonRecord` with `fm_id` + one-sentence
   constraint distilled **deterministically** from check id + evidence
   (template, not LLM), optional LLM polish later.
2. Dedup: `hash(fm_id + normalize(constraint))`.
3. Inject: append to `CONSTRAINTS.md` as `## CST-lesson-<id>` with
   `source: lesson`.
4. On each run end: if `fm_id` present in this run's `failure_ids`,
   `recurrences += 1`. After `recurrence_window` runs, set `effective` or
   `ineffective`. Ineffective → `escalated` log + remaining in constraints
   with a stronger template (e.g. "MUST use ToolBus write; do not emit
   fences").

`CHK-lesson-effectiveness`: fail if any lesson in the workspace is
`ineffective` and not `escalated`.

Until step 4 ships, `docs/HARNESS.md` marks feedback `instrumented` not
`closed-loop`.

---

## 5. Taxonomy and checks

### 5.1 `harness_layer` field

Additive on `FailureMode`. Loader: optional; if present, must be in
`VALID_HARNESS_LAYERS`. Framework/provider FMs omit it.

Bump taxonomy `version` to `1.1.0`.

### 5.2 New checks

| Check | FM | Predicate (fails when…) |
| --- | --- | --- |
| `CHK-constraint-survival` | FM-011 | a constraint id present at intake `phase_start` is absent at testing or deployment `phase_start` |
| `CHK-draft-commit` | FM-012 | a `write` tool_result has `code=ok` on a live `src/` or `tests/` path without a preceding draft + `commit_write` |
| `CHK-lesson-effectiveness` | FM-013 | a lesson is `ineffective` and not escalated |

Each gets fail / pass / `not_applicable` fixtures like eval-harness Phase 3.

`CHK-tool-call-emitted` stays; bus invariant feeds the same spans.

---

## 6. Error handling

| Condition | Behaviour |
| --- | --- |
| Unknown tool | `ok: false`, `code: not_found`; no execute |
| Schema fail | `ok: false`, `code: schema_invalid`; no execute |
| Permission / irreversible without gate | `ok: false`, `code: gated` or `permission_denied` |
| Draft commit path escape | reject; do not promote |
| Missing `CONSTRAINTS.md` at first tool call | create from template (empty human section + optional canary); warn |
| Lessons subsystem error | log; **never** abort the run (existing SI convention) |
| Receipt write fail | log error; run result still returned; comparison treats receipt as missing (FM-008 cousin) |
| CrewAI smoke fail after retries | do not `complete`; escalate like LangGraph |
| SDK native tool bypass | PreToolUse deny; test asserts deny |

Governing principle: **the harness never silently converts "I don't know" or
"I skipped a layer" into a successful live write.**

---

## 7. Testing strategy

### 7.1 Unit — `tests/unit/tools/`, `tests/unit/harness/`, `tests/unit/memory/`

- ToolBus: each `ObservationCode`; summary cap; span emission.
- Draft: write does not touch live path; commit does; irreversible gated.
- ConstraintLoader: full inject; canary survives a fake compaction that
  drops other files.
- Receipt: required fields; `cost_per_accepted_change` denominator.
- Lessons: dedup, TTL, effectiveness flip, inject into CONSTRAINTS.md.
- Router: table lookup; `deterministic` sentinel; same_model profile.

### 7.2 Adversarial — `tests/unit/tools/test_bus_adversarial.py`

- `../` paths, `.env` writes, `confirm=true` delete without policy.
- Args that look like prompt injection (`ignore previous…; rm -rf`).
- SDK hook fixture: native `Write` outside bus → deny.

### 7.3 Eval checks — `tests/unit/evals/`

- Three fixtures per new check; mutation flip; registry validation includes
  FM-011…013.

### 7.4 Integration

- One backend (prefer LangGraph, fastest) writes a file via the bus: draft
  appears, commit materializes, receipt lists the tool.
- CrewAI smoke node exists in flow introspection (listen/router names),
  even if the test mocks `run_app_smoke`.

### 7.5 What is not tested automatically

Live model routing quality. Whether heterogeneous routes beat same-model
is an eval suite question, not pytest.

---

## 8. Migration and sequencing risk

1. **Additive bus first.** Register handlers; keep old wrappers calling
   impls **and** the bus until adapters are proven. Then flip wrappers to
   bus-only (Phase 3).
2. **Draft-commit is the sharp edge.** Land behind a setting
   `AI_TEAM_DRAFT_WRITES=1` default **on** for new code paths, with a
   one-phase escape hatch for tests that monkeypatch `write_file`. Remove
   the hatch when unit tests are migrated.
3. **CrewAI smoke loop** touches `main_flow.py` — the file that produced
   `FM-002`. Reuse the `on_<trigger>` naming convention and the existing
   self-listen meta-test. Do not name a listener after its own method.
4. **Taxonomy bump** is additive; eval-harness loader tests must be
   extended, not broken.
5. **Dashboard receipt view** is last in the observability phase so the
   file format can settle.

The irreversible decision is the observation schema and the three-file
names. Freeze those in Phase 1–2 before backends emit them at volume.

---

## 9. Docs split

| Doc | Owns |
| --- | --- |
| `docs/HARNESS.md` | Seven layers, module paths, FM, checks, instrumentation status |
| `docs/ARCHITECTURE.md` | Backends, flows, crews, UI, ADRs |
| `docs/posts/failure-taxonomy.md` | Narrative of FM-001…010; links to harness_layer |
| `docs/SELF_IMPROVEMENT.md` | Smoke gate (shipped) vs lessons (this spec closes the loop) |
| `.kiro/specs/eval-harness/` | How we measure; not how we execute |

---

## 10. Interview-facing summary

> The product is the harness: one ToolBus, pinned constraints, smoke on every
> backend, a change receipt on disk, and lessons that write files the next run
> actually loads. The orchestrators are engines. The taxonomy is the test suite
> — seven of ten failures we measured were already this layer, and the tweet's
> production checklist is how we stop treating that as an accident.
