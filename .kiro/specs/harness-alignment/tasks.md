# Implementation Plan — Harness Alignment

**Spec ID:** `harness-alignment`
**Requirements:** [`requirements.md`](./requirements.md) · **Design:** [`design.md`](./design.md)

In-repo work is checked off. Live-spend tasks **4.3, 4.5, 5.4, 11.4** stay open
(human-triggered; not run).

---

## How to execute this plan

- Work **one task at a time, in order**. Do not batch phases. Each task is sized to be
  reviewable on its own.
- Every task lists a **Definition of done**. Do not mark it complete until each bullet is
  literally true.
- Run `uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run mypy evals/`
  before marking any task complete.
- **Do not spend money.** Only Phases 4, 5, 7.4 and 11 make live model calls, and every one
  of them is human-triggered and budget-capped. Everything else runs against fixtures.
- Phases 1–2 are strictly additive: no existing check, backend, or report path changes.
- New behavior that touches a normal run (Phases 8, 9, 10) ships **off by default** behind
  an explicit flag until its ablation shows it earns its place.

Cursor prompt shape:

```
Read .kiro/specs/harness-alignment/requirements.md and design.md for context.
Implement task 1.2 from .kiro/specs/harness-alignment/tasks.md.
Do not start any other task. Stop when its Definition of done is satisfied and
`uv run ruff check . && uv run mypy src/ evals/ && uv run pytest tests/unit` passes.
```

---

## Phase 0 — Scaffolding

- [x] **0.1 Create package skeleton**
  - Create `evals/arms/` (with `__init__.py`, `py.typed` not needed — inherits from `evals`),
    `evals/arms/vendor/.gitkeep`, `evals/results/ladder/.gitkeep`,
    `src/ai_team/harness/` additions are in-place (package exists).
  - Add `docs/contracts/.gitkeep` to the workspace scaffold template, not to the repo root.
  - **Definition of done:** `uv run python -c "import evals.arms"` succeeds; `uv run mypy evals/` passes.
  - _Requirements: R1.4_

- [x] **0.2 Taxonomy version bump and reservations**
  - Bump `evals/taxonomy/failure_modes.yaml` `version` to `1.2.0`.
  - Reserve FM-014, FM-015, FM-016, FM-017 ids with `status: reserved` and no
    `implemented_by`, so nothing else claims them mid-implementation.
  - **Definition of done:** `python -m evals.cli taxonomy coverage` runs clean and reports the
    four reserved modes as unimplemented.
  - _Requirements: R7.1, R10.1, R12.1, R16.1_

- [x] **0.3 Trace schema additions**
  - Add `Trace.arm_id: str | None = None` and allow `context_pressure: float | None` inside
    `phase_end` / `session_end` span payloads. Bump `SCHEMA_VERSION`.
  - Confirm every existing fixture under `evals/fixtures/traces/` still loads.
  - **Definition of done:** round-trip test passes for a trace with and without the new fields;
    `python -m evals.cli index rebuild` succeeds on the existing corpus.
  - _Requirements: R1.2, R5.1, R10.2_

- [x] **0.4 Suite guards (landed 2026-09-12 — verify, do not rewrite)**
  - `tests/conftest.py` hashes `evals/golden/`, `evals/fixtures/traces/` and
    `evals/taxonomy/` at session start and asserts them unchanged at teardown.
  - `tests/unit/evals/test_suite_drift_guards.py` asserts `ALL_CHECK_IDS` ≡ registry, no
    duplicates, fixtures present per check, no check pointing at an unknown failure mode,
    and no implemented mode still `reserved`.
  - **Definition of done:** both files present and green; confirm the reserved-mode guard
    (R17.3) fails while FM-014…017 are reserved *and* a check for one of them is
    registered — this is the half-landed state Phase 2 passes through, and it should be
    loud.
  - Fix `_find_workspace` (R17.4): drop the hardcoded root allowlist in
    `_WORKSPACE_PATH_RE`, or return `None` when the log yields no candidate instead of
    falling back to the newest directory in `./workspace/`. The fallback returns a wrong
    workspace rather than an error, so a trace can be built from an unrelated run —
    `test_find_workspace_from_log` fails on any host whose temp root is outside
    `/Users|/home|/tmp|/var|/private`.
  - _Requirements: R17.1, R17.2, R17.3, R17.4_

---

## Phase 1 — Durable acceptance list (free)

