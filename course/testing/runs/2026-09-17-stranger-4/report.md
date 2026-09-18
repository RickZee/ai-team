# Course test report — 2026-09-17-stranger-4

| | |
| --- | --- |
| **Scope / mode / budget / fix / depth** | **week-5,week-6** · stranger · **$1** · no · **build** (scoped re-test after e93a0ca + 3c6cee5; not a full 24-step run) |
| **Git SHA** | `3c6cee5` on `feat/course-v2` (`e93a0ca` Anthropic `.env` / conftest isolate keys / check discovery; `3c6cee5` fixture-contract gate) |
| **Environment** | Darwin 27.0.0 · uv 0.10.2 · Python 3.12.7 |
| **Tester** | Cursor agent (Grok 4.6) · 2026-09-17 |
| **Spend** | **$0.025 recorded of $1** (+ $0.10 projected for two 25 s unset preflights with missing `costs.jsonl`). Per step: B5 LangGraph **$0.024647**. Optional `--n 3` not run (data collection, not lab validation). |
| **Wall time** | ~75 min including preflight, B1–B4, and B5's 7.5 min complete smoke |
| **Coverage** | **in-scope 9/9 = 100%** (RUN + RUN-PARTIAL + JUDGED) · **overall 9/24 = 38%** (W1–W4 SKIPPED-SCOPE by task) |
| **Previous run** | `course/testing/runs/2026-09-17-stranger-3` (SHA `ffaaa2d`, scope all, $10) |
| **Push** | not requested; cancelled |

## Verdict

A stranger on this SHA can finish weeks 5–6 on the $0 spine, write the check without the patch, and **watch the gate fail when a pass fixture is missing** — that is the line that was exit 0 last run. Empty keys still beat `.env`; after `unset`, all three backends get past the key check, including Claude. The first pytest a learner types (`tests/unit/evals`) still stays green if they only write `mine.py`; the discovery guard lives in `tests/unit/repo` and the page's last pytest. Start still clones GitHub `main` (**F1**, not re-derived). Ready to share weeks 5–6 on this branch with that pytest-order footnote; uniqueness 22 is the open decision it was before, not a new finding.

## Scorecard

| Week | Runs | Accurate | Clear | Teaches | Honest | Fits budget | Stranger can finish alone? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 · Build | — | — | — | — | — | — | SKIPPED-SCOPE |
| 2 · Fail | — | — | — | — | — | — | SKIPPED-SCOPE |
| 3 · Observe | — | — | — | — | — | — | SKIPPED-SCOPE |
| 4 · Read | — | — | — | — | — | — | SKIPPED-SCOPE |
| 5 · Evaluate | 4 | 5 | 4 | 5 | 5 | 5 | Yes without the patch; first pytest is still a liar |
| 6 · Improve | 5 | 5 | 5 | 5 | 4 | 5 | Yes on replay; live n=3 optional |

`Buildable` and `Feeds back` (weeks 5–6, `depth: build` only):

| Week | Buildable | Feeds back |
| --- | --- | --- |
| 5 · Evaluate | 5 | 5 |
| 6 · Improve | 5 | 5 |

Week 5 Runs/Clear are 4 because `uv run pytest tests/unit/evals -q` with `mine.py` only is **423 passed** — the page now names `test_check_discovery.py` and runs repo pytest last, but the first command in the Run block is still the silent one. Week 5 Buildable is 5 because B4 actually refuses a deleted pass fixture. Week 6 Honest is 4 because re-backfill still duplicates traces (R13). Week 6 Feeds back is 5: one complete LangGraph moved the check from 0 pass / 2 fail to 1 pass / 4 fail.

## Coverage

| Week | Steps | RUN | RUN-PARTIAL | JUDGED | Skipped (reason) | % |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 3 | 0 | 0 | 0 | all SKIPPED-SCOPE | 0 |
| 2 | 4 | 0 | 0 | 0 | all SKIPPED-SCOPE | 0 |
| 3 | 5 | 0 | 0 | 0 | all SKIPPED-SCOPE | 0 |
| 4 | 3 | 0 | 0 | 0 | all SKIPPED-SCOPE | 0 |
| 5 | 4 | 4 | 0 | 0 | — | 100 |
| 6 | 5 | 3 | 1 | 1 | S3 live `--n 3` SKIPPED-PAID | 100 |
| **In-scope** | **9** | **7** | **1** | **1** | | **100** |
| **All** | **24** | **7** | **1** | **1** | W1–W4 SKIPPED-SCOPE | **38** |

