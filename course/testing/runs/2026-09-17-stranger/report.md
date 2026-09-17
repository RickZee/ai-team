# Course test report — 2026-09-17-stranger

| | |
| --- | --- |
| **Scope / mode / budget / fix** | all · stranger · $10 · no (defaults from `/test-course`) |
| **Git SHA** | `396a348` on `feat/course-v2` (loop-fix `5b131bd` · save-writes `3509ca3`) |
| **Environment** | Darwin 27.0.0 · uv 0.10.2 · Python 3.12.7 |
| **Tester** | Cursor agent (Grok 4.6) · 2026-09-17 |
| **Spend** | **$0.977 of $10.** W1 LangGraph **$0.054** · W2 CrewAI **$0.025** · W2 Claude **$0.899** (under $1; log `max_budget_usd=1.0`). Optional `--n 3` LangGraph batch not run (projected pennies). |
| **Wall time** | ~70 min including clone/`uv sync` and three live smokes. No 15-min kill. |
| **Previous run** | `course/testing/runs/2026-09-16-stranger-2` (SHA `66c0c4a`, budget $5) |

## Verdict

A stranger on this branch can finish the $0 spine and, for the first time in these tests, **a live LangGraph smoke completes** (12.4 min, cents, `completed_at` set). CrewAI still does not finish the prototype brief. Start still clones GitHub `main`, which has no `course/` (**F1**). Ready to share the labs on this branch; not ready to tell people to clone `main`.

## Scorecard

| Week | Runs | Accurate | Clear | Teaches | Honest | Fits budget | Stranger can finish alone? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 · Build | 5 | 5 | 5 | 5 | 5 | 5 | Yes, including the live run |
| 2 · Fail | 5 | 5 | 5 | 5 | 4 | 4 | Yes via recorded case; live race 2/3 finish |
| 3 · Observe | 5 | 5 | 5 | 5 | 5 | 5 | Yes |
| 4 · Read | 5 | 5 | 4 | 3 | 5 | 4 | Mechanics yes; 30 human reads no |
| 5 · Evaluate | 5 | 5 | 4 | 5 | 5 | 5 | Yes with the patch |
| 6 · Improve | 5 | 5 | 5 | 5 | 4 | 5 | Yes on the replay path |

Week 2 Honest is 4 because the page still says the save-writes fix is “not yet by a live one.” Week 6 Honest is 4 for the same leftover sentence plus pytest leftover folders in the audit.

## Step results

| Step | Block | Result | Exit | Time | Note |
| --- | --- | --- | --- | --- | --- |
| W1.S1 | files | MATCH | — | 0 s | backend.py, input.json, diagram |
| W1.S2 | c1 | MATCH | 0 | 8.6 s | dry run |
| W1.S2 | c2 | MATCH | 0 | 0.1 s | `completed_at` + `final_status=complete`; `logs/` empty |
| W1.S2 | c3 | MATCH | 0 | 0.1 s | quoted glob; 0 of 1 open |
| W1.S3 | c1 | MATCH | 0 | 742 s | **live complete**; 0 behavioral fails; `$0.054` |
| W1.S3 | c2 | MATCH | 0 | 0 s | `state.json` phase complete; `test_calc.py` |
| W2.S1 | langgraph | SKIPPED-PAID | — | — | reused W1.S3 |
| W2.S1 | crewai | MATCH | 1 | 850 s | failed DeploymentConfig guardrail; no SIGSEGV |
| W2.S1 | claude | MATCH | 0 | 217 s | **$0.899 < $1**; `max_budget_usd=1.0` |
| W2.S1 | c2 | SKIPPED-SCOPE | — | — | dashboard |
| W2.S1 | c3 | MATCH | 0 | 0 s | three newest: claude, crewai, langgraph |
| W2.S2 | c1–c4 | MATCH | 0 | 0–6 s | evidence; `5b131bd`; 9 tests; `3509ca3` pipeline test |
| W3 | all | MATCH/DRIFT | 0 | <2 s | 4 traces; default 180 spans vs output/runs 3 |
| W4.S1 | c1 | DRIFT | 0 | 0.5 s | n_selected=4 |
| W4.S2 | c1 | MATCH | 0 | 0.1 s | newest Claude run |
| W4.S3 | c1 | MATCH | 0 | 0.3 s | `[ -f "$NOTES" ]` gate; no FileNotFoundError |
| W5.S1 | c1 | MATCH | 0 | 0.9 s | 182 fail; harness 0.479 n=213 |
| W5.S4 | c2 | MATCH | 0 | 18 s | 228 fails; CORPUS n=4; branch `course-test/w5` |
| W6.S2 | c1 | MATCH | 0 | 1.3 s | `CHECK=CHK-trace-has-spans`; thin n=8 |
| W6.S3 | c1 | MATCH | 0 | 51 s | 1643 passed; polluted `output/runs` |
| W6.S3 | c2 | MATCH | 0 | 0.2 s | replay overlap lesson |
| W6.S3 | live n=3 | SKIPPED-PAID | — | — | optional; W1.S3 already live complete |
| W6.S4 | c1 | MATCH | 0 | 0.1 s | `(0.0, 0.2425)` |
| W6.S5 | c1 | DRIFT | 0 | 0.1 s | ingested 13 (4 learner + pytest leftovers) |