- [x] **1.1 Acceptance data model**
  - Implement `src/ai_team/harness/acceptance.py` models per design §3.1: `AcceptanceItem`,
    `AcceptanceList`, `Demotion`, `VerifierIdentity`, `AcceptanceStatus`.
  - `id` = `sha256(normalized_description + "\x00".join(steps))[:12]`; normalization collapses
    whitespace so cosmetic reformatting does not change identity.
  - **Definition of done:** unit test asserts id stability across whitespace/casing-of-punctuation
    changes and instability across any semantic edit.
  - _Requirements: R6.1, R6.2_

- [x] **1.2 Writer, loader, and the snapshot log**
  - Implement `write_initial`, `load`, `mark_passing`, `demote`, `status`.
  - Atomic writes (temp + `os.replace`). Every write appends
    `{ts, op, item_id, sha256_of_file}` to `logs/acceptance.jsonl`.
  - `mark_passing` rejects when `evidence` is empty or any path is absent from the workspace.
  - **Definition of done:** unit tests cover accept, reject-on-missing-evidence, demote,
    concurrent-write safety (two writers, no torn file), and that `demote` refuses without a reason.
  - _Requirements: R6.3, R6.4, R6.5_

- [x] **1.3 Wire into planning**
  - Call `write_initial` at the end of the planning phase from the existing requirements
    output (`src/ai_team/models/requirements.py`), for all three backends.
  - Priority is assigned from existing MoSCoW ordering where present, else source order.
  - **Definition of done:** a stubbed planning run produces `ACCEPTANCE.json` with ≥ 1 item;
    the file appears in the change receipt and the Trace artifact inventory.
  - _Requirements: R6.1, R6.7_

- [x] **1.4 Deny agent writes to the acceptance file**
  - Extend the SDK backend PreToolUse hook to deny `Write`/`Edit`/`MultiEdit` whose
    `file_path` resolves to `ACCEPTANCE.json`, with a reason that names the MCP tool to use instead.
  - **Definition of done:** adversarial unit tests cover the direct path, a relative path, a
    path with `./`, and a symlink pointing at it — all denied; the new denial reaches
    **100% branch coverage** (R17.6). `hooks/security.py` is already at 100%/100% — keep it
    there, and bring `hooks/quality.py` (31% branch) and `hooks/audit.py` (33%) up as part
    of this task, since the same hook chain now carries the acceptance rule (R17.5).
  - _Requirements: R6.3, R17.5, R17.6_

- [x] **1.5 MCP tools `acceptance_status` and `acceptance_mark_passing`**
  - Add both to `tools/mcp_server.py`; `acceptance_status` on all role allow-lists,
    `acceptance_mark_passing` on QA only.
  - `acceptance_mark_passing` records `VerifierIdentity` (`agent_role`, `session_id`, `subagent_id`).
  - **Definition of done:** integration test drives both tools through the MCP surface and
    asserts the identity is persisted. **Cover first (R17.5):** `tools/mcp_server.py` is at
    **0% branch coverage** — bring its existing tool registration, argument validation and
    error paths under test before adding to it, or these two tools will be the only part of
    that module anyone can see break.
  - _Requirements: R6.6, R12.2, R17.5_

---

## Phase 2 — Three new checks (free, retroactive)

- [x] **2.1 `CHK-acceptance-monotonic`**
  - Implement `evals/checks/acceptance.py`. Compare first and last acceptance snapshots:
    fail on removed ids, changed ids, `true → false` without a `demotions[]` record, or a
    `false → true` with empty/dangling evidence.
  - Return `inconclusive` when the trace has no acceptance artifacts at all.
  - **Definition of done:** registered in the check registry; fail and pass fixtures added under
    `evals/fixtures/traces/` following the existing naming convention; FM-014 flipped from
    `reserved` to `active` with `implemented_by: [CHK-acceptance-monotonic]`.
  - _Requirements: R7.2, R7.3, R7.4, R7.5_

- [x] **2.2 Record `context_pressure`**
  - Emit `context_pressure` on `phase_end` and `session_end` spans from SDK usage reporting,
    falling back to `src/ai_team/config/token_tracker.py`. Emit `None` rather than guessing
    when the window size is unknown.
  - **Definition of done:** a stubbed run produces the field on every phase end; a stub with
    no usage data produces `None` and does not raise.
  - _Requirements: R10.2_

