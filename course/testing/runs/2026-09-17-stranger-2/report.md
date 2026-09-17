# Course test report — 2026-09-17-stranger-2

| | |
| --- | --- |
| **Scope / mode / budget / fix** | all · stranger · $10 · no (defaults from `/test-course`) |
| **Git SHA** | `8db7448` on `feat/course-v2` (pathfix: write what was asked) |
| **Environment** | Darwin 27.0.0 · uv 0.10.2 · Python 3.12.7 |
| **Tester** | Cursor agent (Grok 4.6) · 2026-09-17 |
| **Spend** | **$0.89 of $10.** W1 LangGraph **$0.008** · W2 CrewAI **$0.021** · W2 Claude **$0.860** (under $1). Optional `--n 3` not run. |
| **Wall time** | ~50 min including three live smokes (3.8 + 9.8 + 3.8 min). |
| **Previous run** | `course/testing/runs/2026-09-17-stranger` (SHA `396a348`, budget $10) |

## Verdict

On this SHA a stranger can finish the $0 spine **and all three live smokes complete**: LangGraph in **3.8 min with zero retries**, CrewAI in **10 min with passing tests**, Claude in **3.8 min for $0.86**. Start still clones GitHub `main`, which has no `course/` (**F1**). Ready to share the labs on this branch; not ready to tell people to clone `main`.

## Scorecard

| Week | Runs | Accurate | Clear | Teaches | Honest | Fits budget | Stranger can finish alone? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 · Build | 5 | 5 | 5 | 5 | 5 | 5 | Yes, including the live run |
| 2 · Fail | 5 | 4 | 5 | 5 | 4 | 5 | Yes; live race now 3/3 finish |
| 3 · Observe | 5 | 5 | 5 | 5 | 5 | 5 | Yes |
| 4 · Read | 5 | 5 | 4 | 3 | 5 | 4 | Mechanics yes; 30 human reads no |
| 5 · Evaluate | 5 | 5 | 4 | 5 | 5 | 5 | Yes with the patch |
| 6 · Improve | 5 | 5 | 5 | 5 | 4 | 5 | Yes on the replay path |

Week 2 Accurate/Honest are 4 because the page still snapshots this morning’s CrewAI failure and says the pathfix has no live run. Both are stale after this checkout.

## Step results

| Step | Block | Result | Exit | Time | Note |
| --- | --- | --- | --- | --- | --- |
| W1.S2 | c1–c3 | MATCH | 0 | 8.6 / 0.1 / 0.1 s | dry run + empty logs + finalize |
| W1.S3 | c1 first | BROKEN | 1 | 3.4 s | empty `OPENROUTER_API_KEY` in tester shell overrode `.env` |
| W1.S3 | c1 retry | MATCH | 0 | 226 s | **complete, retry=0, $0.008** |
| W1.S3 | c2 | MATCH | 0 | 0 s | `test_calc.py` at workspace root |
| W2.S1 | langgraph | SKIPPED-PAID | — | — | reused W1.S3 |
| W2.S1 | crewai | MATCH | 0 | 588 s | **complete**; pytest 5 passed |
| W2.S1 | claude | MATCH | 0 | 228 s | **$0.860 < $1** |
| W2.S1 | c2 | SKIPPED-SCOPE | — | — | dashboard |
| W2.S1 | c3 | MATCH | 0 | 0 s | claude, crewai, langgraph |
| W2.S2 | c1–c5 | MATCH | 0 | 0–5 s | evidence; `5b131bd`; `3509ca3`; **`8db7448` 4 tests** |
| W3 | all | MATCH/DRIFT | 0 | <2 s | 5 traces; default 123 spans vs output/runs 3 |
| W4.S1 | c1 | DRIFT | 0 | 0.5 s | n_selected=5 |
| W4.S3 | c1 | MATCH | 0 | 0.3 s | annotate gated |
| W5.S1 | c1 | MATCH | 0 | 1.0 s | 182 fail; harness 0.479 n=213 |
| W5.S4 | c2 | MATCH | 0 | 18 s | 228 fails; n=5; branch `course-test/w5` |
| W6.S2 | c1 | MATCH | 0 | 1.3 s | CHK-trace-has-spans **live 60% n=10** |
| W6.S3 | c1 | MATCH | 0 | 57 s | 1656 passed; polluted `output/runs` |
| W6.S3 | c2 | MATCH | 0 | 0.2 s | replay overlap |
| W6.S3 | live n=3 | SKIPPED-PAID | — | — | optional; W1.S3 already live |
| W6.S4 | c1 | MATCH | 0 | 0.1 s | `(0.0, 0.2425)` |
| W6.S5 | c1 | DRIFT | 0 | 0.2 s | ingested 14 after pytest leftovers |

