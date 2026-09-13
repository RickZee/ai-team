# Design — Harness Alignment

**Spec ID:** `harness-alignment`
**Requirements:** [`requirements.md`](./requirements.md)
**Tasks:** [`tasks.md`](./tasks.md)

---

## 1. Overview

### 1.1 The central architectural move

`eval-harness` separated **execution** from **scoring** at the `Trace` boundary. This
spec adds a second axis to the left of that boundary: **what produced the Trace.**

```
   ARMS (billed, Tier C)                    TRACE            SCORING (free, Tier A)
   ────────────────────────                 ─────            ──────────────────────
   solo            ──┐
   reference       ──┤
   ai_team         ──┼──►  evals/traces/*.json  ──►  checks FM-001…FM-016
   ai_team−smoke   ──┤                              ladder aggregation
   ai_team−lessons ──┘                              gate / report
```

The existing `--backend` axis swaps the *framework* while holding the harness constant.
The new `--arm` axis swaps the *harness* while holding framework and model constant.
They are orthogonal, and the second is the one the project's thesis actually rests on.

A single rule keeps this cheap: **an arm is an adapter, never a `Backend`.** Arms produce
workspaces; `evals.trace.from_workspace()` does the rest. No check, judge, gate, or report
component learns that arms exist beyond one new grouping key.

### 1.2 Design principles

1. **Adapters, not integrations.** The reference harness is vendored and pinned, never
   edited, never registered in `src/ai_team/backends/registry.py`. If it drifts upstream,
   the pin is the answer.
2. **The harness owns the definition of done.** `ACCEPTANCE.json` is written by harness
   code and denied to agents at the hook layer. An agent that can edit the bar is an agent
   that will.
3. **Reset, don't compact.** Sessions start clean and re-derive from four files. This
   matches what `harness/context.py` was already built for; R8 is the loop that was
   missing around it, not a new state mechanism.
4. **Every new detector is deterministic.** All three new failure modes are checkable from
   a Trace with no model call, which is what keeps them in the $0 Tier A gate.
5. **Components must earn their place.** Anything R4 can ablate is a hypothesis. That
   includes the components this spec adds — contract negotiation and the bash allowlist
   are ablatable from day one (R11.6, R14.6).
6. **The tooling enforces the caveats.** R5 puts `UNDERPOWERED` and `MIXED-MODEL` stamps in
   code because a caveat that lives in prose is a caveat that gets dropped from the slide.
7. **Every component encodes an assumption about what the model cannot do alone, and
   assumptions expire.** So an ablation result is scoped to the model it was measured on
   (R15), and a component whose evidence predates the current default model is reported
   `STALE` rather than quietly carried forward. The failure this guards against is not a
   bug — it is a harness that keeps charging for a crutch the model outgrew.

### 1.3 What this deliberately does not change

`src/ai_team/backends/*` gains nothing except the hook changes in R14 and the acceptance
write-deny in R6.3. `evals/checks/*` gains three modules and one extension. The Trace
schema gains two optional fields (`context_pressure`, `arm_id`). Everything else is new
surface under `evals/arms/` and `src/ai_team/harness/`.

---

## 2. The ladder

### 2.1 Arm families

| Arm id | Family | What it holds constant | What it removes |
| --- | --- | --- | --- |
| `solo` | `solo` | model, scenario, workspace layout | everything: roles, guardrails, smoke, lessons, constraints, sessions |
| `reference` | `reference` | model, scenario | `ai-team`'s harness entirely; substitutes the quickstart's |
| `harnessed_solo` | `ai_team` | model, scenario, seed, **the whole harness** | only the nine-role decomposition |
| `ai_team` | `ai_team` | — | nothing (control for ablations) |
| `ai_team_ablated:<component>` | `ai_team` | model, scenario, seed, all other components | exactly one named component |

`solo` and `reference` are *external* reference points; the ablation arms are *internal*
attribution. Both are needed: external tells you the harness is worth having, internal
tells you which parts.

`harnessed_solo` is the rung that makes the ladder answer two questions instead of one.
Without it, `solo → ai_team` confounds **harness** with **decomposition**: nine roles and
every guardrail arrive together, so a win cannot be attributed to either. With it:

| Comparison | Isolates |
| --- | --- |
| `solo` → `harnessed_solo` | what the harness buys, holding agent count at one |
| `harnessed_solo` → `ai_team` | what role decomposition buys, holding the harness fixed |

