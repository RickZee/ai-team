# 2026-09-17 — every agent write was a draft, and nothing ever saved one

**Session:** 2026-09-17. Agent-assisted (Claude Opus 5).
**Base:** `66c0c4a` on `feat/course-v2` (not pushed).
**Preceded by** [2026-09-16 (course v2)](2026-09-16-course-v2.md) §8.

Morning (§1–5): agent writes never reached the workspace. Afternoon (§6–9): the first live
LangGraph run finished — and showed three more harness layers underneath. Evening and night (§10–15):
those three fixed, verified live, the reporting bugs behind the numbers closed, the Cursor
test skill taught to build rather than only walk — and that skill immediately finding two
regressions from the same afternoon plus a gate that cannot fail.

## 1. Where it came from

The second `/test-course` run (`course/testing/runs/2026-09-16-stranger-2/`) was the first
live LangGraph run after the guardrail-loop fix (`5b131bd`). It had **zero** relevance
failures and no nested workspace — the fix held — and still did not finish in 15 minutes.
The report blamed "QA rewrite / invalid absolute draft path". The log said something else:

```
file_writer  path=calc.py
draft_staged intended_path=calc.py
toolbus_span code=drafted  "Drafted calc.py; call commit_write to promote."
```

Twelve writes, twelve drafts, **zero commits** in the whole run.

## 2. Root cause — three layers

| # | Defect | Since |
| --- | --- | --- |
| 1 | Draft-then-commit (seven-layer-harness R5.3) is on by default, but **no backend gives agents `commit_write`** and no harness code calls it. Agent writes never reached the workspace; only `salvage_write` (auto-commit) and the Claude SDK's native tools did. | 2026-08-28 (`ef36e39`) |
| 2 | The **QA role had no `file_writer`**, though `agents.yaml` and the LangGraph testing prompt both tell it to use one. Its calls failed with "file_writer is not a valid tool". | long-standing |
| 3 | The unit suite's autouse fixture sets `AI_TEAM_DRAFT_WRITES=0`, so **tests ran a different program** from production, and stayed green. | 2026-08-28 |

Plus: `_snapshot_workspace_files` counted `.harness/drafts/*` as generated files, and agents
that saw a draft ref tried to write *to* `.harness/drafts/<id>`.

This likely explains the 2026-09-13 "pytest exit 5 with test_calc.py right there", the
CrewAI "still in testing at 15 min" (2026-09-16), and part of why live LangGraph never
finished.

## 3. Fix

- `tools/draft.commit_pending_drafts(phase=)` — promotes every staged draft through the bus
  as `commit_write` with `agent_role="_harness"` (audited); newest draft per path wins.
- Called when a phase's guardrails pass: each LangGraph phase node (incl. the testing
  re-prompt), CrewAI after development and before the testing crew's pytest.
  Guardrail-terminal phases do **not** commit.
- `get_qa_tools()` includes `FileWriterTool` (goes through the bus).
- `file_writer` returns `OK (staged; saved … when this phase passes its checks)`; the bus
  summary no longer tells agents to call a tool they don't have.
- Draft paths under `.harness/` are rejected; the file inventory skips `.harness/`.

## 4. Evidence

- `tests/unit/tools/test_draft_commit_regression.py` — 10 tests, drafts **on**; 8 fail on the
  old code (the 2 that pass are "must not commit" guards).
- `tests/unit/backends/langgraph_backend/test_pipeline_writes_reach_disk.py` — the **real
  LangGraph pipeline**, offline, scripted agents calling `file_writer`, real ruff + pytest
  gate. Old code: stuck in testing after 3 retries, pytest exit 5, 15 "files" counted. New
  code: `complete`, tests pass, `retry_count=0`, 1.1 s.
- Unit suite: see commit. Ruff, format, mypy clean.

**Not verified live.** OpenRouter is unreachable from the agent sandbox.

## 5. Also changed

- `course/testing/run_step.py`: macOS refused `killpg` (EPERM) in the second run and the
  `.meta` file was lost. It now walks the process tree, always writes `.meta`, records
  Ctrl-C, and defaults to **960 s** so a lab's own `--timeout 900` watchdog acts first — the
  second run's 908 s outer kill landed inside the 30 s grace window and proved nothing about
  the watchdog.
- Week 4 only runs `annotate` if the export exists (F13).
- Week 2 / week 6 / S2 now tell the second layer as a lesson: *fixing the loudest failure
  uncovers the quiet one; a suite that runs with a production switch off tests a different
  program.*

