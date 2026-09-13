# Requirements — Harness Alignment

**Spec ID:** `harness-alignment`
**Status:** Draft for implementation
**Owner:** Rick Zakharov
**Target repo:** `ai-team` (extends `evals/` and `src/ai_team/harness/`)
**Created:** 2026-09-12
**Depends on:** [`../eval-harness/`](../eval-harness/) — Trace boundary (R1), check registry
(R4), taxonomy (R5), tiers and budget (R11), provenance (R14). This spec adds arms,
ablation, three failure modes, and four harness components. It does not restate those.

---

## Introduction

`ai-team` compares three orchestration backends behind one `Backend` protocol and
scores them through a Trace boundary against a thirteen-mode failure taxonomy
(FM-001…FM-013). The README already concedes the central weakness: with n=5 and mixed
models, the published tables "cannot yet support framework X beats Y."

That weakness is not fixable by running more samples. It is a **missing-arm** problem.
The project measures three points that differ in framework *and* in nothing else it
controls, and has no point of reference outside itself. Two external sources published
by Anthropic supply exactly the reference points that are missing:

1. **`anthropics/claude-quickstarts/autonomous-coding`** (MIT, @3313e97) — a 2,300-line
   minimal harness: two-agent loop (initializer + coding agent), one fresh context window
   per session, all state on disk (`feature_list.json`, `claude-progress.txt`, git), a
   default-deny bash allowlist, and browser-based verification. It has no spend guard, no
   subprocess isolation, and no runtime gate. It is the *unhardened control* for the
   harness layer.
2. **"Harness Design for Long-Running Application Development"** (Rajasekaran, Anthropic
   Engineering) — a generator/evaluator architecture reporting a solo-agent control arm
   (20 min, $9, core feature broken) against a full harness (6 h, $200, working), plus
   three mechanisms `ai-team` does not have: **contract negotiation before
   implementation**, **context resets with structured handoff instead of compaction**, and
   the observation that models exhibit **"context anxiety"** — premature wrap-up as the
   window fills.

Aligning with these yields a **ladder** rather than a leaderboard:

```
  solo agent  →  reference harness  →  ai-team (ablated)  →  ai-team (full)
  no harness     minimal harness       component removed      all components
```

Every rung runs the same scenario contract, emits the same `Trace`, and is scored by the
same deterministic checks. That is a claim the current n=5 matrix cannot make and this
one can: **not "which framework is better" but "what does each harness component buy,
and at what cost."** It answers the question the README actually asks — which failures
are the framework's, which the model's, and which are mine.

### What this spec adds

| Area | Gap today | Requirement |
| --- | --- | --- |
| Comparison arms | Only three same-shape backends | R1, R2, R3 |
| Component attribution | No way to isolate a component's contribution | R4 |
| Claim discipline | Prose caveats, not enforced | R5 |
| Durable acceptance criteria | Run-scoped objects in `models/requirements.py`; nothing survives a session | R6 |
| Goalpost-moving detection | FM-011 covers constraint drop, not criteria mutation | R7 (FM-014) |
| Multi-session builds | One pipeline pass per run; no resume | R8, R9 |
| Premature termination | Not in the taxonomy; `token_tracker` counts cost, not pressure | R10 (FM-015) |
| Contract before code | Criteria flow one way from planning; QA never validates the plan | R11 |
| Self-graded verification | Agent identities are separate by construction but nothing asserts it | R12 (FM-016) |
| UI-level verification | `run_app_smoke` proves HTTP 200; FM-006 is `runtime_verification_gap` by name | R13 |
| Bash confinement | Denylist of patterns; parse failure is not fail-safe | R14 |
| Component staleness | Nothing records which model a component's value was measured against | R15 |
| Role decomposition | Nine roles vs one agent is never measured — `solo` also removes the harness | R2, R4.1 |
| In-run QA quality | Judge alignment is offline; the agent that gates a build is unmeasured | R16 (FM-017) |
| Test-suite trust | Two isolation defects and an unguarded parametrize list, all green | R17 |

### Design constraints (decided)

| Constraint | Decision |
| --- | --- |
| Location | Extends `evals/` and `src/ai_team/harness/` in-repo. No new repo, no fourth first-class backend. |
| Reference harness | Adapter over a **pinned, vendored** copy. Never edited to make it look worse; never promoted to a `Backend` implementation. |
| Tier discipline | Every new check is deterministic and runs in **Tier A at $0.00**. Arms and ablation runs are Tier C only. |
| Arm budget | ≤ **$25.00** per full ladder sweep (one scenario × four rungs), separate from and additive to the eval-harness $5 suite budget. Default `--dry-run`. |
| Backwards compatibility | `run_evals.py --compare`, the three `evals/backends/test_*_eval.py` files, and existing FM-001…013 checks must keep working unchanged. |
| Claims | No arm comparison may be published without n, a cost column, and the model id per arm. Enforced in code (R5), not in prose. |

