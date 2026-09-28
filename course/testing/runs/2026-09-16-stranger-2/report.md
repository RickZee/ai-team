# Course test report — 2026-09-16-stranger-2

| | |
| --- | --- |
| **Scope / mode / budget / fix** | all · stranger · $5 · no |
| **Git SHA** | `66c0c4a` on `feat/course-v2` (includes loop-fix `5b131bd`) |
| **Environment** | Darwin 27.0.0 · uv 0.10.2 · Python 3.12.7 |
| **Tester** | Cursor agent (Grok 4.6) · 2026-09-16 |
| **Spend** | **$0.75 recorded + $0.10 projected = $0.85 counted** of $5. W1 LangGraph $null (count $0.05) · W2 CrewAI $null (count $0.05) · W2 Claude **$0.755** (under $1 cap; log `max_budget_usd=1.0`). Optional `--n 3` LangGraph batch not run. |
| **Wall time** | ~50 min including one 15-min LangGraph time-box. |
| **Previous run** | `course/testing/runs/2026-09-16-stranger` (SHA `72d49e1`, budget $10) |

## Verdict

The copy-paste fences that blocked a macOS stranger last run are fixed. The $0 spine (dry run, recorded case, weeks 3–6 replay) now runs as written. Live LangGraph after `5b131bd` **no longer retries on 8%/5% relevance**, and there is **no nested `workspace/<id>/workspace/`** — but it still **does not complete in 15 minutes**, still has **no `completed_at` / final status** when killed, and **unit tests are not a live proof**. Not ready to claim the loop is gone on real runs.

## Scorecard

| Week | Runs | Accurate | Clear | Teaches | Honest | Fits budget | Stranger can finish alone? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 · Build | 4 | 5 | 4 | 5 | 5 | 3 | Yes through the dry run + stop rule; live run is the finding |
| 2 · Fail | 4 | 5 | 5 | 5 | 5 | 3 | Yes via recorded case + regression tests; live race still optional and flaky |
| 3 · Observe | 5 | 5 | 5 | 5 | 5 | 5 | Yes |
| 4 · Read | 4 | 5 | 4 | 3 | 5 | 4 | Mechanics yes; 30 human reads no |
| 5 · Evaluate | 5 | 5 | 4 | 5 | 5 | 5 | Yes with the patch |
| 6 · Improve | 5 | 5 | 5 | 5 | 5 | 5 | Yes on the replay path |

## Step results

| Step | Block | Result | Exit | Time | Note |
| --- | --- | --- | --- | --- | --- |
| W1.S2 | c1 | MATCH | 0 | 8.7 s | dry run |
| W1.S2 | c2 | MATCH | 0 | 0.1 s | `completed_at` + `final_status=complete`; `logs/` empty |
| W1.S2 | c3 | MATCH | 0 | 0.1 s | quoted glob; CLI `finalize()` in `run_demo.py`; 0 of 1 open |
| W1.S3 | c1 | BROKEN | 124 | 908 s | loop-fix live check: 0 behavioral fails; still no finish |
| W1.S3 | c2 | MATCH | 0 | 0 s | `ls` first; `no state.json`; `test_calc.py` present |
| W2.S1 | langgraph | SKIPPED-PAID | — | — | reused W1.S3 |
| W2.S1 | crewai | BROKEN | 139 | 110 s | SIGSEGV in development crew |
| W2.S1 | claude | MATCH | 0 | 147 s | **$0.755 < $1**; `max_budget_usd=1.0` |
| W2.S1 | c2 | SKIPPED-SCOPE | — | — | dashboard |
| W2.S1 | c3 | MATCH | 0 | 0 s | three newest ids |
| W2.S2 | c1–c3 | MATCH | 0 | 0–4 s | evidence; `5b131bd`; 9 regression tests pass |
| W3 | all | MATCH/DRIFT | 0 | <2 s | quoted globs; `FIX=$(git log…)`; 66 spans |
| W4.S1 | c1 | DRIFT | 0 | 0.5 s | n_selected=4 |
| W4.S2 | c1 | MATCH | 0 | 0.1 s | `ID=$(ls -t …)` |
| W4.S3 | c1 | BROKEN | 0 | 0.5 s | `ls \|\| echo` then annotate still crashes |
| W5.S1 | c1 | MATCH | 0 | 1.0 s | `grep layer` prints harness 0.479 n=213 |
| W5.S4 | c2 | MATCH | 0 | 18 s | 228 fails; CORPUS n=4 |
| W6.S2 | c1 | MATCH | 0 | 1.2 s | `CHECK=CHK-trace-has-spans` |
| W6.S3 | c1 | MATCH | 0 | 60 s | unit tests |
| W6.S3 | c2 | MATCH | 0 | 0.2 s | replay overlap lesson |
| W6.S3 | live n=3 | SKIPPED-PAID | — | — | 1-hour box; W1.S3 already 15 min incomplete |
| W6.S4 | c1 | MATCH | 0 | 0.1 s | `(0.0, 0.2425)` |
| W6.S5 | c1 | MATCH | 0 | 0.1 s | `RUNS=output/runs` |

