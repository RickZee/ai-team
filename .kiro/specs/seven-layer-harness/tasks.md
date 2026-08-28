# Implementation Plan — Seven-Layer Harness

**Spec ID:** `seven-layer-harness`
**Requirements:** [`requirements.md`](./requirements.md) · **Design:** [`design.md`](./design.md)

---

## How to execute this plan

- Work **one task at a time, in order**. Each task is sized to be completable and
  reviewable on its own; do not batch phases.
- Every task lists its **Definition of done**. Do not mark a task complete until each
  bullet is literally true.
- Run `uv run ruff check . && uv run ruff format --check . && uv run mypy src/` before
  marking any task complete (CI `lint` job).
- New eval checks also need `uv run mypy evals/` and
  `uv run pytest tests/unit/evals tests/unit/tools tests/unit/harness -q`.
- **Do not edit `src/ai_team/flows/main_flow.py` before Phase 4** except if a task
  explicitly says so. That file produced `FM-002`; the self-listen meta-test must
  stay green.
- Phases 0–2 are additive. Phase 3 is the cutover: public write/delete/shell
  entrypoints must go through the bus.
- Do not spend money. No task in this spec requires a live model call.

---

## Phase 0 — Scaffolding, taxonomy, docs stub

- [ ] **0.1 Package skeleton**
  - Create `src/ai_team/harness/` with `__init__.py`, `context.py`, `receipt.py`,
    `router.py` (stubs that raise `NotImplementedError` or return empty
    structures — enough to import).
  - Create `src/ai_team/tools/bus.py` and `src/ai_team/tools/kinds.py` (types
    only: `ToolKind`, `RiskClass`, `ObservationCode`, `ToolSpec`,
    `ToolRequest`, `ToolObservation` per design §3.1).
  - Create `src/ai_team/tools/draft.py` stub.
  - **Definition of done:** `uv run python -c "from ai_team.tools.bus import ToolObservation; from ai_team.harness import receipt"` succeeds; mypy clean on the new modules.
  - _Requirements: R1, R4, R20_

- [ ] **0.2 Taxonomy `harness_layer` + FM-011…013 shells**
  - Extend `evals/taxonomy/loader.py`: optional `harness_layer` enum
    `tools | verification | context | guardrails | observability | routing | feedback`.
  - Set `harness_layer` on FM-001…010 per requirements layer map; omit on
    FM-002 and FM-009.
  - Add FM-011 `constraint_drop`, FM-012 `uncommitted_write`, FM-013
    `lesson_ineffective` with full definitions, `detection: check`,
    `implemented_by` naming the future checks, `introduced_in: "1.1.0"`.
    Leave checks unimplemented; registry validation will fail until Phase 1.5 /
    2.3 / 9.3 — that failing test is the checklist, same pattern as
    eval-harness 3.2. **Alternatively** set `implemented_by: []` and
    `detection: check` only after the check exists if current loader treats
    empty `implemented_by` as hard error — follow existing loader rules; do
    not weaken them.
  - Bump taxonomy `version` to `1.1.0`.
  - Extend loader unit tests for the new field (present, absent, invalid enum).
  - Update `COVERAGE.md` generation to include a Harness layer column.
  - **Definition of done:** taxonomy loads; invalid `harness_layer` raises;
    FM-001…010 keep their original `layer` values; version is `1.1.0`.
  - _Requirements: R2_

- [ ] **0.3 `docs/HARNESS.md` stub**
  - Write `docs/HARNESS.md` with the seven-layer table (post requirement, current
    module, FM ids, check ids, status `planned`). Mark each layer
    `instrumented | enforced | closed-loop` as `planned`.
  - Link from `docs/ARCHITECTURE.md` (tools / guardrails / memory) and from
    `docs/posts/failure-taxonomy.md`.
  - **Definition of done:** file exists; links resolve; no duplicated seven-layer
    essay inside `ARCHITECTURE.md`.
  - _Requirements: R3, R19_

---

## Phase 1 — ToolBus (stops escalation)