### Non-goals

- Ranking CrewAI vs LangGraph vs Claude Agent SDK. Out of scope here as it is there.
- Vendoring the quickstart's 200-feature initializer prompt, its unbounded iteration
  loop (`max_turns=1000`, no ceiling), or its `.claude_settings.json` generation as the
  primary permission mechanism. The first is pure spend; the second is a live specimen of
  FM-007 and is *kept* as such, not adopted.
- A design-quality LLM judge that gates a build. R13 defines the rubric and the artifacts;
  gating stays behind the eval-harness alignment bar (TPR ≥ 0.90 / TNR ≥ 0.90) and is not
  claimed by this spec.
- Replacing `harness/context.py`. `CONSTRAINTS.md` / `STATE.md` / `LESSONS.md` is already
  the structured-handoff mechanism the article argues for; R8 consumes it, it does not
  replace it.
- Multi-annotator labeling, online evaluation, fine-tuning. As in `eval-harness`.

### Glossary

| Term | Definition |
| --- | --- |
| **Arm** | One configuration under comparison that is *not* a backend swap: `solo`, `reference`, `ai_team`, or `ai_team_ablated:<component>`. |
| **Ladder** | The ordered set of arms for one scenario, run under one sweep id. |
| **Ablation** | An `ai_team` run with one named harness component disabled by config, holding model, scenario, and seed fixed. |
| **Acceptance list** | `ACCEPTANCE.json` in the run workspace: the durable, monotonic checklist of acceptance criteria. |
| **Monotonic** | Items may be added by the harness at plan time and thereafter only the `passes` field may change, and only `false → true`, except for harness-issued demotions (R9). |
| **Session** | One fresh-context execution over a workspace. A run may span many sessions. |
| **Build contract** | A file-based agreement between developer and QA on what "done" means for one acceptance item, written before implementation begins. |
| **Context pressure** | Fraction of the usable context window consumed at the moment a phase or session ends. |
| **Harnessed solo** | The full `ai-team` harness driving a single generalist agent instead of nine roles — the rung that separates *harness* from *decomposition*. Equivalent to `ai_team_ablated:role_decomposition`. |
| **Stale ablation** | A component whose most recent measured delta was taken against a model that is no longer the configured default. |

---

## Requirements

### R1 — Arm abstraction and registry

**User story:** As an eval engineer, I want every rung of the ladder to be addressable
through one interface, so that a solo agent, a third-party harness, and `ai-team` can be
scored by exactly the same checks.

**Acceptance criteria**

1.1 THE SYSTEM SHALL define `evals/arms/base.py::Arm`, a protocol with
`arm_id: str`, `describe() -> ArmSpec`, and
`run(scenario: ScenarioContract, workspace: Path, budget_usd: float) -> ArmRun`.

1.2 THE SYSTEM SHALL implement arms as adapters that terminate at the existing Trace
boundary: every `Arm.run` SHALL produce a workspace from which
`evals.trace.from_workspace()` yields a valid `Trace`, and SHALL NOT require changes to
`evals/checks/*`.

1.3 An `ArmSpec` SHALL record `arm_id`, `family` (`solo` | `reference` | `ai_team`),
`model_ids` (per role, or one entry for single-agent arms), `harness_components` (the
set of components active), `source_ref` (git sha or vendored pin for third-party code),
and `cost_controls` (`spend_ceiling_usd`, `wall_clock_ceiling_s`, `max_sessions`).

1.4 THE SYSTEM SHALL register arms in `evals/arms/registry.py` by string id and SHALL
raise on duplicate registration, mirroring `evals/checks/registry.py`.

1.5 WHERE an arm exceeds `spend_ceiling_usd` or `wall_clock_ceiling_s`, THE SYSTEM SHALL
terminate it, mark `ArmRun.status = "budget_exhausted"`, and still emit a Trace.

1.6 THE SYSTEM SHALL hold model id, scenario contract, and workspace seed fixed across
all arms in one sweep, and SHALL record any forced divergence in
`ArmRun.divergences[]` with a reason string.

---

### R2 — Solo-agent control arm

**User story:** As an engineer defending the claim that the harness is the deliverable, I
want a no-harness control, so that "the harness bought us X" is a measurement rather than
an assertion.

**Acceptance criteria**

2.1 THE SYSTEM SHALL provide `evals/arms/solo.py::SoloArm`: one Claude Agent SDK session,
one general-purpose system prompt, the scenario brief as its only input, no role
decomposition, no guardrails, no smoke gate, no lessons, no constraint pinning.

2.2 THE SOLO ARM SHALL write the same workspace layout the rest of the repo assumes
(`docs/`, `src/`, `tests/`, `logs/`) so that Trace assembly needs no special case.