Totals: **MATCH 28 · DRIFT 9 · SKIPPED-PAID 2 · SKIPPED-SCOPE 1 · SKIPPED-HUMAN 1 · BROKEN 0**

## W1.S3 — live check of `5b131bd` + `3509ca3`

| Question | This run (`396a348`) | Previous (`66c0c4a`) |
| --- | --- | --- |
| Wall time | **741.8 s** (exit 0) | 908 s (outer 900s time-box) |
| Completes before 15 min? | **Yes** | No |
| `route_after_behavioral decision=fail` | **0** (pass/warn only) | 0 (then hung in QA rewrite) |
| Nested `workspace/<id>/workspace/` | **False** | False |
| `run.json` `completed_at` | **set** | null (killed) |
| `extra.final_status` | **complete** | missing |
| `state.json` | **phase=complete**, retry_count=**3** | absent |
| Test file in workspace | `test_calc.py` | `test_calc.py` (then rewrite hang) |
| Spend | **$0.054** | unrecorded (projected $0.05) |
| Leftover `run_demo` after | **none** | none |
| Watchdog | armed 900s, did not fire | outer kill inside grace window |

**Conclusion:** the recorded-case loop (last-12 scoring + `retry_development`) still does not reproduce. The draft-never-committed hang from yesterday is gone on this live run. Live n for “a LangGraph smoke can finish” is **1**, with **3 retries**. Do not yet say “the loop is gone” as a rate.

## Findings

| ID | Sev | Where | What happened | Suggested change | Evidence |
| --- | --- | --- | --- | --- | --- |
| F1 | P0 | `course/README.md:18` | `git clone https://github.com/RickZee/ai-team.git` has no `course/` on `origin/main`. Known, not re-derived. | Merge `course/` to `main` or change Start to the branch that has it. | `git ls-tree origin/main` |
| F15 | P2 | `course/week-2-fail.md` ~L119; week 6 ~L29 | Page still says both fixes are “not yet by a live one.” This SHA completed a live LangGraph smoke in 12.4 min. | Replace with: “Live n=1 on 2026-09-17: complete in 12 min, `$0.05`, `retry_count=3`. Offline pipeline: 0 retries.” | `logs/W1.S3.c1.txt` |
| F16 | P2 | W2 live CrewAI | Prototype smoke aborted after 3 development guardrail failures (`DeploymentConfig` Dockerfile / CI/CD). No `test_calc.py`. Command itself is fine. | One sentence: CrewAI may fail this brief on deployment checks; fill the Observe card from that. Keep the recorded case as the required path. | `logs/W2.S1.c1-crewai.txt` |
| F17 | P2 | `course/week-6-improve.md` S3 then S5 | `pytest tests/unit` left extra folders in `output/runs` (`h1`, `h2`, `can-2`, `desc_01`, …). Step 5 then ingested **13** runs instead of the learner’s 4. | After pytest: `RUNS=output/runs` should be the week 1–2 ids, or say `ls output/runs` and ignore test leftovers. | `logs/W6.S5.c1.txt` |

Still open from last run, **not re-derived:** **F1**.

Previous F11 (no live complete in 15 min) **does not reproduce** on `396a348`. Previous F12 (CrewAI SIGSEGV) **does not reproduce**. Previous F13 (annotate FileNotFoundError) **does not reproduce**. Previous F14 (`run_step.py` killpg) was not exercised (no timeout).

## Repo findings (not course text)

| ID | Where | What | Owner |
| --- | --- | --- | --- |
| R7 | LangGraph after `3509ca3` | Live smoke **completed** in 12.4 min; `retry_count=3` (offline pipeline test is 0 retries). | langgraph graphs + `tools/draft.py` |
| R8 | CrewAI | No SIGSEGV this run. Fails prototype smoke on DeploymentConfig guardrails; `costs.jsonl` `spent_usd=0.000259` vs log `actual_cost_usd=0.0247`. | crewai backend + cost writer |
| R9 | Claude SDK `run.json` | `started_at` ≈ `completed_at` (6 ms) on a 217 s run — finalize clock, not wall. | `claude_agent_sdk_backend` / `ResultsBundle.finalize` |
| R2 | CLI `finalize()` | Dry run and paid LangGraph both get `completed_at` when the process actually exits. | `scripts/run_demo.py` |