- [ ] **1.1 ToolBus invoke pipeline**
  - Implement `ToolBus.register` and `ToolBus.invoke` per design §4.1:
    lookup → schema validate → permission → kind branch (read executes;
    write/irreversible still call handler but Phase 2 will change write) →
    cap summary → audit + spans.
  - For this task, `write` may still execute live **if** the handler does;
    document that Phase 2 flips it. Permission deny and schema fail must not
    execute.
  - Process-local bus via `get_bus()` / `reset_bus()` for tests (not a
    cross-run singleton that can leak — remember `FM-007` / SpendGuard).
  - **Definition of done:** unit tests for `ok`, `schema_invalid`,
    `permission_denied`, `not_found`; summary truncated to 2,000 chars with
    artifact spill; no network.
  - _Requirements: R4, R6_

- [ ] **1.2 Register existing file/code/git/test handlers**
  - Move live I/O in `file_tools`, `code_tools`, `git_tools` behind
    module-private impls. Register specs with `kind` / `risk_class`
    (reads = `read`/`low`; writes = `write`/`write`; `delete_file` =
    `irreversible`/`irreversible`; shell = `irreversible` or `write` with
    a conservative default of `irreversible` for `execute_shell`).
  - Public `@tool` wrappers still call impls **directly** in this task so
    existing tests stay green. They get a `# TODO bus cutover (task 3.1)`
    comment.
  - **Definition of done:** registry contains the public tools used by
    developers/QA; unit test lists expected names; existing
    `tests/unit/` tool tests still pass.
  - _Requirements: R4, R5.1_

- [ ] **1.3 Structured observation adapters (optional stringify)**
  - Add `observation_to_agent_text(obs: ToolObservation) -> str` that
    returns `summary` plus artifact refs — never raw stdout as the only
    content.
  - **Definition of done:** test that a handler returning 10k of stdout
    yields ≤ 2,000 char agent text and an artifact ref.
  - _Requirements: R6_

- [ ] **1.4 Span emission compatible with eval traces**
  - Emit structures `TraceBuilder` / audit parsers can read (`tool_use` /
    `tool_result` with `kind`, `risk_class`, `ok`, `code`). Prefer the
    existing audit JSONL shape plus new fields.
  - **Definition of done:** a bus invoke produces a parseable audit line;
    `parse_audit_jsonl` does not warn-and-drop it.
  - _Requirements: R4.2, R7.3_

- [ ] **1.5 `CHK-tool-call-emitted` still green**
  - Re-run eval check fixtures for FM-001. Adjust the check only if payload
    field names changed; do not weaken the predicate.
  - **Definition of done:** existing FM-001 fail/pass/na fixtures pass.
  - _Requirements: R7.3_

---

## Phase 2 — Draft-commit and irreversible gates

- [ ] **2.1 Draft area and `commit_write`**
  - Implement `tools/draft.py`: write to
    `workspace/.harness/drafts/<draft_id>`; `commit_write` validates path
    and content then `os.replace` into the live workspace.
  - Register `commit_write` as `kind: write` (the promotion is the live
    write).
  - Flip write handlers registered on the bus to draft-only (`code:
    drafted`).
  - Setting `AI_TEAM_DRAFT_WRITES` default on; document the escape hatch
    for tests not yet migrated.
  - **Definition of done:** unit test: `write_file` via bus does not create
    the live `src/` file; `commit_write` does; path traversal on commit
    raises/returns `validation_failed`.
  - _Requirements: R5.2, R5.3_

- [ ] **2.2 Irreversible policy**
  - Catalog: `delete_file`, lockfile/`requirements.txt` overwrite, shell,
    compose volume wipes, git push if present.
  - Default profiles deny; require `profile.metadata.allow_irreversible`
    or a human-interrupt token on the request.
  - `delete_file(..., confirm=True)` from the model SHALL NOT suffice
    (R5.6).
  - **Definition of done:** unit tests: gated without policy; executes with
    policy; `confirm=true` alone still `gated`.
  - _Requirements: R5.4, R5.5, R5.6_

- [ ] **2.3 `CHK-draft-commit` (FM-012)**
  - Implement the check; three fixtures; register; taxonomy
    `implemented_by` complete; mutation test.
  - **Definition of done:** `validate_registry_against_taxonomy()` includes
    FM-012; fail/pass/na tests green.
  - _Requirements: R5.7, R2.4_

- [ ] **2.4 Adversarial bus tests**
  - Path traversal, `.env` write, injection-shaped shell args,
    `confirm=true` delete without policy.
  - **Definition of done:** `tests/unit/tools/test_bus_adversarial.py` passes.
  - _Requirements: R20.3_