Totals: **MATCH 24 · DRIFT 6 · BROKEN 4 · SKIPPED-PAID 2 · SKIPPED-SCOPE 1**

## W1.S3 — live check of `5b131bd`

| Question | This run | Previous run (`72d49e1`) |
| --- | --- | --- |
| Wall time | 908 s (outer 900s time-box) | 900 s |
| Completes before 15 min? | **No** | No |
| `route_after_behavioral decision=fail` | **0** (all `pass` / `warn`) | fail at 8% then 5%; `guardrail_retry_wrap` attempts 1–2 |
| Nested `workspace/<id>/workspace/` | **False** | not recorded then; files were under the run id |
| `run.json` `completed_at` | **null** (killed) | null |
| `extra.final_status` | **missing** | missing |
| `state.json` | **absent** | absent |
| Test file in workspace | `test_calc.py` by ~minute 1 | same |
| Leftover `run_demo` after | **none** | two orphans (PPID 1) still spending |
| What it was doing at minute 15 | QA rewriting `calc.py` / `test_calc.py`; absolute draft paths rejected | relevance retry loop |

**Conclusion:** the recorded-case loop (last-12 scoring + `retry_development`) did not reproduce. A different hang did. Live n for “the loop is gone” is still **0 completes**.

## Findings

| ID | Sev | Where | What happened | Suggested change | Evidence |
| --- | --- | --- | --- | --- | --- |
| F11 | P0 | live LangGraph after `5b131bd` | No relevance-fail retries, no nested workspace, files exist in ~1 min — then the run does not exit by 15 min (QA rewrite / invalid absolute draft path). Killed runs still lack `completed_at`. | Week 2/6 should say: unit tests pass; live smoke still may not finish in 15 min. Do not claim the loop is gone until a live run completes. | `logs/W1.S3.c1.txt` |
| F12 | P0 | CrewAI CLI | Exit 139 (SIGSEGV) at 110 s in `run_development_crew`. | Point learners at the recorded case; don’t treat the live race as required. | `logs/W2.S1.c1-crewai.txt` |
| F13 | P2 | `course/week-4-read.md:88` | `ls -l $NOTES \|\| echo …` then annotate still raises FileNotFoundError. | `[ -f "$NOTES" ] && uv run python -m evals.cli annotate …` | `logs/W4.S3.c1.txt` |
| F14 | P1 | `course/testing/run_step.py` | `os.killpg` raised `PermissionError`; meta file not written. Leftovers were none this time. | Catch `PermissionError`/`ProcessLookupError`, still write `.meta`, fallback `pkill`. | tester traceback at 900s |

Still open from last run, **not re-derived:** **F1** (`course/` is not on `origin/main`; Start’s GitHub clone still misses the course).

## Repo findings

| ID | Where | What | Owner |
| --- | --- | --- | --- |
| R7 | LangGraph after `5b131bd` | Relevance loop gone; run still open at 15 min (rewrite / draft-path). Watchdog `--timeout 900` did not stop it before the outer killer. | langgraph graphs + `run_demo.py` watchdog |
| R8 | CrewAI | SIGSEGV during development crew kickoff | crewai backend |
| R2 | CLI `finalize()` | Dry run now gets `completed_at`. Paid LangGraph killed before finalize still doesn’t. | `scripts/run_demo.py` — progress vs last run |

## Since last run

Previous: `course/testing/runs/2026-09-16-stranger`.

| Block | Was | Now |
| --- | --- | --- |
| W1.S2.c2 | MATCH (`completed_at` null, as then written) | MATCH (`completed_at` set — writer fix + updated Explain) |
| W1.S2.c3 | BROKEN zsh glob | **MATCH** quoted glob |
| W1.S3.c1 | BROKEN hang + 8%/5% fail + orphans | BROKEN hang, **0 fails**, **no orphans** |
| W1.S3.c2 | BROKEN missing `state.json` grep | **MATCH** (`ls` first) |
| W2.S1 crewai | BROKEN 900s hang | BROKEN **SIGSEGV 110s** |
| W2.S1 claude | MATCH $0.71, recovery $18 | MATCH **$0.755**, recovery **$1.0** |
| W2.S2.c2 | MATCH function grep | MATCH `5b131bd` git show |
| W3.S1.c1/c3 | MISMATCH empty/zero | **MATCH** split Observe |
| W3.S2.c4 | BROKEN `<that commit>` | **MATCH** |
| W3.S5.c1 | BROKEN zsh glob | **MATCH** |
| W4.S2.c1 | BROKEN `ID=<…>` | **MATCH** |
| W4.S3.c1 | BROKEN missing Downloads | BROKEN (hint added, annotate still runs) |
| W5.S1.c1 | MATCH but `head -3` hid layers | **MATCH** `grep layer` |
| W6.S2.c1 | BROKEN `<your check id>` | **MATCH** |
| W6.S3.c2 | SKIPPED-PAID live `--n 5` | **MATCH** `--replay` as the lab |
| W6.S5.c1 | BROKEN `/path/to/your/runs` | **MATCH** `RUNS=output/runs` |