2.3 THE SOLO ARM SHALL be subject to `spend_ceiling_usd` and `wall_clock_ceiling_s` from
its `ArmSpec` and SHALL default to `$3.00` and `1800` seconds.

2.4 THE SYSTEM SHALL run the identical FM-001…FM-016 check set over the solo arm's Trace
and SHALL NOT suppress or special-case any check for it.

2.5 THE SYSTEM SHALL record, for the solo arm, the same receipt fields as an `ai_team`
run (`cost_usd`, `wall_clock_s`, `accepted_change`, `workspace_tree_hash`) via
`src/ai_team/harness/receipt.py`.

---

### R3 — Reference-harness arm

**User story:** As an engineer, I want Anthropic's own minimal autonomous-coding harness
scored by my taxonomy, so that my claims about the harness layer are tested against a
published reference rather than only against my own earlier code.

**Acceptance criteria**

3.1 THE SYSTEM SHALL vendor the reference harness under
`evals/arms/vendor/autonomous_coding/` with `PROVENANCE.md` recording upstream URL,
commit sha, licence (MIT), and retrieval date.

3.2 THE SYSTEM SHALL NOT modify vendored source. WHERE adaptation is required (spend
ceiling, iteration ceiling, scenario injection, log capture), THE SYSTEM SHALL implement
it in `evals/arms/reference.py` as wrapping, monkeypatch-free configuration, and SHALL
list every adaptation in `ArmSpec.divergences[]`.

3.3 THE REFERENCE ARM SHALL translate a `ScenarioContract` into the harness's
`app_spec.txt` input and SHALL cap generated features at a configurable
`max_features` (default `25`, upstream default `200`) recorded as a divergence.

3.4 THE REFERENCE ARM SHALL impose the ceilings of R1.5 externally, since the vendored
harness has none, and SHALL record that absence as an expected FM-007 positive rather
than a defect of the adapter.

3.5 THE SYSTEM SHALL assemble a Trace from the reference arm's artifacts
(`feature_list.json`, `claude-progress.txt`, git history, captured stdout tool events)
and SHALL record coverage gaps in `trace.warnings[]` where the reference harness emits no
equivalent of an `ai-team` log stream, rather than fabricating spans.

3.6 IF the vendored harness cannot run in the current environment (missing
`@anthropic-ai/claude-code`, missing node, blocked network), THEN THE SYSTEM SHALL fail
the arm with `status = "unavailable"` and SHALL NOT silently substitute another arm.

---

### R4 — Ablation runner

**User story:** As the author of the harness, I want to disable one component at a time
and measure what changes, so that "which failures are mine?" has a numeric answer per
component.

**Acceptance criteria**

4.1 THE SYSTEM SHALL define an `AblationSpec` naming one or more ablatable components
from a closed set: `guardrails.behavioral`, `guardrails.security`, `guardrails.quality`,
`smoke_gate`, `constraints_pinning`, `lessons_loop`, `spend_guard`,
`subprocess_isolation`, `contract_negotiation`, `session_regression_check`,
`role_decomposition`.

4.2 THE SYSTEM SHALL implement ablation as configuration read at run construction — no
code deletion, no branch — and SHALL fail loudly if a named component cannot be disabled
by config.

4.3 THE SYSTEM SHALL record the active component set in `ArmSpec.harness_components` and
in the Trace's provenance, so a Trace is self-describing without its sweep manifest.

4.4 FOR each ablation arm, THE SYSTEM SHALL report the delta against the full `ai_team`
arm on: FM incidence per mode, `cost_usd`, `wall_clock_s`, accepted-change rate, and
smoke outcome.

4.5 WHERE an ablation produces no measurable delta across a sweep, THE SYSTEM SHALL
surface that component in the report under a heading that names it plainly
(`components with no measured effect at this n`), because a component that earns nothing
is the finding.

4.6 THE SYSTEM SHALL NOT treat a single-sweep ablation delta as significant; the report
SHALL carry `n` and a confidence interval for every delta, per eval-harness design
principle 2.

---

### R5 — Arm-aware reporting and enforced claim discipline

**User story:** As someone who publishes these numbers, I want the tooling to refuse to
emit an unfalsifiable comparison, so that the honesty of the results does not depend on
my remembering to add a caveat.

**Acceptance criteria**

5.1 THE SYSTEM SHALL extend the existing report with a **ladder table**: one row per arm,
columns `arm_id`, `n`, `cost_usd` (mean, CI), `wall_clock_s` (mean, CI),
`fm_incidence` per mode, `smoke_pass_rate`, `accepted_change_rate`, `demotion_rate`.

5.1a THE REPORT SHALL additionally break cost and wall-clock down **by phase** per arm
(planning, build, verification, QA), sourced from `logs/costs.jsonl`, so that a
component's price is legible next to what it buys rather than only in the run total.