This is not a hypothetical concern. The reference article removed its sprint-decomposition
construct outright at the next model version, on the finding that the generator "ran
coherently for over two hours without the sprint decomposition." A nine-agent team is the
single most expensive assumption `ai-team` makes, and it is currently the only one the
project never tests. `harnessed_solo` is implemented as `ai_team_ablated:role_decomposition`
and given its own id because it is a headline rung, not a footnote.

### 2.2 Arm interface

```python
# evals/arms/base.py
class ArmSpec(BaseModel):
    arm_id: str
    family: Literal["solo", "reference", "ai_team"]
    model_ids: dict[str, str]              # role -> model id; {"*": id} for single-agent
    harness_components: frozenset[str]     # active component names (R4.1 vocabulary)
    source_ref: str                        # git sha, or "vendor:<pin>" for third-party
    cost_controls: CostControls            # spend_ceiling_usd, wall_clock_ceiling_s, max_sessions
    divergences: list[Divergence]          # forced differences, each with a reason

class ArmRun(BaseModel):
    arm_id: str
    sweep_id: str
    workspace: Path
    status: Literal["ok", "failed", "budget_exhausted", "unavailable"]
    started_at: datetime
    ended_at: datetime
    cost_usd: float
    trace_id: str | None

class Arm(Protocol):
    arm_id: str
    def describe(self) -> ArmSpec: ...
    def run(self, scenario: ScenarioContract, workspace: Path, budget_usd: float) -> ArmRun: ...
```

`Divergence` is `{field, expected, actual, reason}`. It is the honesty mechanism: every
place an arm could not be held equal is written down and surfaced in the report (R5.4).

### 2.3 Sweep execution

`python -m evals.cli ladder run --scenario todo-api-beginner --arms solo,reference,ai_team --n 3`

1. Resolve arms from the registry; fail fast on unknown ids.
2. Allocate a `sweep_id`; compute the shared workspace seed.
3. Run arms **sequentially** (not in parallel) — concurrent launches are FM-004
   `run_id_collision` and the point is not to reproduce it accidentally.
4. After each arm, assemble its Trace immediately and free the workspace to the corpus.
5. Write `evals/results/ladder/<sweep_id>/manifest.json` and per-arm `ArmRun` records.
6. Score offline: the ladder report is produced from Traces, so it can be re-rendered for
   free after any check change.

Default is `--dry-run`, which resolves and prints the plan and the projected cost without
spending.

### 2.4 Cost envelope

| Arm | Ceiling | Rationale |
| --- | --- | --- |
| `solo` | $3.00 / 30 min | Article's reference point was $9 at 20 min on a larger brief; beginner scenarios are smaller |
| `reference` | $8.00 / 90 min | Feature cap 25 (R3.3); the session loop is the expensive part |
| `ai_team` | $6.00 / 60 min | Current full-run cost plus headroom |
| each ablation | $6.00 / 60 min | Same as control |

A full three-arm sweep at n=1 is ≈ $17; the R1 sweep ceiling is **$25.00** and is checked
before any arm starts, not after. This is entirely separate from the eval-harness $5 suite
budget: scoring stays $0 and Tier A is untouched.

---

## 3. Data models

### 3.1 Acceptance list

```python
# src/ai_team/harness/acceptance.py
class AcceptanceItem(BaseModel):
    id: str                                  # sha256(description + steps)[:12], stable
    category: Literal["functional", "style", "security", "performance"]
    description: str
    steps: list[str]
    priority: int                            # lower is higher priority; assigned at plan time
    passes: bool = False
    verified_by: Literal["smoke", "ui_smoke", "test", "qa_agent"] | None = None
    verified_at: datetime | None = None
    verifier_identity: VerifierIdentity | None = None   # R12.2
    evidence: list[str] = []                 # workspace-relative artifact paths
    demotions: list[Demotion] = []

class AcceptanceList(BaseModel):
    schema_version: int = 1
    run_id: str
    created_at: datetime
    source: Literal["planning"] = "planning"
    items: list[AcceptanceItem]
```

`id` is content-hashed so that a mutated description produces a *different* id — which is
precisely what makes `CHK-acceptance-monotonic` a set-difference rather than a diff
heuristic.

### 3.2 Session record

```python
class SessionRecord(BaseModel):
    session_id: str
    index: int
    started_at: datetime
    ended_at: datetime
    status: Literal["ok", "dirty_exit", "error", "budget_exhausted"]
    items_attempted: list[str]
    items_passed: list[str]
    items_demoted: list[str]
    cost_usd: float
    context_pressure_at_end: float | None
    termination_reason: str
```

