# 2026-09-17 — every agent write was a draft, and nothing ever saved one

**Session:** 2026-09-17. Agent-assisted (Claude Opus 5).
**Base:** `66c0c4a` on `feat/course-v2` (not pushed).
**Preceded by** [2026-09-16 (course v2)](2026-09-16-course-v2.md) §8.

Morning (§1–5): agent writes never reached the workspace. Afternoon (§6–9): the first live
LangGraph run finished — and showed three more harness layers underneath. Evening (§10–12):
those three fixed, verified live, and the reporting bugs behind the numbers closed.

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

## 12. Start next session with

1. **Cursor validates `8db7448`+ (this commit).** Expect: LangGraph retry 0 under 5 min;
   CrewAI `costs.jsonl` `spent_usd` now matching `actual_cost_usd` with
   `source: crewai_token_tracker`; Claude `run.json` showing a real duration; week 6 step 5
   ingesting only the learner's own runs; the paid steps refusing to start on an empty key.
2. **F1 — the launch blocker:** push/merge `feat/course-v2` so `course/` exists on `main`.
   Everything else on this branch is ready to share.
3. **Get live `n` above 1.** Every number in weeks 2 and 6 is a single observation. The
   optional `--n 3` batch in week 6 is the cheapest way to start.
4. **Trace attribution:** agent-side `toolbus_span` rows still carry
   `agent_role=None backend=None phase=None run_id=None` while `_harness` commits carry all
   four; trace ids still get the `unknown__` prefix even though `by_backend` and `by_status`
   are now right.
5. **Consider flipping the unit-suite default** to drafts **on** — the current default is how
   the draft bug hid for three weeks.
6. Carried: teaching corpus for week 4, Rick's own thirty-trace reading pass, CrewAI SIGSEGV
   (has not reproduced since 09-16).