5.1b WHERE both an ablation delta and a phase cost share are available for a component,
THE REPORT MAY render a derived `cost_per_fm_avoided`, and SHALL mark it
`DERIVED — RATIO OF TWO NOISY ESTIMATES` and suppress it entirely at `n < 5` per arm.

5.2 THE SYSTEM SHALL refuse to render a cross-arm comparison WHEN model ids differ across
arms without an explicit `--allow-mixed-model` flag, and SHALL stamp any such table
`MIXED-MODEL — NOT A HARNESS COMPARISON`.

5.3 THE SYSTEM SHALL refuse to render a cross-arm comparison at `n < 3` per arm without
`--allow-underpowered`, and SHALL stamp such tables `UNDERPOWERED`.

5.4 THE REPORT SHALL state, for every arm, the `source_ref` and the divergence list, so a
reader can see exactly how the reference harness was configured.

5.5 THE SYSTEM SHALL emit the ladder table as both Markdown (for `docs/`) and JSON (for
regression diffing), and the JSON SHALL be the source the Markdown is rendered from, per
FM-008 `metric_source_drift`.

---

### R6 — Durable, monotonic acceptance list

**User story:** As a harness author, I want acceptance criteria to survive a context
reset as a file the harness owns, so that progress is resumable and goalpost-moving is
detectable from a diff.

**Acceptance criteria**

6.1 THE SYSTEM SHALL write `ACCEPTANCE.json` to the run workspace root at the end of the
planning phase, derived from the existing acceptance criteria in
`src/ai_team/models/requirements.py`, so no new authoring step is introduced.

6.2 Each item SHALL contain `id` (stable, content-hashed), `category`
(`functional` | `style` | `security` | `performance`), `description`, `steps[]`,
`passes: bool`, `verified_by` (`null` | `smoke` | `ui_smoke` | `test` | `qa_agent`),
`verified_at`, `evidence[]` (artifact paths), and `demotions[]`.

6.3 THE SYSTEM SHALL treat `ACCEPTANCE.json` as **harness-owned**: it SHALL be written
through `src/ai_team/harness/acceptance.py` only, and the SDK backend's PreToolUse hook
SHALL deny direct `Write`/`Edit` to that path by any agent.

6.4 THE SYSTEM SHALL permit exactly one agent-driven mutation: `passes: false → true`,
and only when accompanied by at least one `evidence[]` entry that resolves to a file in
the workspace.

6.5 THE SYSTEM SHALL permit harness-issued demotion (`true → false`) only from the R9
regression check, appending a `demotions[]` record with `session_id`, `reason`, and
`detected_at`.

6.6 THE SYSTEM SHALL expose acceptance state to agents read-only through an MCP tool
(`acceptance_status`) returning counts and the highest-priority unsatisfied item, so
agents never need to parse the file to orient.

6.7 THE ACCEPTANCE LIST SHALL be included in the change receipt and in the Trace's
artifact inventory.

---

### R7 — FM-014 `acceptance_criteria_mutation`

**User story:** As an eval engineer, I want an agent that edits the definition of done to
be caught by a free check, so that a run cannot pass by lowering the bar.

**Acceptance criteria**

7.1 THE SYSTEM SHALL add `FM-014 acceptance_criteria_mutation` to
`evals/taxonomy/failure_modes.yaml` with `layer: model`, `harness_layer: tools`,
`severity: blocker`, `detection: check`, `introduced_in: "1.2.0"`.

7.2 THE SYSTEM SHALL implement `CHK-acceptance-monotonic` over a Trace: comparing the
first and last observed states of `ACCEPTANCE.json`, THE CHECK SHALL fail on any removed
item, any changed `id`/`description`/`steps`, any reordering that changes item identity,
or any `true → false` transition lacking a `demotions[]` record.

7.3 THE CHECK SHALL fail on any `false → true` transition whose `evidence[]` is empty or
names a path absent from the workspace inventory.

7.4 THE SYSTEM SHALL ship one failing and one passing trace fixture under
`evals/fixtures/traces/`, named per the existing convention
(`CHK-acceptance-monotonic__fail__fixture`, `…__pass__fixture`).

7.5 THE CHECK SHALL run in Tier A at $0.00 and SHALL require no model call.

---

### R8 — Multi-session continuation

**User story:** As an operator, I want a run to continue across many fresh-context
sessions against the durable checklist, so that a build larger than one context window is
possible and cross-session regression becomes observable.

**Acceptance criteria**

8.1 THE SYSTEM SHALL provide `src/ai_team/harness/session_loop.py` driving N sessions over
one workspace, where each session begins with a **fresh context** — not a compaction —
seeded only by `CONSTRAINTS.md`, `STATE.md`, `LESSONS.md`, `ACCEPTANCE.json`, and git
history.