---

## Phase 3 — Cutover: no backend bypasses the bus

- [ ] **3.1 Public wrappers call `ToolBus.invoke` only**
  - CrewAI `@tool` functions, raw functions used by tests (keep a
    `testing=True` impl hook if needed), and any `get_*_tools()` lists
    go through the bus.
  - Meta-test: public `write_file` / `delete_file` / `execute_shell` must
    call `ToolBus.invoke` (inspect wrapping or force impls to be
    `_private`).
  - Migrate existing unit tests that monkeypatched impls.
  - **Definition of done:** meta-test green; `tests/unit/` tools green;
    salvage paths (if any) call the bus with `agent_role="_harness"`.
  - _Requirements: R1.2, R4.5, R7.2, R20.5_

- [ ] **3.2 LangChain adapter**
  - `crewai_tool_to_langchain` / role tool getters invoke the bus, not a
    second copy of the handler.
  - **Definition of done:** LangGraph tool unit tests pass; one test
    asserts a write is `drafted` not live.
  - _Requirements: R4.5_

- [ ] **3.3 Claude SDK MCP + PreToolUse**
  - MCP handlers call `ToolBus.invoke`.
  - PreToolUse: native `Write`/`Bash` mapped or denied. Test the deny
    path with the existing hook fixture style
    (`tests/unit/backends/test_claude_agent_sdk_hooks.py`).
  - **Definition of done:** bypass attempt denied; MCP write is drafted.
  - _Requirements: R4.6, R20.3_

- [ ] **3.4 FM-001 bus invariant hook**
  - Shared phase-end helper: fenced code + zero write observations →
    error span `fm_id=FM-001`. Wire into the common post-phase path if
    one exists; otherwise LangGraph + SDK first and CrewAI in Phase 4.
  - **Definition of done:** unit test with a fake phase payload records
    the span; salvage uses the bus.
  - _Requirements: R7.1, R7.2_

---

## Phase 4 — Verification on every backend

- [ ] **4.1 Cheap vs strong split**
  - Document and implement a `VerifierKind` or reuse task types: cheap
    path calls ruff/pytest/smoke without the architect model.
  - QA tools that already run pytest stay cheap. Architecture guardrail
    stays strong.
  - **Definition of done:** unit test or monkeypatch shows cheap path
    does not instantiate the planning model.
  - _Requirements: R8_

- [ ] **4.2 CrewAI smoke node**
  - After testing in `AITeamFlow`, call `run_app_smoke`; on failure route
    to retry development with traceback payload; bound by existing retry
    cap. **Listener names must not match their trigger** (`on_smoke` /
    `route_after_smoke`). Confirm
    `tests/unit/flows/test_flow_wiring.py` still passes.
  - CrewAI is no longer "post-run only" for smoke.
  - **Definition of done:** flow introspection finds the smoke route;
    mocked fail → retry; mocked pass → deployment; self-listen meta-test
    green.
  - _Requirements: R1.4, R9_

- [ ] **4.3 `cost_per_accepted_change` on run metadata**
  - Compute per design / R10; attach to `RunMetadata.extra` or the
    receipt stub until Phase 7 lands.
  - **Definition of done:** unit test for zero accepts (denominator 1),
    one accept, and rejected-smoke run not counting as accepted.
  - _Requirements: R10_

- [ ] **4.4 `CHK-runtime-smoke-present` vs CrewAI**
  - Fixture: complete CrewAI-shaped trace without `smoke_probe` → fail.
  - **Definition of done:** check fails that fixture; LangGraph pass
    fixture still passes.
  - _Requirements: R9.4_

---

## Phase 5 — Pinned constraints and compaction policy

- [ ] **5.1 Three-file contract I/O**
  - Implement `harness/context.py`: load/append `CONSTRAINTS.md`, write
    `STATE.md` (last N phase facts, no LLM), generate `LESSONS.md` from
    store (may be empty until Phase 9).
  - Create files at run start if missing (template + optional intake
    canary when `AI_TEAM_CONSTRAINT_CANARY` or eval scenario says so).
  - **Definition of done:** unit tests for parse/serialize round-trip;
    STATE.md retains only last N phases.
  - _Requirements: R11_