Written to `logs/sessions.jsonl`, which becomes a new span source in Trace assembly
(`session_start`, `session_end`, `regression_check`).

### 3.3 Build contract

```python
class BuildContract(BaseModel):
    item_id: str
    round: int
    approach: str
    testable_behaviors: list[str]
    files_to_touch: list[str]
    out_of_scope: list[str]
    review: ContractReview | None = None     # {verdict, reasons[], reviewed_at, reviewer}
```

At `docs/contracts/<item_id>.json`. File-based handoff, per `CLAUDE.md`.

### 3.4 Trace additions

Two optional fields, both nullable so every existing fixture stays valid:

- `Trace.arm_id: str | None` — grouping key for the ladder report.
- span `payload.context_pressure: float | None` on `phase_end` and `session_end`.

Schema version bumps; the loader tolerates absence (eval-harness R1.6 already requires
graceful degradation).

---

## 4. Components

### 4.1 `evals/arms/`

```
evals/arms/
├── base.py          Arm protocol, ArmSpec, ArmRun, Divergence, CostControls
├── registry.py      id -> factory, duplicate-registration guard
├── solo.py          SoloArm (R2)
├── reference.py     ReferenceArm wrapping the vendored harness (R3)
├── ai_team.py       AiTeamArm + AblatedArm factory (R4)
├── ladder.py        sweep orchestration, manifest, budget pre-check
└── vendor/
    └── autonomous_coding/   pinned MIT copy + PROVENANCE.md
```

**SoloArm** constructs a single `ClaudeSDKClient` with one system prompt, the scenario
brief, and the standard workspace scaffold pre-created so Trace assembly is uniform. It
reuses the existing cost and audit hooks — the arm is unharnessed with respect to
*behavioral* components, not with respect to *observability*. Measuring it requires
logging it.

**ReferenceArm** shells the vendored `autonomous_agent_demo.py` with
`--project-dir <workspace> --max-iterations N --model <id>`, captures stdout, and parses
the demo's `[Tool: …]` / `[Done]` / `[BLOCKED]` markers into `tool_use` / `tool_result`
spans. Coverage is partial by construction: the reference harness emits no cost stream, so
cost comes from the SDK's own usage accounting at the adapter layer, and `trace.warnings[]`
records every stream it cannot supply (R3.5). Ceilings are enforced by the adapter
(wall-clock kill + iteration cap), and the *absence* of internal ceilings is reported as an
expected FM-007 positive rather than patched (R3.4).

**AblatedArm** is `AiTeamArm` with a component set subtracted. Ablation is config, so the
implementation is a settings override object threaded into run construction — never a
code path fork (R4.2).

### 4.2 `src/ai_team/harness/acceptance.py`

Sole writer of `ACCEPTANCE.json`.

```python
def write_initial(workspace: Path, requirements: RequirementsDoc, run_id: str) -> AcceptanceList
def load(workspace: Path) -> AcceptanceList
def mark_passing(workspace: Path, item_id: str, *, evidence: list[str],
                 verified_by: str, identity: VerifierIdentity) -> AcceptanceList
def demote(workspace: Path, item_id: str, *, session_id: str, reason: str) -> AcceptanceList
def status(workspace: Path) -> AcceptanceStatus       # counts + next unsatisfied item
```

`mark_passing` validates that every evidence path exists in the workspace before writing
(R6.4). Writes are atomic (temp file + `os.replace`) and append a snapshot hash to
`logs/acceptance.jsonl`, which is what gives the monotonic check a first-and-last state
to compare without needing git.

Enforcement is two-layer: the PreToolUse hook denies `Write`/`Edit` on the path, and
`mark_passing` is exposed to agents only through the MCP tool surface.

### 4.3 `src/ai_team/harness/session_loop.py`

```python
def run_sessions(workspace, *, backend, max_sessions, total_budget_usd,
                 no_progress_sessions=2, regression_k=2) -> list[SessionRecord]
```

Per session: build fresh context from the four files → run regression check (R9) → select
target item → negotiate contract (R11, if enabled) → implement → verify → `mark_passing`
→ commit → write `SessionRecord`.

Termination is checked *before* constructing the next session, and every exit path writes a
record. A session that ends with uncommitted changes is `dirty_exit` and feeds FM-012.