Under 80% overall because this was a scoped re-test, not a full 24-step run. In-scope coverage is 100%. Every skip names its reason from the skill, §4a.

## Step results

| Step | Block | Result | Exit | Time | Note |
| --- | --- | --- | --- | --- | --- |
| PREFLIGHT | empty ×3 | MATCH | 1 | ~1 s | langgraph/crewai: OPENROUTER empty. Claude: ANTHROPIC empty (not "not set") |
| PREFLIGHT | unset ×3 | MATCH | 124 | 25+ s | Watchdog armed on all three. Claude: `claude_recovery_attempt`. leftovers none |
| W5.S1 | c1 | MATCH | 0 | 1.6 s | 182 fail; harness 0.479 n=213; **22 uniqueness warnings**, none gating |
| W5.S2 | c1 | DRIFT | 0 | 0 s | 95 fixture files |
| W5.S3 | c1 | MATCH | 0 | 0 s | spend.py na/fail/pass |
| W5.S4 | c1 evals first | MISMATCH | 0 | 11.0 s | mine.py only: **423 passed** |
| W5.S4 | c1 repo | MATCH | 1 | 7.0 s | names `mine` + the import line |
| W5.S4 | no fixtures gate | MATCH | 1 | 0.9 s | completeness FAIL |
| W5.S4 | c2 dump+pytest | MATCH | 0 | 9.3 s | 427 evals; 228 fail Tier A; 16 repo |
| W6.S1 | — | JUDGED | — | — | picked CHK-trace-has-spans |
| W6.S2 | c1 | DRIFT | 0 | 1.1 s | 0 pass / 2 fail / n=2 thin |
| W6.S3 | c1 | MATCH | 0 | 60.1 s | **1688 passed** with empty keys |
| W6.S3 | c2 | MATCH | 0 | 0.2 s | replay overlap |
| W6.S3 | live n=3 | SKIPPED-PAID | — | — | optional; B5 already one live LangGraph |
| W6.S4 | c1 | MATCH | 0 | 0.1 s | `(0.0, 0.2425)` as written |
| W6.S5 | c1 | DRIFT | 0 | 0.1 s | ingested **2** (before B5 finished) |
| B5 | live | MATCH | 0 | 448.7 s | complete, retry=0, $0.025; after: 1 pass / 4 fail n=5 |

Totals (in-scope + preflight): **MATCH 13 · DRIFT 3 · MISMATCH 1 · JUDGED 1 · SKIPPED-PAID 1**. W1–W4: **SKIPPED-SCOPE 15**.

## Build track

| Task | What I predicted | What I changed | What the numbers did | Attempts | Time |
| --- | --- | --- | --- | --- | --- |
| B1 write the check | evals pytest names mine.py | `mine.py` then wiring | evals 423 green → repo names it → completeness exit 1 → 427 pass / 228 fail | 3 | ~20 min |
| B2 make it fail | sabotage caught | always-`passed()` | 4 failed including new fixture-contract test | 2 | ~5 min |
| B3 adjust the eval | 228→257 | require ≥2 spans | **exact**; reverted | 1 | ~5 min |
| B4 baseline + regression | still exit 0 (last run) | `baseline accept`; rm pass json | **gate exit 1**, completeness names the missing pass | 1 | ~5 min |
| B5 live traces | pennies, minutes | LangGraph after unset | complete 448.7 s $0.025; CORPUS 0/2 → 1/5 | 1 | 7.5 min paid |
| B6 full pipeline | green | ruff on learner files | **ruff format would reformat `trace_fixtures.py`**; unit 1688 passed | 1 | <1 min |

**Wiring points (B1)** — did `pytest` name the missing piece, or did I have to read the test?