- [x] **2.3 `CHK-premature-termination`**
  - Implement in `evals/checks/context.py`. Fire only when: status ok, ≥ 1 unsatisfied
    acceptance item, no `spend_event` / `error` / watchdog / `max_turns` evidence in the
    trailing window, and `context_pressure ≥ 0.75` (configurable via check params).
  - Return `inconclusive` when `context_pressure` is `None`.
  - **Definition of done:** fail/pass fixtures plus **four negative-control fixtures**
    (spend event, watchdog kill, error span, max_turns) each asserted not to fire;
    FM-015 set `active`.
  - _Requirements: R10.3, R10.4, R10.5_

- [x] **2.4 `CHK-verifier-independence`**
  - Implement in `evals/checks/verification.py`. Fail when a `passes` transition's
    `VerifierIdentity` matches the identity that produced the write spans for that item and no
    deterministic verifier contributed evidence.
  - **Definition of done:** fail/pass fixtures; a fixture where `smoke` supplied the evidence
    passes even with a matching identity; FM-016 set `active`.
  - _Requirements: R12.3, R12.4, R12.5_

- [x] **2.5 Structured QA verdicts**
  - Have the QA agent emit `docs/qa_verdicts.jsonl` per design §4.5a:
    `{item_id, verdict, issues[], evidence[], qa_prompt_hash, identity, emitted_at}`.
    Structured output, not prose — the check needs to read the evaluator's own findings, not
    infer them.
  - Add the verdict log as a Trace span source (`qa_verdict`).
  - **Definition of done:** a stubbed QA pass writes parseable verdicts including the prompt
    hash; Trace assembly tolerates the file's absence.
  - _Requirements: R16.2, R16.6_

- [x] **2.6 `CHK-evaluator-capitulation` and the QA false-negative rate**
  - Implement in `evals/checks/verification.py`: fail when `verdict == "accept"` while
    `issues[]` holds a `major`/`blocker` entry and no remediation write span for that item
    appears between detection and verdict.
  - Compute `qa_false_negative_rate`: items the QA agent accepted that a deterministic
    verifier (`smoke`, `ui_smoke`, tests) later failed. No labels, no judge.
  - **Definition of done:** fail/pass fixtures; a fixture where the issue *was* fixed before
    acceptance passes; FM-017 set `active`; the rate appears in the metrics output.
  - _Requirements: R16.1, R16.3, R16.4, R16.5, R16.7_

- [x] **2.7 Backfill the existing corpus**
  - Run all four new checks over every trace already in `evals/traces/` and record outcomes.
  - **Definition of done:** `python -m evals.cli run --tier A` passes; a short note in
    `docs/journal/` records what the new checks found retroactively, with trace ids.
  - _Requirements: R7.5, R10.5, R12.5, R16.7_

---

## Phase 3 — Arm scaffold (no new spend)

- [x] **3.1 Arm protocol and registry**
  - Implement `evals/arms/base.py` and `evals/arms/registry.py` per design §2.2.
  - **Definition of done:** round-trip tests for `ArmSpec`/`ArmRun`/`Divergence`; duplicate
    registration raises.
  - _Requirements: R1.1, R1.3, R1.4_

- [x] **3.2 `ai_team` arm over the existing runner**
  - Implement `evals/arms/ai_team.py` wrapping the current run path. No behavior change; it
    only produces an `ArmSpec` and stamps `arm_id` onto the Trace.
  - **Definition of done:** an existing scenario run through the arm produces a byte-identical
    workspace to running it directly, plus `arm_id` on the trace.
  - _Requirements: R1.2, R1.6_

- [x] **3.3 Budget and ceiling enforcement**
  - Implement `CostControls`, the pre-flight sweep budget check, and the wall-clock kill.
  - **Definition of done:** a stub arm that sleeps past its ceiling is terminated and still
    yields a Trace with `status = "budget_exhausted"`.
  - _Requirements: R1.5_

- [x] **3.4 `ladder` CLI with `--dry-run` default**
  - `python -m evals.cli ladder run --scenario S --arms a,b --n N [--execute]`.
  - Dry run prints the resolved plan, per-arm ceilings, and projected total; refuses when the
    projection exceeds the $25 sweep ceiling.
  - **Definition of done:** dry run works end-to-end with stub arms and spends nothing;
    `--execute` is required for any live call.
  - _Requirements: R1.5, R4.6_