## 6. Afternoon — the third `/test-course` run

`course/testing/runs/2026-09-17-stranger/` (Cursor, Grok 4.6, `$0.977` of `$10`, ~70 min,
SHA `396a348`). Its headline holds up against the log:

**W1.S3.c1 — the first LangGraph smoke in this repo's history to finish on its own.**
Exit 0, **741.8 s**, `$0.054`, `completed_at` set, `current_phase=complete`, `retry_count=3`,
`drafts_committed` at all eight phase boundaries (2+2+2+3+2+4+2+2), zero
`route_after_behavioral decision=fail`. `5b131bd` and `3509ca3` are confirmed live.

Also this run: CrewAI failed the prototype brief on `DeploymentConfig` guardrails (850 s, no
SIGSEGV — R8 from the morning does not reproduce); Claude SDK honoured the `$1` cap at
`$0.899`; W4 annotate gate, `run_step.py` `.meta` and the trace backfill all held.

### 6.1 But it used every retry it had, on correct code

`retry_count: 3`, `max_retries: 3`. Phase history: development → testing failed three times,
passed on the fourth. pytest inside those failed rounds was reporting **24 passed**.

Three defects, all harness, all found in `logs/W1.S3.c1.txt`:

| # | Defect | Effect |
| --- | --- | --- |
| 1 | `_write_file_impl` silently rewrote a root-level `test_*.py` to `tests/test_*.py` (`normalize_pytest_path`); the draft/commit path wrote it where the agent asked. | Same suite in two places → pytest import-file mismatch → gate fails. The agent spent four rounds deleting a file it never created and signed off with *"All 74 tests pass (37 from root `test_calc.py` + 37 from `tests/test_calc.py`)"*. |
| 2 | The gate linted the generated project with **this repo's** ruff profile (`UP`, `N`, `B`, `C4`, `SIM`). `Union[int, float]` → UP007, whose fix ruff considers unsafe, so the gate's `--fix` pre-pass could not clear it. | `passed = ruff.ok and pytest.ok` → False on a rule the brief never mentioned. The agent rewrote `calc.py` six times chasing a W292/UP007 it could not see land, because its writes were drafts and its ruff tool read the committed file. |
| 3 | The QA prompt says "Use read_file to inspect source files"; QA had no read tool. | Three `Error: read_file is not a valid tool` turns, then it rewrote the source from memory. |

The brief says *"Output calc.py and test_calc.py only."* Defect 1 means the harness and the
brief were asking for different things, and only the harness knew.

**A theory that did not survive contact.** The first diagnosis was that the workspace
inherited the repo's `testpaths = ["tests"]`. It does inherit the config — but pytest 9 falls
back to the working directory when `testpaths` matches nothing, so root-level tests are
collected anyway. Checked before shipping; recorded here because the report's own
"collected 0 items" quotes come from the *model's* messages, not from the gate. The harness
never emitted `no_tests_collected` in this run. Read the log, not the agent's summary of it.

## 7. Fix (afternoon)

- **`tools/file_tools.py`**: `normalize_pytest_path` deleted, along with its call in
  `_write_file_impl` and the unreachable "refusing to write root-level pytest file" branch
  under it, and its two CrewAI call sites. A write lands where the agent asked.
- **`graphs/subgraph_runners.py`**: the workspace gets its own `pytest.ini`
  (`testpaths = .`, `-p no:cacheprovider`) and `ruff.toml` (`E, F, I, W, B`, line-length 100),
  and the gate passes `-c` / `--config` and an explicit `.` so neither tool can inherit
  ai-team's preferences. The `--fix` pre-pass now covers the whole workspace profile.
- **`tools/qa_tools.py`**: `get_qa_tools()` includes `read_file_tool`; the testing prompt
  names a tool QA actually has.

Tests (all fail on `396a348`, pass now):

- `tests/unit/tools/test_write_path_fidelity.py` — 4 tests, 2 fail on the old code.
- `tests/unit/backends/langgraph_backend/test_quality_gate_config_isolation.py` — 9 tests,
  4 fail on the old code; the fixture nests the workspace under a repo-shaped
  `pyproject.toml`, which is what makes the inheritance visible.
- Three existing tests asserted the relocation and the six-tool QA list; updated with a note
  saying what they used to encode.

Full `tests/unit`: 1649 passed. Ruff, format, mypy clean.

**Not verified live.** These three fixes have no live run behind them yet.

## 8. Course changes