8.2 THE LOOP SHALL terminate on any of: all acceptance items `passes: true`;
`max_sessions` reached; cumulative spend ceiling reached; wall-clock ceiling reached; or
`no_progress_sessions` consecutive sessions with zero net `passes` transitions
(default `2`).

8.3 THE LOOP SHALL write one `SessionRecord` per session to `logs/sessions.jsonl`:
`session_id`, `index`, `started_at`, `ended_at`, `status`, `items_attempted[]`,
`items_passed[]`, `items_demoted[]`, `cost_usd`, `context_pressure_at_end`,
`termination_reason`.

8.4 THE LOOP SHALL be resumable: invoking it on an existing workspace SHALL continue from
the persisted state without re-running planning, and SHALL NOT regenerate
`ACCEPTANCE.json`.

8.5 THE LOOP SHALL require a git commit at session end and SHALL mark a session
`status = "dirty_exit"` when the workspace has uncommitted changes, feeding FM-012
`uncommitted_write`.

8.6 THE LOOP SHALL be off by default; enabling it SHALL require an explicit
`--max-sessions N` and an explicit total budget.

---

### R9 — Session-start regression verification

**User story:** As an operator of a long build, I want each session to prove that
previously passing work still passes before it writes anything new, so that silent
cross-session regression is caught at the session that caused it.

**Acceptance criteria**

9.1 AT the start of every session after the first, THE SYSTEM SHALL re-verify `k`
previously passing acceptance items (default `k = 2`) selected by a deterministic policy:
the highest-priority passing item plus one sampled by a seeded RNG over items not
verified in the last `m` sessions.

9.2 WHERE re-verification fails, THE SYSTEM SHALL demote the item per R6.5 and SHALL
require the session to address demoted items **before** attempting any unsatisfied item.

9.3 THE SYSTEM SHALL emit a `regression_check` span per verified item into the Trace, with
`item_id`, `outcome`, `evidence[]`, and `duration_s`.

9.4 THE SYSTEM SHALL surface `demotion_rate` (demotions per session) in the ladder report
as a first-class reliability metric, since it measures exactly what single-pass runs
cannot see.

---

### R10 — FM-015 `premature_termination_under_context_pressure`

**User story:** As an eval engineer, I want "context anxiety" — an agent wrapping up early
as its window fills — recorded as a named, detected failure mode rather than folklore.

**Acceptance criteria**

10.1 THE SYSTEM SHALL add `FM-015 premature_termination_under_context_pressure` to the
taxonomy with `layer: model`, `harness_layer: context`, `severity: major`,
`detection: check`, `introduced_in: "1.2.0"`.

10.2 THE SYSTEM SHALL record `context_pressure` — consumed tokens over usable window — on
every `phase_end` and `session_end` span, sourced from the SDK's usage reporting and
falling back to `src/ai_team/config/token_tracker.py`.

10.3 THE SYSTEM SHALL implement `CHK-premature-termination`, failing WHEN a phase or
session ends with `status = "ok"`, at least one unsatisfied acceptance item remains, no
blocking error or budget event is present in the trailing span window, AND
`context_pressure ≥ 0.75` (configurable).

10.4 THE CHECK SHALL NOT fire where termination is explained by a `spend_event`, a
watchdog kill, an `error` span, or `max_turns` exhaustion — those are FM-007 and
FM-003 territory and SHALL remain attributed there.

10.5 THE SYSTEM SHALL ship fail/pass trace fixtures and SHALL run in Tier A at $0.00.

10.6 THE SYSTEM SHALL report FM-015 incidence **by arm**, since the hypothesis under test
is that fresh-context sessions (R8) reduce it relative to a single long context.

---

### R11 — Build contract negotiation

**User story:** As a harness author, I want QA to agree on what "done" means for an item
*before* the developer implements it, so that specification drift is caught at plan time
rather than at review time.

**Acceptance criteria**

11.1 BEFORE implementation of an acceptance item, THE SYSTEM SHALL have the developer
agent write `docs/contracts/<item_id>.json` containing `item_id`, `approach` (prose),
`testable_behaviors[]` (each a concrete, observable assertion), `files_to_touch[]`, and
`out_of_scope[]`.

11.2 THE QA AGENT SHALL validate the contract against the acceptance item and SHALL
return `accepted` or `rejected` with `reasons[]`, written to the same file under
`review`, using file-based handoff per `CLAUDE.md` (agents coordinate through paths, not
shared memory).

11.3 WHERE a contract is rejected, THE SYSTEM SHALL permit at most `max_contract_rounds`
(default `2`) renegotiations before escalating to the existing error-handling path, so
negotiation cannot become an unbounded loop (FM-002).