---

## Phase 4 — Control arms (first spend)

- [x] **4.1 Implement `SoloArm`**
  - Single SDK session, one general system prompt, scenario brief only. Pre-create the standard
    workspace scaffold. Keep cost/audit hooks; remove all behavioral components.
  - **Definition of done:** unit test with a mocked client asserts exactly one session, no
    subagents, no guardrail invocation, and the standard workspace layout.
  - _Requirements: R2.1, R2.2, R2.3_

- [x] **4.2 Trace assembly and receipt parity**
  - Ensure `from_workspace` yields a valid Trace for a solo workspace and that
    `receipt.write_from_run` produces the same fields as an `ai_team` run.
  - **Definition of done:** a recorded solo workspace fixture scores through all sixteen
    checks with no special-casing and no crash.
  - _Requirements: R2.4, R2.5_

- [ ] **4.3 First live solo run** *(human-triggered, ≤ $3)*
  - Run `todo-api-beginner` once. Commit the trace as a fixture (redacted via
    `python -m evals.cli fixtures redact`).
  - **Definition of done:** trace committed; FM incidence recorded; cost and wall-clock logged
    in the journal entry.
  - _Requirements: R2.3, R2.4_

- [x] **4.4 `harnessed_solo` arm — the missing middle rung**
  - Implement `role_decomposition` as an ablatable component: the full harness (guardrails,
    smoke gate, constraints pinning, lessons, acceptance list) driving **one generalist
    agent** instead of nine roles. Register it under its own arm id `harnessed_solo` as an
    alias of `ai_team_ablated:role_decomposition`.
  - **Definition of done:** unit test asserts one agent, zero subagent spans, and every
    harness component still active in `ArmSpec.harness_components`.
  - _Requirements: R4.1, R4.2, R4.3_

- [ ] **4.5 First live `harnessed_solo` run** *(human-triggered, ≤ $6)*
  - Same scenario as 4.3. Commit the redacted trace.
  - **Definition of done:** with 4.3 and the existing `ai_team` traces in hand, both
    comparisons are computable — `solo → harnessed_solo` (what the harness buys) and
    `harnessed_solo → ai_team` (what decomposition buys). Record both in the journal, and
    record them even if the second delta is zero or negative. Especially then.
  - _Requirements: R4.4, R4.5_

---

## Phase 5 — Reference-harness arm

- [x] **5.1 Vendor the quickstart**
  - Copy `anthropics/claude-quickstarts/autonomous-coding` to
    `evals/arms/vendor/autonomous_coding/` at a pinned sha. Write `PROVENANCE.md` with URL,
    sha, MIT licence text reference, retrieval date, and an explicit "do not edit" note.
  - **Definition of done:** a test asserts the vendored tree's hash matches a recorded manifest,
    so accidental edits fail CI.
  - _Requirements: R3.1, R3.2_

- [x] **5.2 Implement `ReferenceArm`**
  - Scenario → `app_spec.txt`; `max_features` default 25; external wall-clock and iteration
    ceilings; stdout capture. Every adaptation recorded as a `Divergence`.
  - Handle unavailability (`claude` CLI, node, network) as `status = "unavailable"`.
  - **Definition of done:** unit tests with a stubbed subprocess cover the happy path, the
    ceiling kill, and each unavailability cause.
  - _Requirements: R3.2, R3.3, R3.4, R3.6_

- [x] **5.3 Trace assembly from reference artifacts**
  - Parse `[Tool: …]` / `[Done]` / `[BLOCKED]` markers, `feature_list.json`,
    `claude-progress.txt`, and git history into spans. Record every missing stream in
    `trace.warnings[]` rather than fabricating it.
  - **Definition of done:** a captured stdout fixture yields a Trace whose warnings explicitly
    name the absent cost and guardrail streams.
  - _Requirements: R3.5_

- [ ] **5.4 First live reference run** *(human-triggered, ≤ $8)*
  - Same scenario as 4.3. Commit the redacted trace as a fixture.
  - **Definition of done:** trace committed; the FM-007 positive (no internal spend ceiling) is
    recorded as expected rather than filed as an adapter bug.
  - _Requirements: R3.4, R3.5_

---

## Phase 6 — Ladder report and claim discipline (free)

