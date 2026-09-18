# Course test report — 2026-09-17-stranger-3

| | |
| --- | --- |
| **Scope / mode / budget / fix / depth** | all · stranger · $10 · no · **build** (defaults from `/test-course`) |
| **Git SHA** | `ffaaa2d` on `feat/course-v2` (skill: build not just walk; harness: 73ccfbd spend_guard / empty-key preflight; 8db7448 pathfix) |
| **Environment** | Darwin 27.0.0 · uv 0.10.2 · Python 3.12.7 |
| **Tester** | Cursor agent (Grok 4.6) · 2026-09-17 |
| **Spend** | **$0.78 recorded of $10** (+ $0.05 projected for CrewAI with missing `costs.jsonl`). Per step: W1 LangGraph **$0.0386** · W2 Claude **$0.686** · B5 LangGraph timeout **$0.053** · W2 CrewAI **usd null**. Optional `--n 3` not run. |
| **Wall time** | ~2.5 h including live smokes and build track (~50 min of B1–B6, plus B5's 15 min timeout) |
| **Coverage** | **24/24 steps = 100%** (RUN + RUN-PARTIAL + JUDGED) · per week below |
| **Previous run** | `course/testing/runs/2026-09-17-stranger-2` (SHA `8db7448`, depth walk) |

## Verdict

A stranger can finish the $0 spine on this branch and can complete a live LangGraph and Claude smoke, but **the week 1 `unset` recipe that saves OpenRouter breaks Claude**: preflight says `ANTHROPIC_API_KEY is not set` even when `.env` has the key. CrewAI and a second LangGraph both hit the 900 s watchdog — so the week 2 evening "all three finish" table is one n=1, not a promise. The build track is doable from the page once you import the check; **writing `mine.py` alone does not fail pytest**. Start still clones GitHub `main` (**F1**). Ready to share the labs on this branch with those two footnotes; not ready to tell people to clone `main`.

## Scorecard

| Week | Runs | Accurate | Clear | Teaches | Honest | Fits budget | Stranger can finish alone? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 · Build | 5 | 5 | 4 | 5 | 5 | 5 | Yes for LangGraph after `unset`; Claude not this week's command |
| 2 · Fail | 3 | 4 | 4 | 5 | 4 | 4 | $0 path yes; live race: Claude blocked by unset, CrewAI may timeout |
| 3 · Observe | 5 | 5 | 5 | 5 | 5 | 5 | Yes |
| 4 · Read | 5 | 5 | 4 | 3 | 5 | 4 | Mechanics yes; 30 human reads no |
| 5 · Evaluate | 5 | 5 | 4 | 5 | 5 | 5 | Yes without the patch, slower than 60 min if they trust pytest too early |
| 6 · Improve | 4 | 5 | 4 | 5 | 4 | 5 | Yes on replay; live n=3 optional |

`Buildable` and `Feeds back` (weeks 5–6, `depth: build` only):

| Week | Buildable | Feeds back |
| --- | --- | --- |
| 5 · Evaluate | 4 | 5 |
| 6 · Improve | 4 | 5 |

Week 2 Runs/Accurate/Honest are 4 because Claude's first command is BROKEN as written after the documented `unset`, and the evening live table did not match this n=1 (CrewAI timeout). Week 5 Clear is 4 because pytest stays green if you only write `mine.py`. Week 6 Honest is 4 because re-backfill duplicates traces so `n` drifts without new runs.

## Coverage

| Week | Steps | RUN | RUN-PARTIAL | JUDGED | Skipped (reason) | % |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 3 | 2 | 0 | 1 | — | 100 |
| 2 | 4 | 1 | 1 | 2 | c2 dashboard SKIPPED-SCOPE (inside S1) | 100 |
| 3 | 5 | 5 | 0 | 0 | — | 100 |
| 4 | 3 | 2 | 1 | 0 | S2 human reads SKIPPED-HUMAN (command still run) | 100 |
| 5 | 4 | 4 | 0 | 0 | — | 100 |
| 6 | 5 | 3 | 1 | 1 | S3 live `--n 3` SKIPPED-PAID | 100 |
| **All** | **24** | **17** | **3** | **4** | | **100** |

Every skip names its reason from the skill, §4a. Under 80% does not apply.

## Step results

| Step | Block | Result | Exit | Time | Note |
| --- | --- | --- | --- | --- | --- |
| W1.S1 | — | JUDGED | — | — | Protocol + smoke brief |
| W1.S2 | c1–c3 | MATCH | 0 | 8.8 / 0.1 / 0.1 s | dry run; empty logs; finalize; 0 of 1 open |
| W1.S3 | c1 | MATCH | 0 | 518.2 s | complete, retry=0, **$0.0386**, 3× `decision=fail` |
| W1.S3 | c2 | MATCH | 0 | 0 s | `test_calc.py` at workspace root |
| W2.S1 | langgraph | MATCH | — | 518 s | reused W1.S3 |
| W2.S1 | crewai | MATCH | 124 | 900.3 s | watchdog; `timed_out=False`; no cost file |
| W2.S1 | claude first | BROKEN | 1 | 0.4 s | unset → "ANTHROPIC_API_KEY is not set" despite `.env` |
| W2.S1 | claude retry | MATCH | 0 | 159.6 s | `set -a; . ./.env`; **$0.686**; 13 passed |
| W2.S1 | c2 | SKIPPED-SCOPE | — | — | dashboard |
| W2.S1 | c3 | MATCH | 0 | 0 s | claude, crewai, langgraph |
| W2.S2 | c1–c5 | MATCH | 0 | 0–5 s | `5b131bd` · `3509ca3` · `8db7448` 4 tests |
| W2.S3 | — | JUDGED | — | — | layers: all harness today |
| W2.S4 | — | JUDGED | — | — | n=1 vs evening table already disagrees |
| W3.S1 | c1–c2 | DRIFT | 0 | 1.2 s | unknown×4; **143** spans |
| W3.S2 | c1,c3–c5 | DRIFT/MATCH | 0 | <1 s | labelled backends; force crewai×4 |
| W3.S3 | c1 | DRIFT | 0 | 0.2 s | timeout vs killed; floors UNMET |
| W3.S4 | c1 | DRIFT | 0 | 1.3 s | 0 live / na 88% n=4 |
| W3.S5 | c1 | MATCH | 0 | 0 s | prompt + code writers |
| W4.S1 | c1 | DRIFT | 0 | 0.5 s | n_selected=4 |
| W4.S2 | c1 | MATCH | 0 | 0.1 s | mechanics; human SKIPPED-HUMAN |
| W4.S3 | c1 | MATCH | 0 | 0.3 s | no Downloads export; empty taxonomy |
| W5.S1 | c1 | MATCH | 0 | 1.0 s | 182 fail; harness 0.479 n=213 |
| W5.S2 | c1 | DRIFT | 0 | 0 s | 95 fixtures |
| W5.S3 | c1 | MATCH | 0 | 0 s | spend.py na/fail/pass |
| W5.S4 | c1–c2 | MATCH | 0 | ~35 min | no patch first; 228 then 256/257 fails |
| W6.S1 | — | JUDGED | — | — | picked CHK-trace-has-spans |
| W6.S2 | c1 | DRIFT | 0 | 1.2 s | 0/6 pass, n inflated by duplicate backfill |
| W6.S3 | c1 | BROKEN | 1 | 57.7 s | empty key vs pytest; B6 unset → 1666 passed |
| W6.S3 | c2 | MATCH | 0 | 0.2 s | replay overlap |
| W6.S3 | live n=3 | SKIPPED-PAID | — | — | optional; B5 already one live LangGraph |
| W6.S4 | c1 | MATCH | 0 | 0.1 s | `(0.0, 0.2425)`; own 0/6 vs 0/12 overlap |
| W6.S5 | c1 | DRIFT | 0 | 0.2 s | ingested **5** (no pytest junk) |

Totals: **MATCH 28 · DRIFT 10 · BROKEN 2 · SKIPPED-PAID 1 · SKIPPED-SCOPE 1 · SKIPPED-HUMAN 1** (plus JUDGED 4).

## W2.S1 — live table vs the page

| | langgraph (W1.S3) | crewai | claude-agent-sdk |
| --- | --- | --- | --- |
| Finished? how? | complete | **timeout** (watchdog 900 s) | BROKEN then complete after sourcing `.env` |
| Wall | **518.2 s** | 900.3 s | 159.6 s |
| `retry_count` | **0** | (no usable state) | (field absent) |
| Test file | `test_calc.py` at root | no | `test_calc.py` at root; 13 passed |
| `output/runs/.../logs/` | costs.jsonl | missing costs.jsonl | costs.jsonl only |
| Spend | $0.0386 | null (counted $0.05 projected) | $0.686 |

Page evening snapshot (`8db7448`): LangGraph 3.8 min / $0.008 / retry 0; CrewAI complete 9.8 min; Claude 3.8 min / $0.86. Same brief, later SHA, **n=1 vs n=1 vs n=1**.

B5 second LangGraph: **timeout 900 s, no `state.json`, $0.053**. Week 1's stop rule is not hypothetical.

## Build track

| Task | What I predicted | What I changed | What the numbers did | Attempts | Time |
| --- | --- | --- | --- | --- | --- |
| B1 write the check | pytest names each skip | `mine.py` then 5 wiring points | 404 pass → 4 fail → 408 pass; Tier A 182→228 | 7 | ~25 min |
| B2 make it fail | `-k has_spans` selects the fail fixture | always-`passed()` sabotage | 0 selected (hyphen); then mutation + fixture tests catch it | 2 | ~5 min |
| B3 adjust the eval | fail 70 / pass 23 / na 4 | require ≥2 spans | **exact**; suite 228→257; unit tests red until pass fixture has 2 spans | 2 | ~10 min |
| B4 baseline + regression | gate refuses a deleted pass fixture | `baseline accept`; rm pass json | **gate exit 0**; repo pytest still green | 1 | ~5 min |
| B5 live traces | one more run moves the rate | LangGraph live | thin n=6 → live n=12, still **0% pass**; intervals overlap; run timed out | 1 | 15 min paid |
| B6 full pipeline | green if the check is real | ruff, mypy, unit, Tier A, repo | all green **when keys unset** | 1 | ~2 min |

**Wiring points (B1)** — did `pytest` name the missing piece, or did I have to read the test?

| # | File | Message named it? | Attempts |
| --- | --- | --- | --- |
| 1 | `evals/checks/registry.py` | **No** — skip it and the suite stays green | 1 (had to use the page table) |
| 2 | `evals/coverage.py` | Partial — `missing: ['CHK-trace-has-spans']` in `test_coverage.py`, not the dict name | 1 |
| 3 | `tests/unit/evals/trace_fixtures.py` | Yes for ALL_CHECK_IDS; **No** for the builder (`KeyError`) | 2 |
| 4 | `tests/unit/evals/test_check_sensitivity.py` | Yes — `no mutation defined for CHK-trace-has-spans` | 1 |
| 5 | `evals/fixtures/traces/` | Yes — `no committed fail/pass fixture` | 1 |
| 6 | `evals/baselines/tier_a.json` | N/A until `baseline accept` (needs a clean tree; page is right) | 1 |

- Mutation test (B2) catch a never-fail check? **Yes** — `test_mutation_flips_pass_to_fail` and the fail/na fixture tests, ~5 s. Skill `-k has_spans` selected nothing.
- Gate (B4) block a deliberate regression? **No.** Message: none; exit 0. Unreadable is the wrong complaint — there is no message.
- Wider scope catching a narrower change: empty `OPENROUTER_API_KEY=` on `pytest tests/unit` (W6.S3 / B6); 2-span tighten vs 1-span pass fixture.
- Week 5 claims 60 minutes. Actual B1–B4 ~35 min plus reading failures. Fair if you do not apply the patch; the silent-green `mine.py` costs extra confusion, not extra typing.

## Concept ledger

See `concepts.md`. Headline lessons marked **asserted** or **missing**:

- Week 4 taxonomy: **asserted** (mechanics only; no thirty notes).
- Empty env vs `.env` vs nested Anthropic settings: **missing** from the course, hit in practice (P0 for the Claude row).

## Findings

| ID | Sev | Where | What happened | Suggested change | Evidence |
| --- | --- | --- | --- | --- | --- |
| F1 | P0 | `course/README.md:18` | `origin/main` has no `course/`. Known, not re-derived. | Merge `course/` to `main` or change Start. | `git ls-tree origin/main` |
| F23 | P0 | `course/week-1-build.md:85–87` + `scripts/run_demo.py` `_missing_api_key` | After the documented `unset`, Claude dies in 0.4 s: "ANTHROPIC_API_KEY is not set. Put it in `.env`". `.env` has it. `AnthropicAgentSdkSettings` has no `env_file`; `OpenRouterSettings` does. | Load `.env` for Anthropic the same way as OpenRouter, **or** tell week 1: unset OpenRouter empties; for Claude `set -a && . ./.env`. Change the error text so it does not blame a missing `.env`. | `logs/W2.S1.c1-claude.txt` |
| F24 | P1 | `course/week-5-evals.md:107` | "`if you skip one, pytest tells you which`" — skip the registry import and **404 tests pass**. | Add a discovery test (`evals/checks/*.py` must be imported) or say: import first, then pytest will talk. | `logs/W5.S4.c1-attempt-0.txt` |
| F25 | P1 | `course/week-6-improve.md:50` / evals backfill | Re-running `trace backfill` into the same `--traces-root` **appends** new hashed JSON. 4 runs became 8 then 14 files. Week 6 `n` is partly duplicate instrument. | `rm -rf` traces-root before before/after, or overwrite by `run_id`. | `logs/W6.S2.c1.txt`, `ls course/.work/traces \| wc` |
| F26 | P1 | `course/week-6-improve.md:63` | `pytest tests/unit -q` with empty `OPENROUTER_API_KEY=` (week 1 safety still in the shell, or the tester prefix) fails 4 `test_run_demo.py` tests on the 73ccfbd guard. | One line: `unset OPENROUTER_API_KEY ANTHROPIC_API_KEY` before pytest. Fix the tests to mock the guard. | `logs/W6.S3.c1.txt` vs `logs/W5.S4.c1-b6-pytest-unit.txt` |
| F20 | P2 | `course/week-2-fail.md:56–61` | Evening snapshot: CrewAI complete 9.8 min. This SHA: CrewAI **timeout 900 s**. LangGraph 8.6 min / $0.039 vs 3.8 min / $0.008. | Keep the snapshot, dated, and the sentence already on the page: fill what you see. Maybe add this run as a third row. | `logs/W2.S1.c1-crewai.txt`, `logs/W1.S3.c1.txt` |

### Repo findings (not course text)

| ID | Where | What | Owner (spec / file) |
| --- | --- | --- | --- |
| R11 | `src/ai_team/config/settings.py` `AnthropicAgentSdkSettings` | Nested settings, `env_prefix=ANTHROPIC_`, **no `env_file`**. After `unset`, `get_settings().anthropic.api_key == ""` while `.env` is populated. OpenRouter still works. | settings + `scripts/run_demo.py` `_missing_api_key` (73ccfbd) |
| R12 | `evals/gate.py` `_eval_deterministic_checks` | Baseline stores `"fail"` per check because fail fixtures fire. `pass`→`fail` never triggers. `suite_pass_pow_k=0.0`. Deleting a **pass** fixture: Tier A without `--warn-only` **exits 0**. | evals gate / harness-alignment |
| R13 | `evals.cli trace backfill` | Writes a new hashed filename per invocation; does not replace the previous trace for the same run. | `evals/cli.py` / `evals/trace` |
| R10 | LangGraph on `ffaaa2d` | First live smoke complete 8.6 min retry=0 $0.039 with 3 behavioral fails; second smoke **watchdog timeout**, no `state.json`. Variance is the data. | langgraph backend |

## Week notes

### Week 1 · Build
- Predictions: I thought a stubbed run would still write logs. It does not. I thought `retry_count` would count behavioral fails. It stayed 0.
- Most confusing moment: three `decision=fail` lines next to `retry_count=0`.
- Scores evidence: dry-run card MATCH; live run MATCH and slower than last evening's n=1.

### Week 2 · Fail
- Predictions: Claude fastest (true after the `.env` source); CrewAI would match the evening complete row (false).
- Most confusing moment: following week 1's `unset` and being told the key is not in `.env`.
- Recorded case + three fix commits still MATCH. The live table is honest only if you treat it as dated n=1.

### Week 3 · Observe
- Starved harness reproduces at n=4: wrong default folder, then labelled backends, then two readers disagree (`killed` vs `timeout`).
- Writer table: `phases.jsonl` still asked for in a Claude prompt; my `output/runs/.../logs/` often only has `costs.jsonl`.

### Week 4 · Read
- Sample undershoots to 4. Workbench bundle writes. Human thirty SKIPPED-HUMAN. Two `SIMULATED:` notes in scratch only.

### Week 5 · Evaluate
- Tier A snapshot still exact (182 / harness 0.479). Writing the check without the patch works; the first pytest is a liar. Tightening moved FIXTURE-ONLY numbers exactly as predicted and did not move CORPUS pass rate.

### Week 6 · Improve
- Before: CORPUS n_decided=6, 6 fail, thin. After B5 timeout + duplicate backfill: n_decided=12, 12 fail, live, 0% pass. Intervals overlap. Replay MATCH. Pytest pollution from last run **did not reproduce** (F17).

## Learner questions

- Could a stranger finish alone? On this branch, the $0 path yes. Live Claude: not after the documented unset. Live CrewAI: maybe a 15-minute timeout. Not from GitHub `main` (F1).
- Single most confusing moment: week 1 says unset so `.env` wins; Claude says the key is missing from `.env`.
- Lesson that landed best: two readers disagree, and disagreement is the finding (W3.S3 + CrewAI killed vs timeout). Lesson that is only asserted: open-coding thirty traces.
- Purpose (`campaign-v2`): a stranger can run most of it on this branch. Start still points at `main`.
- After the build track: **yes, I could add a check to a system I did not write**, if that system has a registry test that fails when a module is not imported. This one does not, until you import. I would copy the six-row table, not trust pytest to start the conversation.
- Concept I only understood after something went wrong: empty env vars are not the same as "read `.env`". Also: `n` from backfill is not `n` from `output/runs` unless you wipe the traces folder.

## Since last run

Previous: `course/testing/runs/2026-09-17-stranger-2` (`8db7448`, walk, no build track).

| Block | Was (`8db7448`) | Now (`ffaaa2d`) |
| --- | --- | --- |
| W1.S3.c1 | MATCH complete 226 s retry=0 $0.008 | MATCH complete **518 s retry=0 $0.039** |
| W2.S1 crewai | MATCH complete 588 s, 5 tests | MATCH **timeout 900 s**, no tests, no costs.jsonl |
| W2.S1 claude | MATCH $0.860 after unset | **BROKEN** after unset; MATCH $0.686 after `source .env` |
| W5.S4 | MATCH via **solution patch** | MATCH **without patch**, 7 pytest attempts |
| W6.S2.c1 | live 60% n=10 | thin then live, **0% pass n=6→12** (tightened check + duplicates) |
| W6.S3.c1 | MATCH 1656 passed | BROKEN empty-key prefix; B6 unset 1666 passed |
| W6.S5.c1 | DRIFT ingested 14 | DRIFT ingested **5** (F17 did not reproduce) |

Last run Top 5 #5 (unset after dry run) **landed in week 1 copy** and **caused F23** for Claude. Last run F20 (stale CrewAI failure) was rewritten to an evening complete snapshot; this run's CrewAI row is a timeout again.

Spend / wall: stranger-2 **$0.89 / ~50 min walk**. This run **$0.78 recorded / ~2.5 h build**.

## Top 5 improvements

Ordered by learner impact per hour of work.

1. **Make Claude see `.env` after `unset` (F23 / R11).** Same preflight that week 1 now teaches. One `env_file=".env"` (or export snippet) unblocks the third backend.
2. **Keep Start honest (F1):** merge `course/` to `main` or change the clone line.
3. **Make skipped wiring loud (F24):** a check file that is not imported must fail pytest. Until then, the W5.S4 table is the real teacher.
4. **Stop backfill from minting duplicate `n` (F25 / R13):** overwrite by run id, or tell week 6 to wipe `traces-root` before before/after.
5. **`unset` before week 6 pytest (F26)** — and/or stop the empty-key guard from breaking `test_run_demo.py`.

## Appendix

- Observations: `observations.jsonl`
- Steps and ids: `steps.json`
- Build log: `build.md` · check diff: `my-check.diff`
- Concept ledger: `concepts.md`
- Logs: `logs/` (re-runs carry a `-rerun-N` / `-attempt-N` / `-bN` suffix)
- Spend: `spend.jsonl`
- Build branch left in the test checkout: `course-test/2026-09-17-stranger-3` @ `37f3f9b` in `/var/folders/7f/trms0d492gsf9j9ydv6kp1q00000gn/T/tmp.166I4zt7aE/ai-team`
- Steps not run, and why: W2.S1.c2 dashboard SKIPPED-SCOPE; W4.S2 human reads SKIPPED-HUMAN (mechanics run); W6.S3 live `--n 3` SKIPPED-PAID
- Deviations: W2.S1 LangGraph not re-run (W1.S3); Claude retried after recorded BROKEN; W5 branch name `course-test/$RUN_ID` not `my-first-check`; two `SIMULATED:` notes in TEST `course/.work` only; B5 live LangGraph timed out (still measured)
- Course links: ok
- Leftovers at end: none