11.4 IMPLEMENTATION SHALL NOT begin on an item whose contract is not `accepted`; the
PreToolUse hook SHALL deny writes to `src/` for an item lacking an accepted contract when
contract negotiation is enabled.

11.5 VERIFICATION SHALL be scored against `testable_behaviors[]`, not against the
developer's own summary of what it built.

11.6 CONTRACT NEGOTIATION SHALL be an ablatable component (R4.1), because its value is a
hypothesis this spec exists to test, not an assumption.

---

### R12 — FM-016 `self_graded_verification`

**User story:** As an eval engineer, I want a check that the thing which wrote the code is
not the thing which passed it, so that the generator/evaluator separation is enforced
rather than assumed.

**Acceptance criteria**

12.1 THE SYSTEM SHALL add `FM-016 self_graded_verification` to the taxonomy with
`layer: harness`, `harness_layer: verification`, `severity: major`, `detection: check`.

12.2 THE SYSTEM SHALL record, on every acceptance `passes` transition, the
`agent_role`, `session_id`, and `subagent_id` responsible for the verifying evidence.

12.3 THE SYSTEM SHALL implement `CHK-verifier-independence`, failing WHEN an item's
`passes: true` transition was produced by the same `(agent_role, subagent_id)` that
produced the writes for that item, and no independent verifier
(`smoke`, `ui_smoke`, `test`) contributed evidence.

12.4 THE CHECK SHALL pass where a deterministic verifier supplied the evidence, since a
passing smoke probe is independent of who wrote the code.

12.5 THE SYSTEM SHALL ship fail/pass fixtures and run in Tier A at $0.00.

---

### R13 — UI-level verification

**User story:** As a harness author, I want verification that drives the real UI and
reports console errors, so that "HTTP 200" stops counting as proof that a feature works.

**Acceptance criteria**

13.1 THE SYSTEM SHALL add `src/ai_team/tools/ui_smoke_tools.py::run_ui_smoke` using
**Playwright**, mirroring the contract of `run_app_smoke`: boot, act, probe, write
`docs/ui_smoke_results.json`, never probe a foreign service.

13.2 `run_ui_smoke` SHALL emit, per step: `action`, `selector`, `outcome`,
`console_errors[]`, `page_errors[]`, `screenshot_path`, `duration_ms`.

13.3 CONSOLE ERRORS SHALL be a **deterministic** signal: a step with any
`console_errors[]` or `page_errors[]` entry SHALL fail that step without a model call.

13.4 SCREENSHOTS SHALL be written under `docs/verification/<item_id>/` and SHALL be listed
in the Trace artifact inventory so they survive as evidence (R6.4).

13.5 THE SYSTEM SHALL expose `run_ui_smoke` as an MCP tool on the `ai_team_tools` server
and SHALL add it to the QA role's allow-list only.

13.6 WHERE the scenario declares no UI (`scenario.ui == null`), `run_ui_smoke` SHALL skip
cleanly and SHALL record `skipped` rather than `pass`, so skips cannot inflate pass rates
(FM-008).

13.7 THE SYSTEM SHALL define, in `docs/`, a four-criterion design rubric — design quality,
originality, craft, functionality — with calibration examples, for use by a QA judge.
THE RUBRIC SHALL carry an explicit warning that criterion wording steers output toward
convergence, and SHALL NOT gate a build until it clears the eval-harness alignment bar.

13.8 `CHK-runtime-smoke-present` SHALL be extended to recognise a UI smoke result as
satisfying FM-006 for UI-bearing scenarios, and a backend-only probe SHALL NOT satisfy it
for those scenarios.

---

### R14 — Default-deny bash confinement

**User story:** As a harness author, I want bash to be default-deny with fail-safe
parsing, so that the security layer does not depend on having enumerated every dangerous
pattern in advance.

**Acceptance criteria**

14.1 THE SYSTEM SHALL add an allowlist layer to
`src/ai_team/backends/claude_agent_sdk_backend/hooks/security.py`, evaluated **after** the
existing deny patterns, such that a command is permitted only when every extracted command
name is in the role's allowlist.

14.2 ALLOWLISTS SHALL be per-role, defined in `tools/permissions.py` beside the existing
tool allow-lists.

14.3 WHERE the command string cannot be parsed, THE SYSTEM SHALL **block** and record the
reason, rather than falling through to permit.

14.4 THE PARSER SHALL handle, and SHALL have adversarial tests for: `&&`, `||`, `;`,
pipes, subshells `$(…)` and backticks, `env VAR=x cmd`, `xargs`, `nohup`, `timeout`,
absolute paths, `git -c core.hooksPath=…` and `git -c core.pager=…`, and unclosed quotes.
Anything the parser cannot decompose SHALL be blocked (14.3).