- [ ] **5.2 Inject constraints before first tool call**
  - Wire ConstraintLoader into CrewAI crew prompts, LangGraph
    `build_system_prompt`, and Claude SDK orchestrator / `CLAUDE.md`
    equivalent so the full file is present at every phase start.
  - Record `constraint_ids` + `constraint_sha256` on `phase_start`
    payload (or a `context_inject` span).
  - **Definition of done:** unit tests per backend prompt builder (mock)
    assert canary text in the bundle; trace payload lists the id.
  - _Requirements: R11.2, R12.4_

- [ ] **5.3 `CHK-constraint-survival` (FM-011)**
  - Implement check; three fixtures; mutation: drop id at testing
    phase_start → fail.
  - **Definition of done:** registry complete for FM-011; tests green.
  - _Requirements: R12, R2.4_

- [ ] **5.4 Compaction policy documented and enforced in code**
  - If a summarizer exists, it must take pinned constraint ids as
    untouchable. If none exists, write the policy in `docs/HARNESS.md`
    and a unit test that `ConstraintLoader.pinned_text()` is unchanged
    after a dummy summarizer that empties other context.
  - **Definition of done:** `HARNESS.md` context layer status at least
    `enforced` for pinning; test proves pin survival.
  - _Requirements: R11.4_

---

## Phase 6 — Risk-class guardrails and evidence

- [ ] **6.1 `risk_class` on profiles and tools**
  - Extend `TeamProfile` (optional field, default `write`).
  - Set `smoke`/`prototype` default `write`; document
    `customer-visible` for production-like profiles.
  - **Definition of done:** `test_team_profile.py` covers missing
    (default) and explicit values; YAML for `smoke` updated if needed.
  - _Requirements: R13.1, R13.3_

- [ ] **6.2 Guardrail dispatch by class**
  - Map existing guardrails per design §4.5. Operational spend ceiling
    remains global.
  - **Definition of done:** unit test: `low` does not invoke scope
    guardrail; `customer-visible` does. Guardrail corpus eval still
    `$0` (do not regress eval-harness R6).
  - _Requirements: R13.2, R13.4_

- [ ] **6.3 Evidence bundle structure**
  - Pydantic model for policy version, checks fired, overrides,
    outcomes. Fill from `TeamMonitor` + bus denials even if receipt
    writer is still Phase 7.
  - **Definition of done:** unit test with a fake monitor buffer
    produces a bundle with one override listed (not dropped).
  - _Requirements: R14_

---

## Phase 7 — Change receipt and drift

- [ ] **7.1 `ChangeReceipt` writer**
  - Implement `harness/receipt.py` and write
    `output/runs/<id>/receipt.json` + `receipt.md` from the existing
    results writer path. Include fields in R15.1.
  - All three backends, including abort/kill, including SDK.
  - **Definition of done:** integration-style unit test with a temp
    output dir; SDK path test if a writer hook exists; missing smoke
    still emits a receipt.
  - _Requirements: R15_

- [ ] **7.2 Dashboard / API reads the file**
  - `GET /api/runs/<id>/receipt` returns the JSON file. UI: a Receipt
    panel or compare-tab link. Live stream is not the source of truth
    for cost/files/smoke.
  - Verify in the browser if the dashboard is running; otherwise
    pytest + note what was not clicked.
  - **Definition of done:** API test with a fixture receipt file;
    frontend type + render for the main fields.
  - _Requirements: R15.4_

- [ ] **7.3 `CHK-metric-source-agreement` vs receipt**
  - Extend or companion-assert receipt file count / cost vs artifacts.
  - **Definition of done:** fixture where events lie and receipt
    matches artifacts → check uses receipt (or documents the field).
  - _Requirements: R15.5, FM-008_

- [ ] **7.4 Drift CLI**
  - `python -m evals.cli drift` (or `evals/drift.py` wired to CLI):
    FM hits, smoke pass, files, cost, cost_per_accepted_change over
    two windows. Warn-only. `$0`.
  - **Definition of done:** unit test on fixture receipts; no network.
  - _Requirements: R16_

---

## Phase 8 — Task-typed routing

- [ ] **8.1 `task_routes.yaml` + resolver**
  - Implement `harness/router.py::resolve`. Sentinel `deterministic`
    for `mechanical_check`.
  - Same-model profiles override and set `same_model` on receipt
    routes.
  - **Definition of done:** unit tests for env lookup, missing type
    fallback + warning, same_model override.
  - _Requirements: R17.1–R17.3_