- **Week 2** now ends on the live complete *and* the three new layers, with the 74-tests
  quote and a `test_write_path_fidelity.py` command. The pattern line gained a third clause:
  a harness that silently "helps" makes the agent spend its turns fighting a ghost.
- **Week 6** replaces "nobody has shown a live run" with `n=1, 12.4 min, $0.05,
  retry_count=3 of 3` and says plainly that the last two fixes have no live run at all.
- **Week 2 step 1** now says a failed CrewAI row is a result (F16); **week 6 step 5** tells
  the learner to `ls output/runs` first, because `pytest tests/unit` leaves throwaway runs
  there and the audit counted 13 instead of 4 (F17).

## 9. Evening — the fourth `/test-course` run

`course/testing/runs/2026-09-17-stranger-2/` (`$0.89` of `$10`, ~50 min, SHA `8db7448`).
**All three backends completed live in one session for the first time.**

| | `396a348` (morning) | `8db7448` (evening) |
| --- | --- | --- |
| LangGraph | complete, 741.8 s, `$0.054`, retry **3 of 3** | complete, **226.1 s**, `$0.008`, retry **0** |
| CrewAI | **failed** at 850 s on `DeploymentConfig` guardrails, no tests | complete, 588 s, 5 tests pass |
| Claude SDK | complete, 217 s, `$0.899` | complete, 227 s, `$0.860` |

Verified in `logs/W1.S3.c1-retry.txt`: `phase_history` is planning → development → testing
(passed) → deployment with **no retry**; the workspace holds exactly `calc.py` and
`test_calc.py` and **no `tests/` directory**; six paths in the inventory instead of sixty (the
`.pytest_cache` noise went with `-p no:cacheprovider`); zero `read_file is not a valid tool`.

CrewAI was fixed by the same commit, which was not predicted: it shared the
`normalize_pytest_path` call site in `_persist_test_files_from_code_files`. So the sentence
added that morning saying CrewAI may fail this brief was stale within eight hours — the third
time in two days the course text went stale inside a day. That is now a stated property of the
material, not an accident: every live number in weeks 2 and 6 carries its SHA and its `n`.

## 10. Fix (evening)

**F22 — the key preflight.** An empty `OPENROUTER_API_KEY` beats `.env` *on purpose*: that is
how week 1's placeholder run guarantees `$0`. But when it was still in the shell for a paid
run, the failure arrived ~3 s in as litellm's "Missing credentials … set the `OPENAI_API_KEY`
environment variable" — a variable this project does not use. `run_demo._missing_api_key()`
now refuses before anything starts and distinguishes the two cases: *set but empty in this
shell* (→ `unset`) versus *not set anywhere* (→ put it in `.env`, or use
`--graph-mode placeholder`). The empty-means-do-not-spend semantics are deliberately kept.

**F17 — the audit corpus.** Tests that built a `ResultsBundle` wrote real run directories into
the repo's `output/runs/`, which is the eval corpus and what week 6 step 5 ingests; a learner
who ran `pytest tests/unit` first audited 14 runs instead of their 5. `tests/conftest.py`
gained `_isolate_run_output`: the session points `PROJECT_OUTPUT_DIR` at a temp dir and fails
if anything lands in the real one anyway. `output/runs` held 356 entries before the suite and
356 after.

**R8 — CrewAI spend.** Crews run under subprocess isolation, so the spend guard saw
`$0.000236` of a run its own token tracker measured at `$0.0247` (89× under) and that is the
number `logs/costs.jsonl` carried. New `spend_guard.reconcile_spend(usd, source=…)`: a backend
hands over its own end-of-run total, `current_spend()` reports it with `observed_usd` and
`source` alongside, and `run_demo._finalize_run` writes the row even when this process saw no
calls. It deliberately does **not** move the ceiling — a total that arrives after the run
cannot stop it, and pretending otherwise would be the same class of lie.

**R9 — the Claude clock.** The SDK backend writes its bundle after the orchestrator returns,
so `default_run_metadata` stamped "now" and a 217-second run recorded `started_at` and
`completed_at` 6 ms apart. Both call sites now capture a start time and pass it through.

Tests: `tests/unit/test_run_record_truth.py` — 10 tests across the three; fails at import on
`8db7448` (`cannot import name 'reconcile_spend'`). `tests/unit`: **1662 passed**. Ruff,
format, mypy clean.

## 11. Course changes (evening)