14.5 THE SYSTEM SHALL account for allowlist blocks in the guardrail false-positive corpus
and SHALL hold `CHK-guardrail-fp-budget` (FM-005) at or below its existing budget; a rise
in false positives SHALL fail the gate exactly as any other guardrail regression.

14.6 THE ALLOWLIST SHALL be an ablatable component, and SHALL be enabled by default only
after 14.5 is demonstrated on the fixture corpus.

14.7 THE SYSTEM SHALL NOT adopt the reference harness's practice of writing a settings
file into the generated workspace; filesystem confinement SHALL remain hook-enforced and
workspace-bound as it is today.

---

### R15 — Ablation results expire with the model

**User story:** As a harness author, I want every component's measured value stamped with
the model it was measured against, so that a harness does not silently accumulate
components that stopped earning their place two model versions ago.

**Rationale:** every component in a harness encodes an assumption about what the model
cannot do on its own, and those assumptions go stale as models improve. The article this
spec aligns with removed its sprint-decomposition construct outright when a newer model
handled the job natively. A harness that cannot detect that about itself will keep paying
for it.

**Acceptance criteria**

15.1 THE SYSTEM SHALL record on every ablation result: `model_id`, `model_snapshot_date`,
`measured_at`, `scenario_id`, `n`, and the resulting delta with its confidence interval,
persisted to `evals/results/ablations/<component>.json`.

15.2 WHEN the repo's configured default model for a role differs from the `model_id` of
that component's most recent ablation result, THE SYSTEM SHALL mark the result `STALE` in
the report and SHALL NOT present its delta as current evidence.

15.3 THE SYSTEM SHALL provide `python -m evals.cli ablation status`, listing every
ablatable component with its last measured delta, the model it was measured on, and
`current` | `STALE` | `never measured`.

15.4 THE SYSTEM SHALL treat `never measured` as a first-class state and SHALL NOT render
it as a zero delta, because "we have never checked" and "it makes no difference" are
different claims.

15.5 THE GATE SHALL NOT fail on staleness. Staleness is reporting, not enforcement — a
harness component is not a regression.

---

### R16 — In-run evaluator calibration and FM-017 `evaluator_capitulation`

**User story:** As a harness author, I want to know how often my QA agent finds a real
defect and then waives it, so that "QA passed" means something.

**Rationale:** an out-of-the-box model used as QA identifies legitimate issues and then
talks itself into approving the work anyway, and tests superficially rather than at the
edges. This is distinct from FM-016: the evaluator here *is* independent, and still
returns the wrong verdict. It is also distinct from the offline judge alignment in
`eval-harness`, which scores traces after the fact; this is the in-run agent whose verdict
gates a build.

**Acceptance criteria**

16.1 THE SYSTEM SHALL add `FM-017 evaluator_capitulation` to the taxonomy with
`layer: model`, `harness_layer: verification`, `severity: major`, `detection: check`,
`introduced_in: "1.2.0"`.

16.2 THE QA AGENT SHALL emit a structured verdict per acceptance item —
`{item_id, verdict, issues[], severity_per_issue, evidence[]}` — to
`docs/qa_verdicts.jsonl`, rather than prose the harness must parse.

16.3 THE SYSTEM SHALL implement `CHK-evaluator-capitulation`, failing WHEN a verdict is
`accept` while `issues[]` contains at least one entry of severity `major` or `blocker`,
and no remediation write span for that item appears between the issue's detection and the
verdict.

16.4 THE SYSTEM SHALL compute the QA agent's **false-negative rate against deterministic
verifiers**: for every item the QA agent accepted where `smoke`, `ui_smoke`, or the test
suite subsequently failed, count a QA false negative. THIS SHALL require no human labels
and no judge, since the deterministic verifier is the ground truth.

16.5 THE REPORT SHALL surface `qa_false_negative_rate` per arm, and the ladder table SHALL
show it beside `smoke_pass_rate`, because an arm can buy its pass rate by lowering its
evaluator.

16.6 WHERE the QA prompt is revised, THE SYSTEM SHALL record the prompt hash on every
verdict, so a change in false-negative rate can be attributed to the prompt rather than to
the model or the scenario.

16.7 THE SYSTEM SHALL ship fail/pass fixtures for `CHK-evaluator-capitulation` and SHALL
run it in Tier A at $0.00.

---

### R17 — Test hygiene and cover-before-extend

**User story:** As the author of a harness whose whole claim is that it measures things
honestly, I want the test suite itself to be measurably trustworthy, so that a silent gap
in the instruments cannot masquerade as a green build.