- [ ] **8.2 Wire mechanical_check, plan, generate**
  - Cheap verifiers use `mechanical_check`. Planning/architect uses
    `plan`. Generation keeps role models via `generate` default.
  - Log `task_type` + model id onto the receipt (per phase acceptable
    for v1).
  - **Definition of done:** one test shows pytest path does not resolve
    to the architect model id.
  - _Requirements: R17.4, R17.5, R8.2_

---

## Phase 9 — Closed lessons loop

- [ ] **9.1 Structured lesson on smoke/check fail**
  - Deterministic template `{fm_id, constraint, evidence_span}` into
    the lessons store + `LESSONS.md`. Dedup by `fm_id` + normalized
    text.
  - **Definition of done:** unit tests: write, dedup, no-throw if
    store fails (log only).
  - _Requirements: R18.1, R18.2_

- [ ] **9.2 Inject into `CONSTRAINTS.md` and next run**
  - Active lessons appended as pinned `CST-lesson-*`. Next run loader
    includes them before first tool call (reuse Phase 5 injector).
  - **Definition of done:** two-run unit test (temp workspace): fail →
    file contains lesson → second load sees it.
  - _Requirements: R18.3, R18.7_

- [ ] **9.3 Effectiveness tracking + `CHK-lesson-effectiveness`**
  - Recurrence window; `effective` / `ineffective` / `escalated`.
  - Implement FM-013 check; three fixtures; registry complete.
  - **Definition of done:** ineffective without escalate fails the
    check; escalate passes; `docs/HARNESS.md` feedback layer may be
    marked `closed-loop`.
  - _Requirements: R18.4–R18.6, R2.4_

---

## Phase 10 — Docs close-out and instrumentation bar

- [ ] **10.1 Finish `docs/HARNESS.md`**
  - Every layer: module path, FMs, checks, status
    (`instrumented` / `enforced` / `closed-loop`) matching what
    actually shipped.
  - Honest: if Phase 8 stubs remain, say so. Feedback is
    `closed-loop` only if 9.3 shipped.
  - Update `docs/SELF_IMPROVEMENT.md` to point at the closed loop
    without claiming magic.
  - **Definition of done:** every command or module path in the doc
    exists; R19.3 table filled.
  - _Requirements: R3, R19_

- [ ] **10.2 Taxonomy coverage regen**
  - `python -m evals.cli taxonomy coverage` (or existing command)
    shows FM-011…013 covered. Cross-links in the taxonomy essay.
  - **Definition of done:** `COVERAGE.md` committed with harness
    layer column and new FMs.
  - _Requirements: R2.6_

- [ ] **10.3 Quality gate sweep**
  - `uv run ruff check . && uv run mypy src/ evals/ && uv run pytest tests/unit/tools tests/unit/harness tests/unit/memory tests/unit/evals tests/unit/flows -q`
  - **Definition of done:** all green; no `print()` in new modules.
  - _Requirements: R20_

---

## Sequencing summary

```
Phase 0  scaffolding + taxonomy + HARNESS stub     additive, ~3h
Phase 1  ToolBus + observations + spans            additive, ~1d     ◄── freeze observation schema
Phase 2  draft-commit + irreversible + FM-012      additive, ~1d     ◄── stops live escalation
Phase 3  cutover all backends                      first hard flip, ~1d
Phase 4  verification + CrewAI smoke + cost        ~1d               ◄── touches main_flow.py
Phase 5  pinned constraints + FM-011               ~1d               ◄── highest leverage with 1–3
Phase 6  risk_class + evidence                     ~4h
Phase 7  receipt + dashboard + drift               ~1d
Phase 8  task-typed routing                        ~4h               (when the bill hurts)
Phase 9  closed lessons loop + FM-013              ~1d               (when the same FM repeats)
Phase 10 docs + coverage + lint                    ~3h
```

**If time is short, the minimum defensible slice is Phases 0–3 plus Phase 5.**
A bus every backend must use, draft-commit on writes, and pinned
`CONSTRAINTS.md` the summarizer cannot drop. Receipts, routing, and lessons
become measurable once those two are on the path every engine shares.

You do not need all seven layers polished to ship a demo. You need all seven
**instrumented** (Phase 10 status table) before treating any backend as
"the one."