| # | File | Message named it? | Attempts |
| --- | --- | --- | --- |
| 1 | `evals/checks/registry.py` | **Yes — if you run `tests/unit/repo`.** **No — if you run `tests/unit/evals` first** (423 passed). | 1 |
| 2 | `evals/coverage.py` | Partial — coverage / ALL_CHECK_IDS, same as last run | 1 |
| 3 | `tests/unit/evals/trace_fixtures.py` | Yes for ALL_CHECK_IDS; builder KeyError if you skip it | 1 |
| 4 | `tests/unit/evals/test_check_sensitivity.py` | Yes — `no mutation defined for CHK-trace-has-spans` | 1 |
| 5 | `evals/fixtures/traces/` | **Yes, and the gate now fails completeness without them** | 1 |
| 6 | `evals/baselines/tier_a.json` | N/A until `baseline accept` (needs a clean tree; page is right) | 1 |

- Mutation test (B2) catch a never-fail check? **Yes** — three old tests plus `test_every_check_honours_its_own_fixtures`, ~6 s.
- Gate (B4) block a deliberate regression? **Yes.** Message: readable completeness line. **Flipped vs stranger-3 exit 0.**
- Wider scope catching a narrower change: `tests/unit/repo` vs `tests/unit/evals` on `mine.py` only; ruff format on the builder; empty-key pytest now green.
- Week 5 claims 60 minutes. Actual B1–B4 ~35 min. Fair.

Full narrative: `build.md`. Diff: `my-check.diff`.

## Concept ledger

See `concepts.md`. Headline this pass:

- Baseline vs ground truth: **taught** (I deleted the pass fixture).
- Empty env vs `.env`: **taught** (was **missing** last run; Claude now matches OpenRouter).
- Week 4 taxonomy: not re-run (SKIPPED-SCOPE).

## Findings

| ID | Sev | Where | What happened | Suggested change | Evidence |
| --- | --- | --- | --- | --- | --- |
| F1 | P0 | `course/README.md` Start | `origin/main` has no `course/`. Known, not re-derived. | Merge `course/` to `main` or change Start. | (known) |
| F24 | P2 | `course/week-5-evals.md:131` + skill B1 | Page now names `test_check_discovery.py` and runs repo pytest last. The **first** pytest in the Run block (`tests/unit/evals`) with `mine.py` only is still **423 passed**. Skill B1 types that command first. | Make the first pytest `uv run pytest tests/unit/evals tests/unit/repo -q`, or move `test_check_discovery.py` into `tests/unit/evals`. | `logs/W5.S4.c1-attempt-0-evals.txt` vs `…-attempt-0-repo.txt` |
| F27 | P2 | `tests/unit/evals/trace_fixtures.py` builder | Learner's `_has_spans` fails `ruff format --check` (B6). | Format the snippet in the page / solution patch, or tell week 5 to run `ruff format` on the builder. | `logs/W5.S4.c1-b6-ruff-mypy.txt` |

**Not new this run (open by decision / still open):** 22 uniqueness warnings in `gate.md` (warn, do not fail); F25/R13 duplicate hashed traces; R10 LangGraph variance (this B5 completed; last B5 timed out).

### Closed since stranger-3

| ID | Was | Now |
| --- | --- | --- |
| F23 / R11 | Claude after `unset`: "ANTHROPIC_API_KEY is not set. Put it in `.env`" | Empty: "set but empty… unset…". After unset: Watchdog armed + `claude_recovery_attempt`. |
| F26 | empty `OPENROUTER_API_KEY=` → 4 `test_run_demo` fails | **1688 passed** |
| R12 | B4 delete pass fixture: gate **exit 0** | gate **exit 1**, completeness names the missing pass |

### Repo findings (not course text)

| ID | Where | What | Owner (spec / file) |
| --- | --- | --- | --- |
| R13 | `evals.cli trace backfill` | Still writes a new hashed filename per invocation. 2 runs → 3 built, n=5 decided. | `evals/cli.py` / `evals/trace` (known) |
| R10 | LangGraph | Variance is the data: last SHA B5 watchdog 900 s; this SHA complete 448.7 s retry=0 $0.025. | langgraph backend (known) |

## Week notes

### Weeks 1–4
SKIPPED-SCOPE. Preflight only: empty-key recipe MATCH on all three backends; unset 25 s MATCH (Claude starts).

### Week 5 · Evaluate
- Predictions: I thought evals pytest would now name `mine.py`. It does not. I thought B4 would still exit 0. It did not.
- Most confusing moment: 423 passed after writing the check the page just told me to write, then repo pytest quoting the table row.
- Scores evidence: Tier A snapshot still exact (182 / harness 0.479). Completeness gate MATCH. Uniqueness 22 expected.