**Rationale:** a 2026-09-12 audit found two defects that **no amount of line coverage
would have caught**, both in the eval suite this spec extends: a unit test rewrote a
committed golden record's `validated_at` on every run
(`test_r16_unit_gaps.py` monkeypatched `VALIDATION_LOG` but not `ALIGNMENT_DIR`), and a
second test's assertion silently depended on the repo's `workspace/` directory being
empty. Both suites stayed green throughout. The same audit found that `ALL_CHECK_IDS` —
the hand-maintained list driving the network-purity, sensitivity and outcome suites — was
never asserted to match the check registry, so a registered-but-unlisted check would
escape all three. This spec adds **four** checks.

**Acceptance criteria**

17.1 THE TEST SUITE SHALL fail WHEN any test modifies, creates or removes a tracked file
under `evals/golden/`, `evals/fixtures/traces/` or `evals/taxonomy/`, enforced by a
session-scoped guard in `tests/conftest.py`. A test needing to exercise a writer SHALL
redirect it to `tmp_path` by monkeypatching the module's directory constant.

17.2 THE TEST SUITE SHALL assert that `ALL_CHECK_IDS` and the check registry are equal in
both directions, that the list is duplicate-free, that every registered check has
committed `__fail__` and `__pass__` fixtures, and that no check references a failure mode
absent from the taxonomy.

17.3 THE TEST SUITE SHALL fail WHEN a failure mode with a registered check is still
`status: reserved` in the taxonomy — the half-landed state task 0.2 creates deliberately.

17.4 WORKSPACE DISCOVERY SHALL NOT depend on hardcoded filesystem roots.
`evals/run_evals.py::_WORKSPACE_PATH_RE` matches only paths under
`/Users|/home|/tmp|/var|/private`; on a host whose temp root differs, no candidate is
found and `_find_workspace` falls through to "newest directory in `./workspace/`" — which
returns a **wrong workspace rather than an error**, so a trace can be assembled from
someone else's run. `test_find_workspace_from_log` fails for exactly this reason on such a
host. THE FUNCTION SHALL either derive candidate roots from the log text without a root
allowlist, or return `None` when the log yields no match, rather than guessing. Related to
FM-008 `metric_source_drift`: a silently-wrong source is worse than a missing one.

17.5 WHERE a task in this plan extends an existing module, THAT TASK SHALL bring the
module's existing behaviour under test **before** adding to it. The modules this plan
lands on, with their branch coverage as of 2026-09-12:
`tools/mcp_server.py` **0%** (tasks 1.5, 7.3), `tools/permissions.py` 35% (task 10.2),
`hooks/quality.py` 31% and `hooks/audit.py` 33% (tasks 1.4, 9.3).
`hooks/security.py` was brought to 100% line / 100% branch on 2026-09-12 and is the bar.

17.6 EVERY deny, refusal or guard path introduced by this spec — the `ACCEPTANCE.json`
write denial (R6.3), the contract gate (R11.4), the bash allowlist (R14) — SHALL reach
**100% branch coverage**, with adversarial tests, before the component is enabled by
default. Feature paths carry no such bar; refusal paths do, because a guard's untested
branch is a guard that is not there.

17.7 WHERE a test documents current behaviour that the plan intends to change (the
allowlist bypasses of R14.4, the case-sensitive `AI_TEAM_DENY_NATIVE_TOOLS` switch), THE
TEST SHALL say so in its docstring and name the requirement that will invert it, so the
change arrives with a deliberately flipped assertion rather than a silent edit.

17.8 THE COVERAGE FLOOR (`fail_under`) SHALL be re-ratcheted at the end of each phase that
adds modules, and SHALL never be lowered to accommodate new untested code.

---

## Traceability summary

| Requirement | Source | New FM | New check |
| --- | --- | --- | --- |
| R1–R3 | Article (solo control arm) + quickstart (reference harness) | — | — |
| R4 | Article ("iteratively strip complexity") | — | — |
| R5 | `ai-team` README's own caveat | — | — |
| R6 | Quickstart `feature_list.json` | — | — |
| R7 | Quickstart monotonic invariant | FM-014 | `CHK-acceptance-monotonic` |
| R8–R9 | Quickstart session loop + article context resets | — | — |
| R10 | Article ("context anxiety") | FM-015 | `CHK-premature-termination` |
| R11 | Article (sprint contracts) | — | — |
| R12 | Article (self-evaluation bias) | FM-016 | `CHK-verifier-independence` |
| R13 | Quickstart Puppeteer verification + article Playwright evaluator | — | extends `CHK-runtime-smoke-present` |
| R14 | Quickstart bash allowlist | — | extends `CHK-guardrail-fp-budget` |
| R15 | Article (components encode assumptions that go stale; sprint construct removed in v2) | — | — |
| R16 | Article (evaluator waives its own findings; QA is weak out of the box) | FM-017 | `CHK-evaluator-capitulation` |
| R17 | 2026-09-12 coverage audit (golden-file writes, order-dependent test, unguarded `ALL_CHECK_IDS`) | — | — |