The loop does not summarize. The next session's context is `CONSTRAINTS.md` + `STATE.md`
(last-N phase facts) + `LESSONS.md` + `ACCEPTANCE.json` + `git log` — all already produced
by `harness/context.py` and the receipt writer.

### 4.4 `src/ai_team/harness/contracts.py`

Reads and writes `docs/contracts/<item_id>.json`, enforces the round ceiling (R11.3), and
exposes `require_accepted(item_id) -> bool` to the PreToolUse hook so writes to `src/` can
be denied for un-contracted items (R11.4). When the component is ablated, the hook check
is a no-op and the negotiation step is skipped entirely.

### 4.5 `src/ai_team/tools/ui_smoke_tools.py`

Mirrors `smoke_tools.py`'s shape deliberately — same result-file contract, same
"never probe a foreign service" rule, same `load_or_run` caching by age.

```python
class UiStepResult(BaseModel):
    action: str; selector: str | None; outcome: Literal["pass","fail","skipped"]
    console_errors: list[str]; page_errors: list[str]
    screenshot_path: str | None; duration_ms: int

class UiSmokeResult(BaseModel):
    status: Literal["pass","fail","skipped"]; steps: list[UiStepResult]
    started_at: datetime; duration_s: float; base_url: str | None; skip_reason: str | None
```

Playwright, headless, Chromium, fixed viewport for screenshot comparability. Steps come
from the acceptance item's `steps[]` where they are machine-interpretable, and from the
scenario's `ui` block otherwise. Console and page errors fail the step deterministically —
no judge involved (R13.3).

Scenario contracts gain an optional `ui` block (`base_url`, `boot_cmd`, `ready_path`,
`viewport`); its absence means `skipped`, never `pass` (R13.6).

### 4.5a QA verdict store

`docs/qa_verdicts.jsonl`, one record per item per QA pass:

```python
class QaVerdict(BaseModel):
    item_id: str
    verdict: Literal["accept", "reject"]
    issues: list[QaIssue]            # {description, severity, evidence[]}
    evidence: list[str]
    qa_prompt_hash: str              # R16.6 — attribute rate changes to the prompt
    identity: VerifierIdentity
    emitted_at: datetime
```

Structured output rather than prose is what makes FM-017 checkable at all: the check needs
to see that the evaluator *recorded* a blocker and then *accepted anyway*. Parsing that
intent out of free text would be a judge; reading it out of a field is a comparison.

The false-negative rate (R16.4) needs no labels: every item the QA agent accepted and a
deterministic verifier later failed is a counted miss. The deterministic verifier is the
ground truth, which is the cheapest ground truth this project has access to.

### 4.6 Checks

| Check | Module | FM | Evidence |
| --- | --- | --- | --- |
| `CHK-acceptance-monotonic` | `evals/checks/acceptance.py` | FM-014 | `logs/acceptance.jsonl` first/last snapshots + artifact inventory |
| `CHK-premature-termination` | `evals/checks/context.py` (extend) | FM-015 | `phase_end` / `session_end` spans, trailing span window, acceptance state |
| `CHK-verifier-independence` | `evals/checks/verification.py` (extend) | FM-016 | `verifier_identity` on passes transitions, write spans per item |
| `CHK-evaluator-capitulation` | `evals/checks/verification.py` (extend) | FM-017 | `docs/qa_verdicts.jsonl` verdicts vs their own `issues[]`, remediation spans between |
| `CHK-runtime-smoke-present` | `evals/checks/verification.py` | FM-006 | extended to require UI smoke for UI-bearing scenarios |

All four are pure functions over a Trace, registered through the existing
`evals/checks/registry.py`, and carry fail/pass fixtures under `evals/fixtures/traces/`.

### 4.7 Reporting

`evals/report.py` gains `render_ladder(traces, *, allow_mixed_model, allow_underpowered)`:

- Groups by `arm_id`; computes per-arm `n`, mean and CI for cost and wall-clock, FM
  incidence per mode, smoke pass rate, accepted-change rate, demotion rate.
- Emits JSON first, renders Markdown *from that JSON* — never computes twice (FM-008).
- Applies the stamps of R5.2 / R5.3 before any table is rendered, and refuses outright
  without the corresponding flag.
- Ablation deltas are rendered against the `ai_team` control with CIs, and components with
  no measured effect get their own named section (R4.5).
- **Per-phase cost and wall-clock** per arm, from `logs/costs.jsonl` (R5.1a), so a
  component's price sits beside what it buys. The optional `cost_per_fm_avoided` is a ratio
  of two noisy estimates and is stamped and suppressed accordingly (R5.1b).