### Week 6 · Improve
- Before: CORPUS n_decided=2, 2 fail, thin. After B5 complete + duplicate backfill: n_decided=5, 1 pass / 4 fail. Intervals overlap. Replay MATCH. Empty-key pytest MATCH (F26).

## Learner questions

- Could a stranger finish alone? On this branch, weeks 5–6 yes, if they read the wiring table and run the last pytest. Not from GitHub `main` (F1).
- Single most confusing moment: first pytest green with a check that is not in the registry.
- Lesson that landed best: a baseline answers "did this change?"; fixtures answer "is this right?" (B4). Lesson only asserted this pass: none in-scope — uniqueness is a warning you can ignore, which is the current decision.
- Purpose (`campaign-v2`): weeks 5–6 on this branch do what they claim, minus pytest folder order. Start still points at `main`.
- After the build track: **yes, I could add a check to a system I did not write**, if I run the discovery test. I would still copy the six-row table. I would not trust `pytest tests/unit/evals` to start the conversation.
- Concept I only understood after something went wrong: deleting one pass file is enough, now. Last run it was not.

## Since last run

Previous: `course/testing/runs/2026-09-17-stranger-3` (`ffaaa2d`, scope all, $10).

| Block | Was (`ffaaa2d`) | Now (`3c6cee5`) |
| --- | --- | --- |
| PREFLIGHT empty Claude | "not set. Put it in `.env`" (F23) | "set but empty… unset…" |
| PREFLIGHT unset Claude | would have died at key check | Watchdog armed, `claude_recovery_attempt` |
| W5.S4 mine.py only + evals pytest | 404 passed (F24) | **423 passed** (same hole, different folder) |
| W5.S4 mine.py only + repo pytest | (no discovery test) | **FAIL**, names `mine` + import |
| W5.S4 registered, no fixtures | silence / `--warn-only` exit 0 | **completeness exit 1** |
| B4 delete pass fixture | **exit 0** (R12) | **exit 1** |
| W6.S3.c1 empty keys | BROKEN, 4 failed | **MATCH 1688 passed** |
| B5 LangGraph | timeout 900 s, $0.053, 0% pass n=12 | **complete 448.7 s, $0.025**, 1 pass n=5 |
| uniqueness | (not gated) | 22 warnings, still not gated (expected) |

Spend / wall: stranger-3 **$0.78 / ~2.5 h all-weeks**. This run **$0.025 / ~75 min scoped**.

## Top 5 improvements

Ordered by learner impact per hour of work.

1. **Make the first pytest talk (F24 residual).** `uv run pytest tests/unit/evals tests/unit/repo -q` in week 5's Run block and in skill B1 — or move `test_check_discovery.py` next to the other wiring tests.
2. **Keep Start honest (F1):** merge `course/` to `main` or change the clone line.
3. **Stop backfill from minting duplicate `n` (F25 / R13):** overwrite by run id, or tell week 6 to wipe `traces-root` before before/after.
4. **Format the `_has_spans` snippet (F27)** so B6 `ruff format --check` is not the first red a learner sees after a green suite.
5. **Uniqueness 22** — not a new finding. Decide: fail the gate, or keep warn-only and stop printing 22 bullets in `gate.md` as if they were the result.

## Appendix

- Observations: `observations.jsonl`
- Steps and ids: `steps.json`
- Build log: `build.md` · check diff: `my-check.diff`
- Concept ledger: `concepts.md`
- Logs: `logs/` (re-runs carry a `-attempt-N` / `-bN` suffix)
- Spend: `spend.jsonl`
- Build branch left in the test checkout: `course-test/2026-09-17-stranger-4` @ `5040e77` in `/var/folders/7f/trms0d492gsf9j9ydv6kp1q00000gn/T/tmp.TgK6E63bpW/ai-team`
- Steps not run, and why: W1–W4 all SKIPPED-SCOPE; W6.S3 live `--n 3` SKIPPED-PAID
- Deviations: W5 branch name `course-test/$RUN_ID` not `my-first-check`; B3 tighten reverted (not committed); B4 deleted *our* pass fixture (page example used another check's); W6.S5 ingested 2 because B5 had not finished; B6 ruff format failed so mypy was not reached in that command; uniqueness 22 expected
- Course links: not re-checked this scoped pass
- Leftovers at end: none
- Remote: **not pushed**
