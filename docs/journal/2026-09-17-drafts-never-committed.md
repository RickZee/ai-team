# 2026-09-17 — every agent write was a draft, and nothing ever saved one

**Session:** 2026-09-17. Agent-assisted (Claude Opus 5).
**Base:** `66c0c4a` on `feat/course-v2` (not pushed).
**Preceded by** [2026-09-16 (course v2)](2026-09-16-course-v2.md) §8.

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

## 6. Start next session with

1. **Live check on the Mac** (pennies):
   `AI_TEAM_ENV=dev AI_TEAM_RUN_BUDGET_USD=0.5 uv run python scripts/run_demo.py demos/00_smoke_test --backend langgraph --skip-estimate --timeout 900`
   Look for `drafts_committed` lines, `calc.py` + `tests/test_calc.py` in the run workspace,
   and a finish before 15 min. If it still runs to 900 s, confirm the watchdog message and
   exit 124.
2. **Re-run `/test-course`** (stranger, $5) → `2026-09-17-stranger`.
3. **CrewAI SIGSEGV (R8):** one run with `PYTHONFAULTHANDLER=1`.
4. **Consider flipping the unit-suite default** to drafts **on** and opting *out* where needed —
   the current default is how this hid for three weeks. Larger change; not done here.
5. Carried: push/merge `feat/course-v2` (F1), teaching corpus, `unknown` trace status, read
   thirty.