- **Staleness** (R15): every ablation row carries the model it was measured on, and is
  marked `STALE` when that differs from the configured default. `never measured` renders as
  its own state, never as a zero delta.
- **`qa_false_negative_rate`** per arm (R16.4), computed for free against the deterministic
  verifiers, beside `smoke_pass_rate` — because an arm can buy a pass rate by lowering its
  evaluator, and the table should make that visible rather than reward it.

---

## 5. Sequencing

The phases are ordered so that the cheapest, highest-signal work lands first and nothing
expensive runs before the free scoring path can consume it.

```
Phase 1  acceptance list + FM-014            free, no arms, immediately useful
Phase 2  FM-015/016/017 checks               free, retroactive over existing corpus
Phase 3  arms scaffold + ai_team arm         no new spend (wraps existing runs)
Phase 4  solo + harnessed_solo arms          first spend; the two-question ladder
Phase 5  reference arm                       vendoring + adapter
Phase 6  ladder report + claim discipline    free; makes phases 4–5 publishable
Phase 7  UI smoke + FM-006 extension         medium cost, unlocks style criteria
Phase 8  session loop + regression check     largest change; consumes phases 1–2
Phase 9  contract negotiation                hypothesis; ablatable from the start
Phase 10 bash allowlist                      last, behind the FP budget
Phase 11 ablation sweep + writeup            the payoff
```

Phases 1–2 are strictly additive and can land before any decision about arms is made.
Phases 8–9 are the only ones that change agent behavior in a normal run, and both are off
by default.

---

## 6. Error handling

| Failure | Behavior |
| --- | --- |
| Arm exceeds ceiling | Terminate, `status = "budget_exhausted"`, Trace still emitted (R1.5) |
| Vendored harness unavailable | `status = "unavailable"`, sweep continues, report shows the arm as absent — never substituted (R3.6) |
| `ACCEPTANCE.json` corrupt or missing mid-run | Session aborts with `error`; the loop does not regenerate it (R8.4), because regeneration is indistinguishable from goalpost-moving |
| Evidence path missing on `mark_passing` | Reject the write, return an error to the agent, log a `guardrail_check` span |
| Contract rounds exhausted | Escalate through the existing `flows/error_handling.py` path; never loop (R11.3, FM-002) |
| Playwright unavailable or browser launch fails | `UiSmokeResult.status = "skipped"` with `skip_reason`; FM-006 check treats skip as unsatisfied for UI scenarios, so it fails loudly rather than passing quietly |
| Token usage unavailable for `context_pressure` | Field is `None`; `CHK-premature-termination` returns `inconclusive`, not `pass` |
| Bash parse failure | Block (R14.3) |

The recurring rule: **absence of evidence is never recorded as evidence of success.** Skips,
inconclusives, and unavailables are distinct outcomes from passes, and the aggregation
keeps them out of pass-rate numerators *and* denominators.

---

## 7. Testing strategy

**Unit** (`tests/unit/harness/`, `tests/unit/evals/arms/`)

- `acceptance.py`: monotonic enforcement, atomic write, evidence validation, demotion
  records, content-hash stability across whitespace changes.
- Bash allowlist parser: the full adversarial list of R14.4, one test per construct, each
  asserting *block* for anything undecomposable.
- `ArmSpec` / `Divergence` round-trips; registry duplicate guard.
- Ladder report: stamp application, refusal without flags, Markdown-rendered-from-JSON
  identity.

**Check tests** (`tests/unit/evals/checks/`)

- Each new check: the fail fixture fails, the pass fixture passes, a trace missing the
  required span type returns `inconclusive`.
- `CHK-premature-termination` negative controls: spend event present, watchdog kill,
  `max_turns` exhaustion — each must *not* fire (R10.4).

**Integration** (`tests/integration/`)

- Session loop over a stubbed backend: three sessions, one injected regression, assert
  demotion → prioritization → re-pass, and assert `sessions.jsonl` shape.
- Contract negotiation with a stubbed QA returning `rejected` twice, asserting escalation
  at round 3 rather than a fourth round.
- UI smoke against a fixture static app with a deliberate console error, asserting step
  failure without any model call.

**Suite-level guards** (`tests/conftest.py`, `tests/unit/evals/test_suite_drift_guards.py`)