Totals: **MATCH 30 · DRIFT 9 · BROKEN 1 (tester env) · SKIPPED-PAID 2 · SKIPPED-SCOPE 1 · SKIPPED-HUMAN 1**

## W1.S3 — live check of `8db7448` (pathfix)

| Question | This run (`8db7448`) | Previous (`396a348`) |
| --- | --- | --- |
| Wall time | **226 s** | 742 s |
| Completes before 15 min? | **Yes** | Yes |
| `retry_count` | **0** | 3 of 3 |
| `route_after_behavioral decision=fail` | **0** | 0 |
| Nested workspace | **False** | False |
| `completed_at` / `final_status` | **set / complete** | set / complete |
| Test file | **`test_calc.py` at root** (brief path) | `test_calc.py` (plus retries) |
| Spend | **$0.008** | $0.054 |
| Leftovers | none | none |

**Conclusion:** the third layer (two write paths, house-style lint, QA with no `read_file`) has a live n=1 with **zero retries**. Still not a rate. Week 6 should say so.

## Findings

| ID | Sev | Where | What happened | Suggested change | Evidence |
| --- | --- | --- | --- | --- | --- |
| F1 | P0 | `course/README.md:18` | `origin/main` has no `course/`. Known, not re-derived. | Merge `course/` to `main` or change Start. | `git ls-tree origin/main` |
| F20 | P2 | `course/week-2-fail.md` ~L52 and ~L127; `week-6-improve.md` ~L27 | Page snapshots CrewAI failing DeploymentConfig in 14 min, and says the last two fixes have no live run. This SHA: CrewAI **complete** in 10 min; LangGraph **complete in 3.8 min, retry=0**. | Replace those sentences with today’s numbers and keep “n=1 is not a rate.” | `logs/W1.S3.c1-retry.txt`, `logs/W2.S1.c1-crewai.txt` |
| F17 | P2 | `course/week-6-improve.md` S3 then S5 | `pytest tests/unit` still leaves extra folders in `output/runs`; step 5 ingested **14** runs. | Point the audit at the week 1–2 ids, or isolate pytest. | `logs/W6.S5.c1.txt` |
| F22 | P2 | week 1 dry-run prefix → paid run | An empty `OPENROUTER_API_KEY` in the environment beats `.env`. First paid attempt died in 3.4 s (`openrouter_api_key=''`). After `unset`, it worked. | One line after the dry run: `unset OPENROUTER_API_KEY ANTHROPIC_API_KEY` so the next command reads `.env`. | `logs/W1.S3.c1.txt` |

Previous F15 (page said “not yet live”) was **addressed in this SHA’s course text** (n=1, 12.4 min, retry=3). It is now **stale in the other direction** — see F20.

Previous F16 (CrewAI DeploymentConfig abort) **does not reproduce** on `8db7448`.

## Repo findings (not course text)

