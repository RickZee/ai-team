# 2026-09-17 — every agent write was a draft, and nothing ever saved one

**Session:** 2026-09-17. Agent-assisted (Claude Opus 5).
**Base:** `66c0c4a` on `feat/course-v2` (not pushed).
**Preceded by** [2026-09-16 (course v2)](2026-09-16-course-v2.md) §8.

Morning (§1–5): agent writes never reached the workspace. Afternoon (§6–9): the first live
LangGraph run finished — and showed three more harness layers underneath.

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

## 9. Start next session with

1. **Live check on the Mac** (pennies), now the real one to run:
   `AI_TEAM_ENV=dev AI_TEAM_RUN_BUDGET_USD=0.5 uv run python scripts/run_demo.py demos/00_smoke_test --backend langgraph --skip-estimate --timeout 900`
   Expect `retry_count=0` or 1, one `test_calc.py` and no `tests/` directory, and a finish
   well under 12 minutes. If `retry_count` is still 3, read the gate's `test_results`, not
   the agent's summary.
2. **Re-run `/test-course`** (stranger, $10) → `2026-09-18-stranger`, and get live `n` above 1.
3. **F1 — the launch blocker:** push/merge `feat/course-v2` so `course/` exists on `main`.
4. **R9:** Claude SDK `started_at` ≈ `completed_at` (6 ms apart on a 217 s run) — finalize
   clock, not wall clock. **R8:** CrewAI `costs.jsonl` recorded `$0.000259` against an actual
   `$0.0247` (~95× under). Reporting only — the spend guard uses in-memory LiteLLM costs.
5. **Trace attribution:** agent-side `toolbus_span` rows carry
   `agent_role=None backend=None phase=None run_id=None` while `_harness` commits carry all
   four. Likely the source of the `unknown` rows in week 3.
6. **Consider flipping the unit-suite default** to drafts **on** — the current default is how
   the draft bug hid for three weeks.
7. Carried: CrewAI SIGSEGV with `PYTHONFAULTHANDLER=1` (did not reproduce on 09-17),
   teaching corpus for week 4, Rick's own thirty-trace reading pass.