- Tracked ground truth (`evals/golden/`, `evals/fixtures/traces/`, `evals/taxonomy/`) is
  hashed at session start and asserted unchanged at teardown (R17.1). This is not
  belt-and-braces: it caught a live defect the day it was written.
- `ALL_CHECK_IDS` ≡ registry, no duplicates, fixtures present for every check, no check
  pointing at an unknown failure mode, no implemented mode left `reserved` (R17.2, R17.3).
- The four checks this spec adds are covered by those guards automatically — which is the
  point of writing them before Phase 2 rather than after.

**Cover before extend.** Tasks 1.4, 1.5, 7.3, 9.3 and 10.2 attach to modules whose deny
paths are largely untested (`mcp_server.py` at 0% branch being the worst). Each of those
tasks carries the existing module's tests as part of its definition of done (R17.5), and
every new refusal path reaches 100% branch coverage before its component is enabled by
default (R17.6). `hooks/security.py` — 100%/100% as of 2026-09-12 — is the reference.

**Never in pytest:** live arms, live model calls, live judge quality assertions. Arm runs
are Tier C, human-triggered, and budgeted.

---

## 8. Claim discipline

What this spec licenses the project to say, once the ladder has n ≥ 3 per arm at a fixed
model:

- "Removing `<component>` changed FM-`<id>` incidence by X ± CI at n=N on scenario S."
- "A solo agent on the same brief and model produced W at cost C; the full harness
  produced W' at cost C'."
- "The published reference harness exhibits FM-007 and FM-006 on this scenario; here are
  the traces."

What it still does not license:

- "Framework X beats framework Y." Unchanged, and out of scope.
- "This harness generalizes." One scenario family, one model, one author.
- Any design-quality claim from the R13.7 rubric until it clears the alignment bar.

The `UNDERPOWERED` / `MIXED-MODEL` stamps exist so that a table lifted out of context
carries its own caveat. That is the whole point of putting them in the renderer rather
than the README.

### 8.1 Effect on claims already published

Three of this spec's four new modes are `layer: model`. The taxonomy essay's central
statistic — "only one of the ten was caused by an LLM being dumb" — becomes four of
seventeen, and that sentence is load-bearing for the project's whole "it was systems
engineering, not the model" framing. Two honest readings, and the second is the right one:

1. The thesis weakened. More failures turned out to be the model's after all.
2. The instruments improved. FM-014, FM-015 and FM-017 describe failures that were always
   occurring and were previously undetectable — goalposts moved without a diff to catch it,
   sessions wrapped up early with no measure of context pressure, evaluators waived their
   own findings in prose nobody parsed. The denominator grew because detection grew.

Reading 2 is supportable and reading 1 is not, because the new modes were found by building
detectors, not by observing a regression. But the essay has to say so explicitly, and the
ratio has to be computed from the YAML rather than typed, or the next three modes will
silently falsify it again (task 11.5).

---

## 9. Open decisions

1. **Scenario for the first ladder sweep.** `todo-api-beginner` is cheapest and has a UI
   story; `architecture-planning-intermediate` better exercises the contract mechanism but
   has no runnable artifact. Recommendation: `todo-api-beginner` first.
2. **Whether `reference` counts toward FM incidence rates in the headline table** or is
   reported in a separate external-reference block. Recommendation: separate block — it is
   a different harness, not a variant of yours.
3. **Whether `context_pressure` can be sourced reliably per-phase** from the SDK across all
   three backends, or only from the Claude Agent SDK backend. If only the latter, FM-015
   is scoped to that backend in v1 and the check returns `inconclusive` elsewhere.
4. **Brief fidelity.** The reference article's planner expands a 1–4 sentence brief, and
   deliberately withholds granular technical detail so that a wrong guess cannot cascade
   downstream. `ai-team`'s scenario contracts are structured and detailed, so the thin-brief
   path — the one most real users take — is never exercised, and the planner's
   over-specification risk is never measured. Options: (a) leave it, recording detailed
   contracts as a known limitation in every arm's divergence list; (b) add a `thin` variant
   per scenario carrying only the brief, as a second sweep dimension. Recommendation: (a)
   for v1, (b) once the ladder has produced its first result — it doubles sweep cost and the
   ladder should prove itself first.
5. **Whether `harnessed_solo` or the `smoke_gate` ablation is the better second live arm**
   if budget allows only one beyond `solo`. `harnessed_solo` answers the bigger question
   (is the nine-role team earning its cost?) and is the more uncomfortable one to ask, which
   is usually the sign it should be asked first.