| ID | Where | What | Owner |
| --- | --- | --- | --- |
| R10 | LangGraph after `8db7448` | Live smoke **complete in 3.8 min, retry_count=0**, files at the brief paths. | `file_tools.py`, QA `read_file`, workspace `ruff.toml` |
| R8 | CrewAI | Live smoke **complete**; pytest 5 passed. `costs.jsonl` still reports `$0.000236` vs log `actual_cost_usd=0.021`. | crewai backend + cost writer |
| R9 | Claude `run.json` | Completes under $1. Timestamps still look like finalize-time (not re-checked this run). | SDK backend |

## Since last run

Previous: `course/testing/runs/2026-09-17-stranger` (`396a348`).

| Block | Was | Now |
| --- | --- | --- |
| W1.S3.c1 | MATCH complete 742 s retry=3 $0.054 | **MATCH complete 226 s retry=0 $0.008** |
| W2.S1 crewai | MATCH failed DeploymentConfig 850 s | **MATCH complete 588 s, 5 tests** |
| W2.S1 claude | MATCH $0.899 | MATCH **$0.860** |
| W2.S2.c5 | (new) | **MATCH** `8db7448` + 4 path-fidelity tests |
| W6.S2.c1 | MATCH thin n=8 | MATCH **live 60% n=10** |
| W4.S3.c1 | MATCH gated | MATCH gated (no regression) |

Last run’s Top 5 #1 (update “not yet live”) landed in `8db7448` course copy. Last run’s Top 5 #5 (CrewAI DeploymentConfig sentence) also landed — and is already outdated.

Spend / wall: morning $0.98 of $10 in ~70 min (CrewAI failed); this run **$0.89 of $10 in ~50 min**, 3/3 live completes.

## Week notes

### Week 1
Dry-run card matches. Live smoke is now the easy part on this SHA (3.8 min). The empty-key footgun is the only snag.

### Week 2
Recorded case + three fix commits (`5b131bd`, `3509ca3`, `8db7448`) plus a live table that is finally all green. Update the CrewAI snapshot.

### Weeks 3–6
Unchanged $0 spine. CHK-trace-has-spans is live on this tiny corpus. Pytest still pollutes the week 6 audit. Week 6 copy still says pathfix has no live run.

## Learner questions

- Could a stranger finish alone? On this branch, yes — $0 path and all three live smokes. Not from GitHub `main` (F1).
- Single most confusing moment: week 2 describing a CrewAI failure that no longer happens, next to a LangGraph “no live run” claim that this command just disproved.
- Lesson that landed best: each harness fix uncovers the next layer (week 2). Lesson that is only asserted: any *rate* (“the loop is gone”) — n is still 1.
- Purpose (`campaign-v2`): a stranger can run it on this branch. Start still points at `main`.

## Top 5 improvements

Ordered by learner impact per hour of work.

1. **Update week 2/6 for this SHA’s live table.** LangGraph 3.8 min / $0.008 / retry=0; CrewAI complete in 10 min with tests. Keep “n=1 is not a rate.”
2. **Keep Start honest (F1):** merge `course/` to `main` or change the clone line.
3. **Ship a 30-run teaching corpus** so week 4 is finishable on a fresh clone.
4. **Don’t let `pytest tests/unit` pollute `output/runs`** before the week 6 audit.
5. **One line after the dry run:** `unset OPENROUTER_API_KEY ANTHROPIC_API_KEY` so an empty prefix cannot override `.env`.

## Appendix

- Observations: `observations.jsonl`
- Logs: `logs/`
- Spend: `spend.jsonl`
- Test checkout: `/var/folders/7f/trms0d492gsf9j9ydv6kp1q00000gn/T/tmp.MXGd3JbfdN/ai-team` (week 5 left on `course-test/w5`, not merged)
- Leftovers at end: none
- Deviations: skipped W2.S1 LangGraph re-run; skipped dashboard; skipped live `--n 3`; two `SIMULATED:` notes in scratch only; W5 used `solutions/week-5-check.patch` on `course-test/w5`; W1.S3 retried after `unset` (first attempt was tester-env)
- Course links: ok
