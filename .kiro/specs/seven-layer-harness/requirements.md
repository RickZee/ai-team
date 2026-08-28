# Requirements — Seven-Layer Harness

**Spec ID:** `seven-layer-harness`
**Status:** Draft for implementation
**Owner:** Rick Zakharov
**Target repo:** `ai-team` (in-place; shared path above backends)
**Created:** 2026-08-28
**Sources:** [choopyplug1 production checklist](https://x.com/choopyplug1/status/2088973320964215253);
`docs/posts/failure-taxonomy.md`; `docs/SELF_IMPROVEMENT.md`; `.kiro/specs/eval-harness/`

---

## Introduction

`ai-team` runs a nine-agent software engineering team across three orchestration
backends (CrewAI, LangGraph, Claude Agent SDK). It already measured that **7 of 10
failure modes are harness**, 1 is model, 1 is framework, 1 is provider.

The tweet's claim is the same thesis from the other side: prompt engineering and
context engineering got absorbed. The bottleneck is the execution layer around the
model — tools, verification, memory, permissions, observability, routing, feedback.
Same model + different harness = different outcomes.

The useful move is not "add a harness." We already have one. The useful move is to
treat the seven layers as the **product architecture**, then close the gaps the post
names that the taxonomy already keeps hitting.

Today those layers exist as a skeleton:

| Layer | What exists | What is missing |
| --- | --- | --- |
| Tools | File / code / git / test tools with path checks; prose salvage (`FM-001`); SDK `PreToolUse`; sandboxed execution | A single dispatcher every backend must go through; draft-then-commit; structured observations |
| Verification | QA role; runtime smoke (HTTP including CRUD); quality guardrails; Tier A `$0` replay; `FM-006` | Cheap vs strong split; smoke as a graph node on **CrewAI**; `cost_per_accepted_change` |
| Context | SQLite `LongTermStore`; experimental lessons; filesystem handoff; team profiles | Pinned constraints the summarizer cannot drop; `STATE.md` / `CONSTRAINTS.md` before first tool call |
| Guardrails | Behavioral / security / quality / operational; `FM-005`; profiles right-size the crew | `risk_class` scaled to blast radius; evidence pack per run |
| Observability | `TeamMonitor`, structlog, cost estimator, eval traces, `FM-008` | Change receipt; week-over-week drift |
| Routing | `config/models.py`, team profiles, `--backend` | Mid-run routing by **task type**, not by agent prose |
| Feedback | Smoke → retry on LangGraph + SDK; lessons capture sketched | Effectiveness tracking; a rejection that writes a constraint the *next* run loads |

After this spec the story is:

**Shared harness (the product) → swappable orchestrators (the engines) → taxonomy as the test suite.**

### Design constraints (decided)

| Constraint | Decision |
| --- | --- |
| Product boundary | Lift tools, guardrails, memory, smoke, spend, traces, and receipts **above** backends. Finish the `Backend` protocol so CrewAI cannot bypass the bus. |
| Taxonomy `layer` | Keep the four-way attribution (`model` \| `framework` \| `harness` \| `provider`) from eval-harness R4. Add `harness_layer` for the seven production layers. Do not overwrite the published claim. |
| Eval harness | New checks and FMs register in `evals/`. Do not reopen eval-harness phases. |
| Docs split | `docs/HARNESS.md` = layer → module → FM → check. `docs/ARCHITECTURE.md` stays backends, flows, crews. |
| Backwards compatibility | Existing `@tool` functions, LangChain adapters, and SDK MCP tools keep working by wrapping the bus — callers do not rewrite every agent. |
| Demo bar | All seven layers instrumented. Not all seven polished. Demos already shipped. |

### Non-goals (v1)

- Replacing CrewAI, LangGraph, or the Claude Agent SDK.
- Fine-tuning or changing model weights. Feedback writes files, not weights.
- SOC2 / EU AI Act certification. The evidence bundle is the auditor artifact; the audit is out of scope.
- 30-day policy re-audit automation (named in the post; scheduled reminder in docs is enough for v1).
- Role-eval breadth (`docs/EVALS_ROADMAP.md`).
- Making CrewAI the recommended production backend. CrewAI stays a comparison datapoint; it still must use the bus and the smoke node.
- Rewriting `docs/posts/failure-taxonomy.md` as a seven-layer essay. Cross-link it.

### Glossary

| Term | Definition |
| --- | --- |
| **Harness** | Everything around the model that executes, verifies, remembers, permits, observes, routes, and learns. The product. |
| **Orchestrator / backend** | CrewAI, LangGraph, or Claude Agent SDK. An engine. Swappable. |
| **ToolBus** | The only execution path for tool calls. Validates schema, checks permission, executes or drafts, returns a structured observation. |
| **Tool kind** | `read` (immediate), `write` (draft then commit), `irreversible` (human or policy gate). |
| **Risk class** | `low` \| `write` \| `irreversible` \| `customer-visible`. Scales which guardrails run. |
| **Observation** | `{ok, code, summary, artifact_refs}` returned to the agent. Never raw shell for the model to guess at. |
| **Pinned constraint** | Text in `CONSTRAINTS.md` that compaction is forbidden to drop or summarize. |
| **Change receipt** | One JSON + Markdown artifact per run: context sources, policy, tool permissions, routes, tests/smoke, overrides, cost, accepted hash, rollback pointer. |
| **Task type** | `classify` \| `format` \| `mechanical_check` \| `plan` \| `judge` \| `generate`. Router input. |
| **Harness layer** | `tools` \| `verification` \| `context` \| `guardrails` \| `observability` \| `routing` \| `feedback`. |
| **Accepted change** | A run whose smoke (or skip-with-reason) and required artifacts pass, with an output hash recorded on the receipt. |

---

## Layer map (existing FMs)

Keep `layer` as the four-way root cause. Add `harness_layer` as below. `FM-002`
stays framework; `FM-009` stays provider; `FM-001` stays model with
`harness_layer: tools` because the bus is how we stop it.

| ID | Slug | `layer` | `harness_layer` |
| --- | --- | --- | --- |
| FM-001 | `tool_call_omission` | model | tools |
| FM-002 | `self_triggering_retry_loop` | framework | — |
| FM-003 | `runtime_coupling_starvation` | harness | observability |
| FM-004 | `run_id_collision` | harness | observability |
| FM-005 | `guardrail_false_positive` | harness | guardrails |
| FM-006 | `runtime_verification_gap` | harness | verification |
| FM-007 | `unbounded_spend` | harness | guardrails |
| FM-008 | `metric_source_drift` | harness | observability |
| FM-009 | `provider_dialect_mismatch` | provider | — |
| FM-010 | `gate_environment_mismatch` | harness | verification |

New FMs (this spec):

| ID | Slug | `layer` | `harness_layer` | Detection |
| --- | --- | --- | --- | --- |
| FM-011 | `constraint_drop` | harness | context | check (`CHK-constraint-survival`) |
| FM-012 | `uncommitted_write` | harness | tools | check (`CHK-draft-commit`) |
| FM-013 | `lesson_ineffective` | harness | feedback | check (`CHK-lesson-effectiveness`) |

`cost_per_accepted_change` is a **receipt metric**, not an FM.

---

## Requirements

### R1 — Shared harness above backends

**User story:** As a maintainer, I want tools, verification, memory, spend, traces,
and receipts to live above the orchestrators, so swapping a backend cannot silently
drop a layer.

**Acceptance criteria**

1.1 THE SYSTEM SHALL expose a shared harness package under `src/ai_team/harness/`
(or equivalent modules under `tools/`, `memory/`, `guardrails/` that the backends
import — see design) such that CrewAI, LangGraph, and Claude Agent SDK call the
same ToolBus, the same smoke gate, the same constraint loader, and the same
receipt writer.

1.2 WHEN a backend executes a tool, THE SYSTEM SHALL route that call through the
ToolBus. A unit test SHALL fail if a public write/delete/shell entrypoint is
invoked without a ToolBus span.

1.3 THE SYSTEM SHALL NOT require a backend to reimplement path validation, draft
commit, or observation shaping. Adapters wrap; they do not copy.

1.4 CrewAI SHALL use the same smoke node contract as LangGraph and the Claude
Agent SDK (R9). "Comparison-only" SHALL NOT mean "no loop."

---

### R2 — Taxonomy `harness_layer` and new failure modes

**User story:** As an eval engineer, I want every FM to name which production layer
it lives in, so `docs/HARNESS.md` and `evals/taxonomy/COVERAGE.md` cannot drift.

**Acceptance criteria**

2.1 THE SYSTEM SHALL add an optional field `harness_layer` to
`evals/taxonomy/failure_modes.yaml` with enum
`tools | verification | context | guardrails | observability | routing | feedback`.

2.2 THE SYSTEM SHALL keep existing `layer` values unchanged for FM-001…010.

2.3 THE SYSTEM SHALL seed `harness_layer` on FM-001…010 per the layer map above.
FM-002 and FM-009 SHALL omit `harness_layer` (or set it null).

2.4 THE SYSTEM SHALL add FM-011, FM-012, FM-013 with full definitions, `detection:
check`, `implemented_by` naming the new checks, `introduced_in: "1.1.0"`, and
`status: active`.

2.5 THE taxonomy loader SHALL accept the new field, reject unknown enum values, and
SHALL NOT require `harness_layer` on framework- or provider-attributed FMs.

2.6 `evals/taxonomy/COVERAGE.md` SHALL include a `Harness layer` column.

---

### R3 — `docs/HARNESS.md` as the layer index

**User story:** As a reader (and as a candidate), I want one document that maps
layer → module → FM → check, so `ARCHITECTURE.md` can stay about backends.

**Acceptance criteria**

3.1 THE SYSTEM SHALL add `docs/HARNESS.md` covering all seven layers, each with:
what the post requires, what `ai-team` has, the module path, the FMs, and the
checks.

3.2 `docs/ARCHITECTURE.md` SHALL link to `docs/HARNESS.md` from the tools /
guardrails / memory sections and SHALL NOT duplicate the seven-layer checklist.

3.3 `docs/posts/failure-taxonomy.md` SHALL link to `docs/HARNESS.md` and to
`harness_layer` in the YAML.

3.4 `docs/SELF_IMPROVEMENT.md` SHALL point at R19 for the closed lessons loop and
SHALL keep the honesty about experimental vs shipped.

---

### R4 — ToolBus is the only execution path

**User story:** As a security engineer, I want every tool call — from any backend —
to pass through one dispatcher, so schema, permission, and audit cannot be skipped.

**Acceptance criteria**

4.1 THE SYSTEM SHALL introduce `ToolBus` as the only execution path for registered
tools. The model (or adapter) SHALL submit `{tool, args}`; the bus SHALL validate
schema, check permission, execute or draft, and return a `ToolObservation`.

4.2 THE SYSTEM SHALL emit a `tool_use` span before execution and a `tool_result`
span after, with `tool`, `kind`, `risk_class`, `ok`, and `code`, so eval checks
and the receipt can read them without parsing prose.

4.3 WHEN schema validation fails, THE SYSTEM SHALL NOT execute the tool and SHALL
return `ok: false`, `code: schema_invalid`.

4.4 WHEN permission fails, THE SYSTEM SHALL NOT execute the tool and SHALL return
`ok: false`, `code: permission_denied`.

4.5 Existing CrewAI `@tool` wrappers, LangChain `StructuredTool` adapters, and
Claude SDK MCP handlers SHALL call the bus. Direct filesystem or `subprocess`
from those wrappers SHALL be removed or reduced to a private implementation used
only by the bus.

4.6 Claude SDK native tools (`Write`, `Bash`, …) SHALL be gated: either routed
into the bus via `PreToolUse`, or denied when they would bypass workspace policy.
A test SHALL cover the bypass attempt.

---

### R5 — Tool kind: read / write / irreversible

**User story:** As an operator, I want writes to be draft-then-commit and
irreversible actions to wait for a gate, so the model cannot escalate on first
suggestion.

**Acceptance criteria**

5.1 Every registered tool SHALL declare `kind: read | write | irreversible` and
`risk_class: low | write | irreversible | customer-visible`.

5.2 `read` tools SHALL execute immediately on a valid, permitted call.

5.3 `write` tools SHALL write to a draft area (not the live workspace path) and
return `code: drafted` with an artifact ref. A separate `commit_write` (or
`commit_changes`) tool SHALL promote drafts after policy checks.

5.4 Overwriting `requirements.txt`, deleting files, `git push`, and
`docker compose down -v` (and equivalents) SHALL be `irreversible` and SHALL NOT
execute on the first suggestion.

5.5 `irreversible` tools SHALL require a human interrupt **or** an explicit
allow-policy on the team profile / run config. Default profiles (`smoke`,
`prototype`, `full`) SHALL deny them unless opted in.

5.6 `delete_file` SHALL move from `confirm=True` on the tool schema to
`kind: irreversible` on the bus. A model passing `confirm=true` SHALL NOT be
sufficient.

5.7 THE SYSTEM SHALL implement `CHK-draft-commit` (FM-012): fail when a
development or QA phase has a successful live write that did not pass through
draft-then-commit (except `read` tools and harness-owned files: `STATE.md`,
receipts, logs).

---

### R6 — Structured observations (never raw shell)

**User story:** As an agent runtime, I want every tool result in a fixed shape, so
the model cannot be asked to parse shell output and so injection cannot hide in
stderr.

**Acceptance criteria**

6.1 Every ToolBus result SHALL be a `ToolObservation`: `{ok, code, summary,
artifact_refs}` plus `tool`, `kind`, `risk_class`, `duration_ms`. Optional
`detail` MAY hold structured fields (exit code, paths) but SHALL NOT dump raw
stdout/stderr into the model-visible `summary` beyond a capped excerpt.

6.2 `summary` SHALL be ≤ 2,000 characters. Excess SHALL be stored as an artifact
and referenced.

6.3 THE SYSTEM SHALL NOT return a raw shell transcript as the sole tool message
content to any backend.

6.4 Observation `code` SHALL be a closed enum at minimum: `ok`, `drafted`,
`gated`, `schema_invalid`, `permission_denied`, `not_found`, `validation_failed`,
`error`.

---

### R7 — FM-001 as a bus invariant

**User story:** As a developer of the harness, I want "phase produced code in text
and zero successful write-tool spans" to be a bus invariant, not only a salvage
afterthought.

**Acceptance criteria**

7.1 WHEN a development or testing phase ends with fenced code in an assistant
message and zero successful write observations (`ok` or `drafted`), THE ToolBus
(or phase hook) SHALL record an `FM-001` invariant violation on the trace.

7.2 Existing prose-as-code salvage MAY still run, but it SHALL go through the
bus as a harness-originated write (draft then commit), not a backdoor
`Path.write_text`.

7.3 `CHK-tool-call-emitted` SHALL keep working and SHALL additionally treat
"zero ToolBus write spans" as the same failure when an audit log exists.

---

### R8 — Cheap vs strong verification split

**User story:** As a cost owner, I want syntax, compile, pytest, and diff-in-scope
to use deterministic checks or a cheap model, so the planning model is not billed
for `ruff`.

**Acceptance criteria**

8.1 THE SYSTEM SHALL classify verifiers as `cheap` or `strong`. Cheap: syntax,
compile, ruff/mypy, pytest, diff-in-scope, smoke HTTP. Strong: architecture
judgment, salvage-after-smoke-fail, contested design review.

8.2 Cheap verifiers SHALL NOT invoke the planning / architecture model id. They
SHALL be deterministic code or a model from the `mechanical_check` route (R18).

8.3 Strong verifiers MAY use the architecture / judge route.

8.4 Maker and checker SHALL NOT be required to share a model family. Default
production profiles SHALL use a different model (or a deterministic checker) for
cheap verification than for generation. Same-model profiles (`full-claude`,
`smoke-claude`) SHALL remain available for science and SHALL set
`same_model: true` on the receipt.

---

### R9 — Smoke is a graph node on every backend

**User story:** As a QA owner, I want a failed smoke to retry development on
CrewAI the same way it does on LangGraph and the Claude Agent SDK, so
"comparison-only" cannot skip `FM-006`.

**Acceptance criteria**

9.1 THE SYSTEM SHALL run `run_app_smoke` as an explicit phase/node after testing
on CrewAI, LangGraph, and Claude Agent SDK, bounded by the same retry budget.

9.2 WHEN smoke fails, THE SYSTEM SHALL feed `{endpoint, status, traceback, logs}`
into the next development attempt. WHEN retries exhaust, THE SYSTEM SHALL
escalate (human or fatal), not mark the run complete.

9.3 The shared post-run quality gate SHALL remain as a backstop. It SHALL NOT be
the only CrewAI smoke path.

9.4 `CHK-runtime-smoke-present` SHALL fail a `status == complete` CrewAI run with
no `smoke_probe` span, matching LangGraph / SDK.

---

### R10 — Cost per accepted change

**User story:** As a harness owner, I want to know whether the extra checks pay
for themselves, so I can decide routing and retry budgets from a number, not a
feeling.

**Acceptance criteria**

10.1 THE SYSTEM SHALL compute `cost_per_accepted_change = total_usd / max(accepted_changes, 1)`
per run and per suite, and SHALL record it on the change receipt.

10.2 An accepted change SHALL require: required artifacts present, smoke
`success` or `ran=false` with a recorded skip reason, and no unresolved
`FM-001` / `FM-006` / `FM-012` check failures.

10.3 THE SYSTEM SHALL keep reporting total USD. `cost_per_accepted_change` is
additional, not a replacement.

---

### R11 — Three-file contract the harness owns

**User story:** As an operator, I want constraints, state, and lessons in files
the harness loads — not in a summary the model is free to drop — so turn 40 still
knows the turn-1 constraint.

**Acceptance criteria**

11.1 Every run workspace SHALL have, under `docs/` (or workspace root, see design):

| File | Who writes it | Compaction rule |
| --- | --- | --- |
| `CONSTRAINTS.md` | human + harness | never summarize away; always inject in full |
| `STATE.md` | harness after each phase | last N phases only; facts not prose |
| `LESSONS.md` | lessons loop | deduped, TTL, effectiveness score |

11.2 THE SYSTEM SHALL load `CONSTRAINTS.md` in full **before the first tool call**
of every phase, on every backend.

11.3 THE SYSTEM SHALL update `STATE.md` after each phase with structured facts
(phase name, files written, tests, smoke, errors). THE SYSTEM SHALL NOT ask the
LLM to be the only writer of `STATE.md`.

11.4 THE SYSTEM SHALL NOT use the LLM as the only compaction function. Pin
`CONSTRAINTS.md`, then summarize everything else.

11.5 Intake MAY append a distinctive constraint (for evals: a canary string) to
`CONSTRAINTS.md`. Human-authored constraints SHALL survive subsequent phases.

---

### R12 — Constraint survival check

**User story:** As an eval engineer, I want a deterministic check that a
turn-1 constraint is still in the prompt bundle at testing/deployment, so
compaction failures show up as `FM-011` rather than a migrated schema.

**Acceptance criteria**

12.1 THE SYSTEM SHALL implement `CHK-constraint-survival` (FM-011): inject or
read a distinctive constraint at intake; assert it is present in the prompt
bundle (or equivalent injected context) at testing and at deployment.

12.2 WHEN the constraint is absent at a later phase, THE CHECK SHALL fail with
the phase name and the missing constraint id.

12.3 THE CHECK SHALL be Tier A (no model spend) given a trace that records
injected context hashes or the constraint text in spans.

12.4 Traces SHALL record `context_inject` spans (or equivalent payload on
`phase_start`) listing constraint ids injected, so the check does not need live
LLM replay.

---

### R13 — Risk-class scaling of guardrails

**User story:** As a product owner, I want a smoke calculator and a
billing-service agent to share a catalog but not the same friction, so
`FM-005` false positives drop without weakening high-blast-radius checks.

**Acceptance criteria**

13.1 Team profiles and tools SHALL carry `risk_class`.

13.2 THE SYSTEM SHALL map existing guardrails onto risk classes. `low` SHALL run
a subset (path + secrets). `write` SHALL add quality/scope. `irreversible` and
`customer-visible` SHALL run the full chain plus the irreversible gate.

13.3 Default `smoke` / `prototype` profiles SHALL be `risk_class: write` unless
overridden. A profile that deploys customer-facing services SHALL set
`customer-visible`.

13.4 Guardrail-weight changes SHALL be argued from the existing guardrail
corpus (eval-harness R6), not from one batch.

---

### R14 — Guardrail evidence bundle

**User story:** As an auditor (or a future SOC2 conversation), I want one
artifact per run that lists policy version, checks fired, overrides, and
outcomes.

**Acceptance criteria**

14.1 Every run SHALL emit a guardrail evidence bundle (part of the change
receipt): `policy_version`, checks invoked, results, overrides, and the
ToolBus permission set.

14.2 THE SYSTEM SHALL derive this from events `TeamMonitor` and ToolBus already
emit. It SHALL NOT require a parallel logging system.

14.3 Human overrides SHALL be listed explicitly. Silent skip SHALL be a
harness bug.

---

### R15 — Change receipt

**User story:** As an operator, I want one receipt per run that cannot lie the
way a live event stream can (`FM-008`), so the dashboard opens a file, not a
websocket guess.

**Acceptance criteria**

15.1 At run end (including abort/kill), THE SYSTEM SHALL write
`output/runs/<id>/receipt.json` and `receipt.md` containing at minimum:

- context sources + policy version
- tool permission set
- model route per phase (and per task type when R18 exists)
- tests + smoke result
- reviewer / human overrides
- cost (`usd`, `cost_per_accepted_change`) and failure ids
- accepted output hash (workspace tree hash or git ref)
- rollback pointer (workspace snapshot / git ref)

15.2 THE SYSTEM SHALL promote the existing `output/runs/<id>/` bundle rather
than invent a second tree. `run.json` / `state.json` / `events.jsonl` remain;
the receipt is the normalized view.

15.3 Claude Agent SDK runs SHALL write the same receipt path (closing the
historical "SDK writes no output bundle" gap if it still exists on any path).

15.4 The web dashboard SHALL be able to open a receipt from disk. Live streams
MAY decorate; they SHALL NOT be the source of truth for cost, file count, or
smoke.

15.5 `CHK-metric-source-agreement` (FM-008) SHALL compare receipt fields to
artifact-derived values.

---

### R16 — Behavioral drift job

**User story:** As a maintainer, I want week-over-week drift on committed traces
so a silent provider update shows up before users do (`FM-009` cousin).

**Acceptance criteria**

16.1 THE SYSTEM SHALL provide `python -m evals.cli drift` (or equivalent) that
reads committed traces / receipts and reports distributions of: `FM-*` hits,
smoke pass rate, files written, cost, `cost_per_accepted_change`.

16.2 THE JOB SHALL compare the current window to the previous window (default
7 days or last N traces) and SHALL warn when a rate moves beyond a configured
tolerance.

16.3 THE JOB SHALL be runnable with no model API (`$0`). It MAY be a nightly
workflow later; v1 is a CLI + unit tests on fixtures.

---

### R17 — Task-typed routing table

**User story:** As a cost owner, I want lint and "did pytest pass" to hit a cheap
route, and architecture / salvage-after-smoke-fail to hit a strong route, so
routing lives in config, not in agent prose.

**Acceptance criteria**

17.1 THE SYSTEM SHALL define task types: `classify`, `format`, `mechanical_check`,
`plan`, `judge`, `generate`.

17.2 THE SYSTEM SHALL store a router table in config (YAML or `models.py`),
mapping `(task_type, env)` → model id (and optional backend hint). Agents SHALL
NOT choose models by mentioning names in prompts.

17.3 Same-model matrices (`full-claude`, `smoke-claude`) SHALL remain for
science. Production default profiles SHALL be heterogeneous on purpose.

17.4 Every LLM call SHALL log `task_type` + model id onto the receipt so cost
and quality attribute to the **route**, not the brand of backend.

17.5 v1 MAY implement the table and logging first, with mechanical_check +
plan + generate wired; remaining types MAY stub to generate with a warning.

---

### R18 — Closed lessons loop

**User story:** As a harness owner, I want a rejection, timeout, or budget
overshoot to write a constraint the next run loads automatically, so feedback
is a file, not a prompt tweak.

**Acceptance criteria**

18.1 WHEN smoke or an eval check fails, THE SYSTEM SHALL write a structured
lesson `{fm_id, constraint, evidence_span}` into the lessons store and
`LESSONS.md`.

18.2 THE SYSTEM SHALL dedup by `fm_id` + normalized constraint text.

18.3 THE SYSTEM SHALL inject active lessons into `CONSTRAINTS.md` and/or the
prompt prefix of the next run (pinned, not summarized).

18.4 THE SYSTEM SHALL record, for the next N runs (default 5), whether that
`fm_id` recurs. If it does not, mark the lesson `effective`. If it does,
mark `ineffective` and escalate (constraint too soft, or wrong layer).

18.5 `CHK-lesson-effectiveness` (FM-013) SHALL fail when a lesson is
`ineffective` beyond the configured recurrence budget without escalation.

18.6 Until 18.4 exists, THE SYSTEM SHALL NOT claim a "feedback layer" in
`docs/HARNESS.md` — it is a prompt tweak. The doc SHALL stay honest.

18.7 CrewAI SHALL participate in capture + inject even if its inner smoke
retry lands in R9. Lessons are harness-owned.

---

### R19 — Instrumentation completeness

**User story:** As a researcher comparing backends, I want every layer to emit
spans before I declare a winner, so I do not attribute harness gaps to
frameworks.

**Acceptance criteria**

19.1 Before a published cross-backend comparison that claims production
readiness, THE SYSTEM SHALL have spans or receipt fields for all seven layers
on all three backends.

19.2 A layer MAY be thin (e.g. routing table logged but not yet heterogeneous)
but SHALL NOT be absent.

19.3 `docs/HARNESS.md` SHALL mark each layer `instrumented` | `enforced` |
`closed-loop` so the demo bar and the production bar stay distinct.

---

### R20 — Tests, quality gates, and non-bypass

**User story:** As a maintainer, I want unit and adversarial tests for the bus,
draft-commit, constraint survival, and backend adapters, so a "helpful" direct
write cannot ship.

**Acceptance criteria**

20.1 New modules SHALL have type hints, Google-style docstrings, structlog (no
`print()`), Pydantic models, and SHALL pass ruff / mypy / black.

20.2 ToolBus SHALL have unit tests: happy path, schema fail, permission deny,
draft vs commit, irreversible gated, observation cap.

20.3 Adversarial tests SHALL include: path traversal, prompt-injection-shaped
args that try to reach shell, `confirm=true` on delete without policy, SDK
native Write bypass attempt.

20.4 Constraint survival SHALL have a fixture trace that drops the canary and
fails `CHK-constraint-survival`.

20.5 A meta-test SHALL fail if `write_file` / `delete_file` / `execute_shell`
public wrappers call the filesystem or subprocess without going through
`ToolBus.invoke` (or a documented bus-internal helper).

20.6 Checks live under `evals/checks/` with fail / pass / `not_applicable`
fixtures, registered against FM-011…013.

---

## Traceability

| Requirement | Primary artifacts |
| --- | --- |
| R1, R4–R7 | `src/ai_team/tools/bus.py` (ToolBus), adapters, SDK hooks |
| R2, R12, R20.6 | `evals/taxonomy/failure_modes.yaml`, `evals/checks/` |
| R3, R19 | `docs/HARNESS.md`, links from `ARCHITECTURE.md` |
| R8, R9, R10 | `smoke_tools.py`, CrewAI flow node, receipt cost fields |
| R11, R12 | workspace `CONSTRAINTS.md` / `STATE.md` / `LESSONS.md`, context injector |
| R13, R14 | `GuardrailSettings` / profiles, evidence bundle |
| R15, R16 | `output/runs/<id>/receipt.json`, `evals` drift CLI |
| R17 | router table in config |
| R18 | `src/ai_team/memory/lessons.py`, effectiveness tracking |
| R20 | `tests/unit/tools/`, `tests/unit/evals/`, adversarial tests |