No finding marked fixed in the previous report still reproduced **as the same bug**, except F1 (known, still true) and the live hang (same symptom, different cause).

Spend / wall: last run $1.64 of $10 in ~80 min; this run $0.85 of $5 in ~50 min.

## Week notes

### Week 1
Dry-run card now matches the updated Explain (end time exists, logs empty). Paid LangGraph is the remaining lesson: files appear, the record may not.

### Week 2
Recorded case + `5b131bd` + 9 passing regression tests are the product. Live race is correctly marked optional. Claude stayed under $1.

### Weeks 3–6
Fences that were P0 last time run as written. Replay is the week-6 lab and teaches overlap. Teaching corpus still absent (week 4 n=4).

## Learner questions

- Could a stranger finish alone? On this branch, yes for the $0 path. Not from GitHub `main` (F1). Live LangGraph/CrewAI still fail as labs.
- Most confusing moment: files exist, guardrails pass, the process still will not end.
- Best lesson: instrument vs agents (weeks 3 and 5). Asserted-only: “the loop is gone” as a live claim.
- Purpose (`course/README.md`): the $0 labs on this branch now match “a stranger can run it,” except Start still points at `main`.

## Top 5 improvements

1. **Do not claim the LangGraph loop is gone on live runs.** Report: 0 relevance fails, 0 completes in 15 min, `completed_at` null when stopped. Need one live complete (or an honest “not yet”).
2. **Keep Start honest (F1):** merge `course/` to `main` or change the clone line.
3. **Gate week-4 annotate on the export file existing** (`[ -f "$NOTES" ] && …`).
4. **Harden `run_step.py` `killpg`** so a PermissionError still writes `.meta` and tries `pkill`.
5. **Ship a 30-run teaching corpus** so week 4 is finishable on a fresh clone.

## Resolution (added after review, 2026-09-17)

| ID | Status | What changed |
| --- | --- | --- |
| F11 / R7 | root cause found and fixed (offline-proven, not live) | The log showed every agent write ending as a draft (`call commit_write to promote`) with no commit in the whole run. No backend gave agents `commit_write`, and nothing else promoted drafts (on by default since 2026-08-28). The harness now commits pending drafts once a phase's guardrails pass (LangGraph: each phase node; CrewAI: after development and before pytest), audited as `_harness` `commit_write`. The QA role also lacked `file_writer`, which every QA prompt names; it now has it. Offline full pipeline with drafts on: complete, tests pass, 0 retries (was retry_count=3, pytest exit 5). |
| F11 watchdog | open — needs a clean measurement | The outer kill (908 s) landed inside `run_demo`'s 30 s grace window, so this run can't show whether the watchdog works live. `run_step.py` now defaults to 960 s. |
| F12 / R8 | open | CrewAI SIGSEGV — re-run with `PYTHONFAULTHANDLER=1`. The draft fix also applies to CrewAI, so its earlier "testing, no tests" hang may change. |
| F13 | fixed | Week 4 runs `annotate` only when the export file exists. |
| F14 | fixed | `run_step.py` walks the process tree when macOS refuses `killpg`, always writes `.meta`, and records Ctrl-C. |
| Test gap | fixed | Unit tests ran with `AI_TEAM_DRAFT_WRITES=0`; new tests opt in with `bus_draft`, including an offline end-to-end pipeline test that fails on the old code. |

## Appendix

- Observations: `observations.jsonl`
- Logs: `logs/`
- Spend: `spend.jsonl`
- Test checkout: `/var/folders/7f/trms0d492gsf9j9ydv6kp1q00000gn/T/tmp.1HiTgZgNaA/ai-team` (week 5 left on `my-first-check`, not merged)
- Leftovers at end: none
- Deviations: skipped W2.S1 LangGraph re-run; skipped live `--n 3` LangGraph batch (1-hour box); two `SIMULATED:` notes in scratch only; W5 used `solutions/week-5-check.patch`