- [x] **6.1 `render_ladder`**
  - Implement per design §4.7: JSON first, Markdown rendered from that JSON, per-arm `n`,
    means with CIs, FM incidence, smoke pass rate, accepted-change rate, demotion rate.
  - **Definition of done:** golden-file test on the three committed fixture traces; a test
    asserts the Markdown numbers are read from the JSON, not recomputed.
  - _Requirements: R5.1, R5.5_

- [x] **6.2 Stamps and refusals**
  - Implement `MIXED-MODEL` and `UNDERPOWERED` stamping and the flag-gated refusals.
  - **Definition of done:** tests assert refusal without flags, stamping with them, and that the
    stamp text appears in both JSON and Markdown outputs.
  - _Requirements: R5.2, R5.3_

- [x] **6.3 Per-phase cost, QA rate, and staleness columns**
  - Add per-phase cost and wall-clock breakdown per arm from `logs/costs.jsonl`;
    `qa_false_negative_rate` beside `smoke_pass_rate`; and the `STALE` /
    `never measured` markers on ablation rows.
  - Implement `cost_per_fm_avoided` as optional, stamped
    `DERIVED — RATIO OF TWO NOISY ESTIMATES`, suppressed below n=5.
  - **Definition of done:** golden-file test covers a stale row, a never-measured row, and a
    suppressed ratio; no ablation row can render a zero delta for a component that was never
    measured.
  - _Requirements: R5.1a, R5.1b, R15.2, R15.4, R16.5_

- [x] **6.4 Divergence surfacing**
  - Render each arm's `source_ref` and full divergence list beneath the table.
  - **Definition of done:** the reference arm's row shows `max_features=25` and every other
    adaptation; a divergence added in code appears in the report without a report change.
    Every arm's row notes that it received a full scenario contract rather than a thin brief
    (design §9.4).
  - _Requirements: R5.4_

---

## Phase 7 — UI verification

- [x] **7.1 Scenario `ui` block**
  - Extend the scenario contract schema with an optional `ui` block
    (`base_url`, `boot_cmd`, `ready_path`, `viewport`). Populate it for `todo-api-beginner`.
  - **Definition of done:** existing scenarios without the block still validate.
  - _Requirements: R13.6_

- [x] **7.2 `run_ui_smoke`**
  - Implement `src/ai_team/tools/ui_smoke_tools.py` per design §4.5 with Playwright, headless
    Chromium, fixed viewport. Write `docs/ui_smoke_results.json` and screenshots to
    `docs/verification/<item_id>/`. Never probe a foreign service.
  - Console and page errors fail a step deterministically.
  - **Definition of done:** integration test against a fixture static page with a deliberate
    console error fails the step with no model call; a UI-less scenario returns `skipped`.
  - _Requirements: R13.1, R13.2, R13.3, R13.4, R13.6_

- [x] **7.3 Expose as an MCP tool and extend FM-006**
  - Register `run_ui_smoke` on `ai_team_tools`, QA allow-list only. Extend
    `CHK-runtime-smoke-present` so UI-bearing scenarios require a UI smoke result and a
    backend-only probe does not satisfy them.
  - **Definition of done:** a fixture trace with only an HTTP probe on a UI scenario now fails
    the check; the same trace on a non-UI scenario still passes.
  - _Requirements: R13.5, R13.8_

- [x] **7.4 Design rubric document**
  - Write `docs/UI_QUALITY_RUBRIC.md`: four criteria (design quality, originality, craft,
    functionality), calibration examples at each level, and an explicit note that criterion
    wording steers output toward convergence. State plainly that it is advisory until it clears
    the eval-harness alignment bar.
  - **Definition of done:** the document exists, is linked from `docs/EVAL_METHODOLOGY.md`, and
    no gate reads it.
  - _Requirements: R13.7_

---

## Phase 8 — Multi-session continuation

- [x] **8.1 `SessionRecord` and the session log**
  - Implement the model and `logs/sessions.jsonl` writing; add `session_start` / `session_end` /
    `regression_check` span types to Trace assembly.
  - **Definition of done:** round-trip test; Trace assembly reads the new log without breaking
    on its absence.
  - _Requirements: R8.3_

- [x] **8.2 Session loop**
  - Implement `run_sessions` per design §4.3. Fresh context per session from the four files.
    Terminate on all-pass, `max_sessions`, spend, wall-clock, or `no_progress_sessions`.
  - Off by default; requires explicit `--max-sessions` and a total budget.
  - **Definition of done:** integration test over a stubbed backend runs three sessions and
    exercises each termination condition in its own test.
  - _Requirements: R8.1, R8.2, R8.4, R8.6_