## Since last run

Previous: `course/testing/runs/2026-09-16-stranger-2`.

| Block | Was | Now |
| --- | --- | --- |
| W1.S3.c1 | BROKEN hang 908 s, `completed_at` null | **MATCH complete 742 s** |
| W1.S3.c2 | MATCH (`no state.json`) | **MATCH** (`state.json` complete) |
| W2.S1 crewai | BROKEN SIGSEGV 110 s | **MATCH** failed guardrail 850 s (no crash) |
| W2.S1 claude | MATCH $0.755 | MATCH **$0.899**, cap 1.0 |
| W2.S2.c4 | (step did not exist) | **MATCH** `3509ca3` + pipeline pytest |
| W4.S3.c1 | BROKEN annotate FileNotFoundError | **MATCH** gated |
| W6.S5.c1 | MATCH | **DRIFT** 13 traces after pytest leftovers |

No finding marked fixed in the previous report still reproduced as the same bug, except **F1**.

Spend / wall: last run $0.85 of $5 in ~50 min (one 15-min hang); this run **$0.98 of $10 in ~70 min**, all three live smokes exited on their own.

## Week notes

### Week 1 · Build
- Predict a newcomer would make: the dry run has no end time / no logs. The step corrects the end-time part; empty `logs/` is the lesson.
- Most confusing moment: none this run — the live smoke finished.
- Scores evidence: every command worked as written; 12 min / $0.05 is inside the “30 min, cents” box.

### Week 2 · Fail
- Recorded case + `5b131bd` + `3509ca3` + tests are still the product.
- Live table this run: LangGraph complete 12.4 min retry=3 with tests; CrewAI failed 14 min no tests; Claude complete 3.6 min $0.90 with tests.
- Honest gap: “not yet by a live one” is now stale on this SHA.

### Week 3 · Observe
- Split Observe (fresh clone vs maintainer) holds. Default backfill still mislabels `unknown` and reads `./workspace` (180 spans); `output/runs` has 3.

### Week 4 · Read
- Mechanics work. n=4. Human 30-read SKIPPED. Annotate gate fixed.

### Week 5 · Evaluate
- Tier A 182 fail / harness 0.479 n=213 matches the page. Patch + baseline on `course-test/w5`, not merged.

### Week 6 · Improve
- Replay teaches overlap. Live `--n 3` skipped (optional; n=1 live complete already). Audit after pytest is noisier than the learner’s own runs.

## Learner questions

- Could a stranger finish alone? On this branch, yes — $0 path and the live LangGraph smoke. Not from GitHub `main` (F1). CrewAI live is a failed row, not a stuck command.
- Single most confusing moment: week 2 still saying the live proof does not exist after a 12-minute complete.
- Lesson that landed best: two folders, one reader (week 3). Lesson that is only asserted: “the loop is gone” as a *rate* (n=1 complete, 3 retries).
- Purpose (`campaign-v2`): a stranger can run it on this branch. Start still points at `main`.

## Top 5 improvements

Ordered by learner impact per hour of work.

1. **Update week 2/6 for the live complete.** One live LangGraph smoke finished in 12.4 min for $0.05 with `retry_count=3`. Replace “not yet by a live one.”
2. **Keep Start honest (F1):** merge `course/` to `main` or change the clone line.
3. **Ship a 30-run teaching corpus** so week 4 is finishable on a fresh clone.
4. **Don’t let `pytest tests/unit` pollute `output/runs` before the week 6 audit** (name the learner ids, or isolate pytest).
5. **One sentence on CrewAI:** prototype smoke may fail DeploymentConfig; the recorded case is the required path.

## Appendix

- Observations: `observations.jsonl`
- Logs: `logs/`
- Spend: `spend.jsonl`
- Test checkout: `/var/folders/7f/trms0d492gsf9j9ydv6kp1q00000gn/T/tmp.IDbA2LA3XW/ai-team` (week 5 left on `course-test/w5`, not merged)
- Leftovers at end: none
- Deviations: skipped W2.S1 LangGraph re-run; skipped dashboard; skipped live `--n 3` LangGraph batch; two `SIMULATED:` notes in scratch only; W5 used `solutions/week-5-check.patch` on `course-test/w5` instead of `my-first-check`
- Course links: ok