- **Week 2 step 1** is reframed: "optional, and it will probably work — that is the point."
  It carries a morning/evening table for all three backends on the same day, four commits
  apart, and two readings: a run that *finished* while burning every retry it had is not a
  run that worked, and one fix moved two backends because they shared a piece of glue.
- **Week 2 header** now says most of the breaking lives in the recorded case and the git
  history, which is what "we fixed it" is supposed to look like.
- **Week 6** replaces the prose before/after with the two-row table (741.8 s retry 3 →
  226.1 s retry 0) and sends the learner to put **n=1 against n=1** through the interval step.
  Step 5 keeps the pollution story as a lesson and notes the suite no longer causes it.
- **Week 1** explains the empty-key semantics at step 2 and the recovery at step 3.

## 12. The Cursor test skill now builds, not just walks

The first four `/test-course` runs typed commands and checked output. Every step that asked
the learner to *make* something was skipped: week 5 step 4 ("write your own check") was
satisfied by applying `course/solutions/week-5-check.patch`, and week 6 step 3 ("fix and
re-run") only ever took the free replay path. So the two steps where the course stops being a
tour were the two steps nobody had tested.

`.cursor/skills/course-test/SKILL.md` gained a fifth parameter, `depth` (`walk` | `build`,
default **build**), and a build track, §5:

| | Task | Tests |
| --- | --- | --- |
| B1 | Write `evals/checks/mine.py` and find the six wiring points *without* the solution patch | W5.S4's claim that "pytest tells you which" — attempts logged per wiring point |
| B2 | Sabotage the check so it can never fail; confirm the sensitivity test catches it | whether the eval harness has teeth (a mutation test the course never asks for) |
| B3 | Change what the check *means*; predict the new numbers, then re-measure | `FIXTURE-ONLY` vs `CORPUS` — a change visible in no number is the finding |
| B4 | Re-accept the baseline, then try to sneak a regression past the gate | whether the gate blocks, and whether the message is readable |
| B5 | Take the check to live traces; one fresh run; rate and `n` before and after | that the learner's own work meets real data |
| B6 | ruff · mypy · `pytest tests/unit` · Tier A · `tests/unit/repo` | that the check is part of the system, not a file in a folder |

Every change re-runs at three scopes (§5a): the step, the gate, the pipeline. A wider scope
catching what a narrower one missed is called out as the most valuable finding a run can
produce.

Two more things the report now has to carry:

- **§4a coverage.** Every step id from `extract_steps.py` gets a disposition from a closed
  list (`RUN`, `RUN-PARTIAL`, `JUDGED`, or a named skip). Coverage is reported per week and
  overall; under 80% on a full run needs an explanation. "No runnable blocks" stopped being a
  reason to skip — a step with only prose still has a *Predict* and an *Explain* to judge.
- **§4b concept ledger.** Twelve ideas about agentic systems (draft-then-commit, guardrails
  failing correct work, retries as a cost multiplier, writer-vs-reader telemetry, abstention,
  corpus kinds, intervals, monitoring as an eval on a cadence), each marked **taught**,
  **asserted** or **missing**. A headline lesson marked *asserted* is a P1.

Observations are now written in the first person before the reviewer verdict, with
`predicted`, `surprised_me`, `still_dont_understand` and `could_i_explain_it`. A step where
nothing surprised the learner and they could already explain it taught nothing, and scores
`Teaches` accordingly. The rubric gained **Buildable** and **Feeds back** for weeks 5–6.

`course/testing/report-template.md` and `.cursor/commands/test-course.md` match. Verified
before shipping: `git apply --check course/solutions/week-5-check.patch` still applies, so B1
can end by diffing against the published solution.

## 13. Night — the fifth run, the first with `depth: build`

`course/testing/runs/2026-09-17-stranger-3/` (`$0.78` of `$10`, ~2.5 h, SHA `ffaaa2d`,
**100% step coverage**). The build track paid for itself on its first outing: it found three
things four walk-throughs could not, two of which were regressions from the same afternoon.

**F23 / R11 — my own preflight blocked a working Claude run.** `AnthropicAgentSdkSettings`
declared `env_prefix="ANTHROPIC_"` and **no `env_file`**, so it read the process environment
only. With the key in `.env` but not exported — precisely the state week 1's new `unset`
advice creates — `get_settings().anthropic.api_key` was `""` while `OpenRouterSettings`
(which does declare `env_file`) found its key. The §10 preflight asked the empty one and
refused in 0.4 s with "not set. Put it in .env", pointing at the file the key was in. Fixed
by giving the model an `env_file`; an explicitly empty variable still wins, so week 1's `$0`
guarantee is intact. Verified both ways.

**F26 — the same preflight made the suite read the developer's shell.** Four
`test_run_demo.py` tests call `main()`; with `OPENROUTER_API_KEY=` left over from week 1 they
failed, and with a *real* key exported they ran against live settings. Either way the suite
tested a different program than CI does. `tests/conftest.py::_isolate_api_keys` now pins both
variables to a fixed fake value for the session; a test that cares sets its own.
`tests/unit` is 1665 passed with the shell clean **and** with both keys blanked.

**F24 — a check nobody imports is a check that never runs.** The tester wrote `mine.py`,
skipped the one-line registry import, and 404 tests stayed green. Week 5 claimed *"the test
suite enforces each of these"*. It didn't, for the one wiring point the others can't cover:
every remaining guard only inspects checks the registry already knows about.
`tests/unit/repo/test_check_discovery.py` finds check modules by looking for `@check(` in the
source rather than by filename, so a new module is covered the moment it exists and helpers
like `validation.py` (which declares none) need no allowlist. Proven against a temporary
`probe_mine.py`: it fails, names the file, and gives the one-line fix.

It also found a real one immediately — `evals/checks/validation.py` is in that folder and is
not imported — which turned out to be correct: it is the check *validator*, not a check.
Hence the `@check(` rule instead of a filename list.

Week 5's sentence is rewritten to say what is now true: every row has a test behind it, some
messages name the missing file and some only name the symptom, so read the table first.

### Still open from that run, not yet fixed

- **R12 — the Tier A deterministic-check gate cannot flag a regression.** Worse than the
  report said: `evals/baselines/tier_a.json` holds `check_outcomes` for 20 checks and
  **every one is `"fail"`** (`suite_pass_pow_k: 0.0`), because the fixture corpus contains a
  fail fixture per check and the baseline collapses all fixtures into one aggregate outcome.
  `_eval_deterministic_checks` only raises on `base_outcome == "pass" and "fail" in cur`, so
  that branch is dead across the whole suite and deleting a *pass* fixture exits 0. Week 5
  teaches learners to add their check to this gate. Fix needs a baseline schema decision:
  per-check outcome **counts** (regress when the pass count drops) versus per-fixture
  outcomes keyed by trace id. Counts tolerate corpus growth; per-fixture is precise but
  churns. Rick to pick.
- **R13 — `trace backfill` mints duplicate traces.** `make_trace_id` ends in
  `uuid4().hex[:4]`, and `TraceStore.write` refuses overwrites but never collides, so every
  backfill of the same run writes a new file: 4 runs → 8 → 14. In a course whose rule is *no
  rate without its `n`*, the instrument inflates `n`. Committed fixtures are named by
  check+outcome so they are unaffected, and existing traces keep their ids; the only real
  decision is what backfill does when an id now collides — skip or replace.
- **R10 — variance is the story week 2 is missing.** LangGraph on the same brief: 226 s
  (evening), 518 s with three `decision=fail` lines, and a 900 s watchdog timeout with no
  `state.json`. CrewAI: 588 s complete, then a 900 s timeout with no `costs.jsonl`. The
  "3.8 min, retry 0" row is one draw, presented as an after-state.

## 14. R12 — the gate that could not fail

Fixed, and the design is worth recording because the bug was conceptual rather than a slip.

**The two questions.** A baseline answers *"did this change since last time?"*. The fixture
corpus was being asked *"is this still correct?"*. Those need different machinery, and using
the first for the second is what produced a vacuous gate: `baseline accept` records whatever
it sees, the corpus deliberately contains a failing fixture per check, so all 20 checks were
recorded as `"fail"` and the only rule (`baseline == "pass" and "fail" in current`) became
dead code. It did not drift into uselessness — it was accepted into it, by a human who had no
way to see what they were accepting.

**Counts were the wrong answer.** The first proposal here was per-check outcome counts
(`{"pass": 3, "fail": 1}`) with a regression when the pass count drops. It was rejected on
inspection: counts do not say *which* fixture produced which outcome, so a check whose
condition gets inverted — pass fixture now fails, fail fixture now passes — leaves the counts
identical and slips through. That is not a corner case; it is one of the likelier ways to
break a check. Counts also still need `baseline accept` on every corpus change, which is the
friction that produced the bad baseline.

**What shipped: `evals/fixture_contract.py`, three rules, no baseline.** A fixture whose trace
id is `CHK-x__pass__fixture` *declares* its expected outcome, so the corpus is compared with
its own specification:

1. **Completeness** — in a report that replays the fixture corpus, every check that ran has
   all three fixtures. The only rule that can notice a *deleted* fixture, since a table built
   from files that exist cannot miss what is not there. Scoped to replay reports: a live
   CORPUS run is not replaying fixtures and owes none.
2. **Expectation** — every fixture produces the outcome its id declares, **for its own
   check**. A fixture constrains only the check it was built for; the other 19 running over
   it abstain and carry no promise. Fails in both directions.
3. **Uniqueness** — no trace id loaded twice. A **warning**, not a failure: deleting Rick's
   committed fixtures is a human decision, not the gate's.

All three are computed from `SuiteReport.check_results`, so the gate stays a pure function of
the report and touches no disk. The contract runs **before** the baseline is consulted and
fires even when no baseline exists on disk, because ground truth does not need a past.
`Baseline.check_outcomes` stays, documented as informational.

**First run against the real corpus: zero expectation violations, zero completeness
violations.** The checks were right all along; only the gate was broken. And 22 uniqueness
warnings — 22 trace ids exist under two filenames each (`CHK-x__pass.json` and
`CHK-x__pass__fixture.json`), so those traces have been counted twice in every rate the suite
reports. Rick's call whether to delete the 22 duplicates.

**The other half of the same bug.** `suite_pass_pow_k` was `0.0` because
`_cell_outcomes_from_checks` counted every fixture as a trial, and the corpus contains a
deliberate failure for each check — so the metric was measuring "the corpus contains the
failures we put in it". Expectation fixtures are now excluded. The scorecard is 3 real cells
of n=4 (the `coverage__<backend>__<status>` traces). It still reads 0.0, because three of
those four statuses are degraded by design — but it is now a true statement that will move
when the corpus does, instead of an artifact.

Tests: `tests/unit/evals/test_fixture_contract.py`, 19 tests, including the exact R12
scenario (delete a pass fixture → exit 1, was exit 0), the inverted-check case that counts
would have missed, the "another check's result on this fixture is not constrained" scope rule,
and two guards that run the real corpus on every commit. `tests/unit`: 1684 passed.

Week 5 gained a short *Why row 5 is not optional* after the wiring run, ending on the line
this whole thing turns on: **a baseline answers "did this change?", which is a different
question from "is this right?"** Where you have ground truth, compare against the truth.

### Still open

- **R13** — `make_trace_id` ends in `uuid4().hex[:4]`, so re-backfilling a run mints a new
  trace instead of replacing it (4 runs → 8 → 14). Smaller than it looked: committed fixtures
  are named by check+outcome and existing traces keep their ids, so the only decision is what
  backfill does when an id now collides. Recommend replace, with `--skip-existing` for the old
  behaviour.
- **The 22 duplicate fixture files** surfaced by rule 3.
- **R10** — LangGraph variance (226 s / 518 s / 900 s timeout) still not reflected in week 2.

## 15. Start next session with

1. **R13, then week 2's variance row, then the 22 duplicate fixtures.** R12 is done (§14).
2. **Cursor re-validates.** Expect the key preflight to pass for all three backends, the
   check-discovery guard to be exercised in B1, and week 5's wiring table to be honest. Also:
   CrewAI `costs.jsonl` `spent_usd` now matching `actual_cost_usd` with
   `source: crewai_token_tracker`; Claude `run.json` showing a real duration; week 6 step 5
   ingesting only the learner's own runs; the paid steps refusing to start on an empty key.
3. **F1 — the launch blocker:** push/merge `feat/course-v2` so `course/` exists on `main`.
   Everything else on this branch is ready to share.
4. **Get live `n` above 1.** Every number in weeks 2 and 6 is a single observation, and the
   09-17 night run showed how wide the spread is (226 s / 518 s / timeout on one brief). The
   optional `--n 3` batch in week 6 is the cheapest way to start.
5. **Trace attribution:** agent-side `toolbus_span` rows still carry
   `agent_role=None backend=None phase=None run_id=None` while `_harness` commits carry all
   four. (The `unknown__` prefix on trace ids is the *scenario* id, not the status — an
   earlier note here had that wrong.)
6. **Consider flipping the unit-suite default** to drafts **on** — the current default is how
   the draft bug hid for three weeks.
7. Carried: teaching corpus for week 4, Rick's own thirty-trace reading pass, CrewAI SIGSEGV
   (has not reproduced since 09-16).