- [x] **8.3 Commit discipline**
  - Require a commit at session end; mark `dirty_exit` otherwise and feed FM-012.
  - **Definition of done:** a stubbed session leaving uncommitted changes produces
    `status = "dirty_exit"` and the existing FM-012 check fires on its trace.
  - _Requirements: R8.5_

- [x] **8.4 Regression verification**
  - Implement the R9 policy: highest-priority passing item plus one seeded-random item not
    verified in the last `m` sessions. Demote on failure and prioritize demoted items.
  - **Definition of done:** integration test injects a regression between sessions and asserts
    demotion → prioritization → re-pass, with `demotion_rate` surfacing in the report.
  - _Requirements: R9.1, R9.2, R9.3, R9.4_

---

## Phase 9 — Contract negotiation

- [x] **9.1 Contract model and store**
  - Implement `src/ai_team/harness/contracts.py` and the `docs/contracts/<item_id>.json` format.
  - **Definition of done:** round-trip tests; round ceiling enforced at the store layer.
  - _Requirements: R11.1, R11.3_

- [x] **9.2 Negotiation step**
  - Developer writes the contract; QA validates against the acceptance item and returns
    `accepted` / `rejected` with reasons. File-based handoff only.
  - **Definition of done:** integration test with a stubbed QA rejecting twice asserts
    escalation at round 3 through `flows/error_handling.py`, not a fourth round.
  - _Requirements: R11.2, R11.3_

- [x] **9.3 Gate implementation on an accepted contract**
  - PreToolUse hook denies writes to `src/` for an item without an accepted contract, when the
    component is enabled. No-op when ablated.
  - **Definition of done:** adversarial tests for enabled-deny and ablated-allow; verification
    scores against `testable_behaviors[]`.
  - _Requirements: R11.4, R11.5, R11.6_

---

## Phase 10 — Default-deny bash

- [x] **10.1 Command extraction with fail-safe semantics**
  - Implement the parser. Block on anything it cannot decompose.
  - **Definition of done:** one unit test per construct in R14.4 — `&&`, `||`, `;`, pipes,
    `$(…)`, backticks, `env VAR=x cmd`, `xargs`, `nohup`, `timeout`, absolute paths,
    `git -c core.hooksPath=…`, `git -c core.pager=…`, unclosed quotes — each asserting the
    expected allow or block, with undecomposable input always blocked.
  - `tests/unit/backends/test_claude_sdk_security_hook_adversarial.py::test_known_bypasses_are_not_caught_today`
    already documents the denylist's gaps and names this requirement. **Invert it here**
    (R17.7) rather than deleting it — the diff should show the bypasses closing.
  - Also decide on `AI_TEAM_DENY_NATIVE_TOOLS` case-sensitivity: the switch matches
    lowercase only, so `TRUE` fails **open**. One-line fix (`.strip().lower()`), with the
    documenting test inverted in the same commit.
  - _Requirements: R14.3, R14.4, R17.7_

- [x] **10.2 Per-role allowlists**
  - Define them in `tools/permissions.py` beside the tool allow-lists. Evaluate the allowlist
    **after** the existing deny patterns.
  - **Definition of done:** a developer-role command permitted for developers is blocked for the
    architect role; existing deny patterns still fire first. **Cover first (R17.5):**
    `tools/permissions.py` sits at 35% branch — add a guard asserting every role's allow-list
    references only registered tool names, which is how a typo'd MCP tool name (silently
    granting nothing) would otherwise ship.
  - _Requirements: R14.1, R14.2, R17.5_

- [x] **10.3 False-positive budget**
  - Run the guardrail corpus with the allowlist active; measure the FP delta against the current
    budget. Keep the allowlist **disabled by default** unless `CHK-guardrail-fp-budget` holds.
  - **Definition of done:** corpus numbers recorded in the journal; the default-on decision is
    made from that measurement, not from preference.
  - _Requirements: R14.5, R14.6_

- [x] **10.4 Confirm no settings-file confinement**
  - Assert in a test that no `.claude_settings.json` is written into a generated workspace;
    confinement stays hook-enforced.
  - **Definition of done:** test present and passing.
  - _Requirements: R14.7_

---

## Phase 11 — Ablation sweep and writeup

- [x] **11.1 `AblatedArm` and the component registry**
  - Implement config-driven ablation for the closed set in R4.1. Fail loudly on a component
    that cannot be disabled by config.
  - **Definition of done:** each named component can be disabled and the active set is recorded
    in `ArmSpec.harness_components` and in trace provenance.
  - _Requirements: R4.1, R4.2, R4.3_

- [x] **11.2 Ablation result store and staleness**
  - Persist each result to `evals/results/ablations/<component>.json` with `model_id`,
    `model_snapshot_date`, `measured_at`, `scenario_id`, `n`, delta and CI.
  - Implement `python -m evals.cli ablation status` listing every component as
    `current` | `STALE` | `never measured`.
  - Staleness never fails the gate (R15.5).
  - **Definition of done:** changing the configured default model flips every prior result to
    `STALE` without re-running anything; a component with no result reads `never measured`.
  - _Requirements: R15.1, R15.2, R15.3, R15.4, R15.5_

- [x] **11.3 Ablation deltas in the report**
  - Render deltas against the `ai_team` control with CIs, plus the
    `components with no measured effect at this n` section.
  - **Definition of done:** golden-file test on synthetic traces; a zero-delta component lands
    in the named section rather than being silently omitted.
  - _Requirements: R4.4, R4.5, R4.6_

- [ ] **11.4 Full ladder sweep** *(human-triggered, ≤ $25)*
  - `todo-api-beginner`, n ≥ 3 per arm, fixed model: `solo`, `harnessed_solo`, `reference`,
    `ai_team`, plus the ablation with the strongest prior (`smoke_gate`).
  - **Definition of done:** all traces committed as fixtures; ladder report rendered; every
    table carries its stamps honestly.
  - _Requirements: R5.1–R5.5, R4.4_

- [x] **11.5 Journal entry and taxonomy update**
  - Write `docs/journal/<date>.md` with commit references per house style. Record what each
    arm cost, what each ablation changed, and — explicitly — any component that bought nothing.
  - Update `docs/posts/failure-taxonomy.md` with narrative sections for **FM-011 through
    FM-017** — not just this spec's four. The essay documents ten modes; the YAML has
    thirteen as of taxonomy 1.1.0, so FM-011/012/013 are already undocumented drift that this
    task inherits.
  - **Headline-stat consequence — decide deliberately, do not discover at publish time.** The
    essay's punchline is "only one of the ten was caused by an LLM being dumb," and it is also
    the flagship post's alternate title. FM-014, FM-015 and FM-017 are all `layer: model`, so
    the ratio becomes **four of seventeen**. The honest framing is that the model-layer count
    rose because the instruments improved — these are failures that were always happening and
    were previously invisible — not because the model got worse. Rewrite the punchline; do not
    quietly keep the old number beside a seventeen-row table.
  - **Definition of done:** journal entry follows the existing entry shape; the taxonomy essay
    and `failure_modes.yaml` agree on all seventeen modes; the layer ratio stated in the essay
    matches a count computed from the YAML rather than typed by hand.
  - _Requirements: R4.5, R7.1, R10.1, R12.1, R16.1_

---

- [x] **11.6 Re-ratchet the coverage floor**
  - Recompute the combined `src/ai_team` + `evals` figure on macOS and in CI, then raise
    `fail_under` in `pyproject.toml` to the measured value less the observed
    macOS/ubuntu branch variance (~6pt). Record the new value and its basis in the comment
    block that already tracks this history.
  - **Definition of done:** floor raised; the gate fails on a deliberately reverted test
    file; no module added by this spec is below the bar of R17.6.
  - _Requirements: R17.8_

---

## Minimum defensible slice

If the full plan is too long: **Phases 0–2, plus Phase 4, plus Phase 6.**

The acceptance list with a monotonic check, three new deterministic failure modes scored
retroactively over the existing corpus, the `solo` and `harnessed_solo` control arms, and a
report that refuses to overclaim. That is a coherent result on its own — "here is what the
harness buys, what the nine-role team buys on top of it, and here are the caveats, enforced
in code." Everything past it is refinement.

If even that is too long, task 4.5 is the one to keep. Two runs and an existing `ai_team`
trace give you the only number in this spec that could change what you build next.

The session loop (Phase 8) without Phase 1 is not worth building: resumption with no durable,
protected checklist is just a longer run.
