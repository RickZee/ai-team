# Build track — 2026-09-17-stranger-3

Throwaway branch in the test checkout: `course-test/2026-09-17-stranger-3` @ `37f3f9b`.
Not merged. Solution patch **not** applied first. Claimed W5.S4 time: 60 min. Actual B1–B4: ~35 min; B5 paid timeout added 15 min; B6 ~2 min.

## B1 — Write the check without the patch

**Predicted:** pytest would fail naming each of the six wiring points as I skipped them.

**Changed:** typed `evals/checks/mine.py` from the page, then added wiring one failure at a time.

| Attempt | What I had | pytest | Did the message name the missing piece? |
| --- | --- | --- | --- |
| 0 | `mine.py` only | **404 passed** | No. Dead code is green. The page's "if you skip one, pytest tells you which" is false until the registry import exists. |
| 1 | + `import evals.checks.mine` | 4 failed | **Partial.** `test_coverage.py` says `missing: ['CHK-trace-has-spans']` (not `_CHECK_SPAN_READS`). `test_all_check_ids_covers_every_registered_check` names `trace_fixtures.py`. Committed fail/pass fixtures named, not the dump+copy commands. |
| 2 | + `evals/coverage.py` `_CHECK_SPAN_READS` | 3 failed | ALL_CHECK_IDS + fixtures still named. Coverage went quiet. |
| 3 | + id in `ALL_CHECK_IDS` (no builder) | 5 failed, 65 errors | **No.** `KeyError: 'CHK-trace-has-spans'` in `build_for_check` pollutes every fixture test. Sensitivity also fails. I had to read the dict. |
| 4 | + `_has_spans` builder | 3 failed | **Yes** for mutation: `no mutation defined for CHK-trace-has-spans` (`test_check_sensitivity.py`). Fixtures still missing. |
| 5 | + `_mutate`: `trace.spans = []` | 2 failed | Fixtures only. |
| 6 | dump + `cp` into `evals/fixtures/traces/` | **408 passed** | — |

Clean-tree `git apply --check course/solutions/week-5-check.patch` → **exit 0**. (Fails on a dirty tree after the same edits; that is expected, not P0.)

Diff of my B1 wiring: `my-check.diff`. I did not get the wiring wrong relative to the published patch; I got the *order* wrong in the way a learner would (ids before builder).

**Re-run matrix after B1:** evals pytest green; Tier A `182 → 228` fails (`W5.S4.c2-rerun-1.txt`); pipeline not yet.

## B2 — Make it fail on purpose

1. Skill command `-k has_spans`: **408 deselected / 0 selected** (underscore vs `CHK-trace-has-spans` hyphen). Retry `-k trace-has-spans`: 4 passed (fail/pass/na + mutation).
2. Sabotage: `return passed(...)` always. Caught in ~5 s by:
   - `test_mutation_flips_pass_to_fail[CHK-trace-has-spans]`
   - `test_check_fixture_outcome[fail-fail-…]`
   - `test_check_fixture_outcome[na-not_applicable-…]`
3. `git checkout -- evals/checks/mine.py`

The course never asks for this. It was the fastest way I understood "na is a real outcome". **P2** to add as a *Change* beat.

## B3 — Tighten to two spans

**Predicted (before running):** 42 fixtures with 0 spans stay fail; 29 with 1 span flip pass→fail; 26 with 2+ stay pass; na stays 4. So CHK-trace-has-spans: **fail 70, pass 23, na 4**. Suite fails 228+29=257. Own pass fixture (1 span) will go red in unit tests.

**Actual:** fail 70 / pass 23 / na 4 on 97 fixtures. Suite **257 failed**. Exact hit. Unit tests: 2 failed (`pass` fixture + mutation assumed the pass fixture still passed).

**Finding:** a meaning change that unit tests do not know about is caught by `tests/unit/evals`, not by Tier A (Tier A happily counts more fails). I then gave the pass builder two spans and re-dumped. Suite **256 failed** (own pass fixture recovered). CORPUS still 0 pass — the live traces do not have two spans in the reader the check uses, so **the corpus has no trace that exercises "one span vs two" as a pass**. That is FIXTURE-ONLY vs CORPUS in week 5's own words.

## B4 — Baseline + sneak a regression

- `baseline accept --reason "tighten CHK-trace-has-spans"` → `CHK-trace-has-spans: fail` in `tier_a.json`. Commit `37f3f9b`.
- Deleted `CHK-tool-call-emitted__pass.json`, ran **without** `--warn-only`: **exit 0**. `tests/unit/repo` still **13 passed** (mapping only requires some fixture filename to contain the slug).
- Restored the file.

The gate compares per-check aggregate `pass`→`fail`. Every baseline outcome is already `"fail"` because fail fixtures exist, and `suite_pass_pow_k` is `0.0`. **Deleting a passing fixture is not a regression this gate can see.** P0 repo finding.

## B5 — Live traces

**Before (W6.S2):** `CHK-trace-has-spans` thin, 0 pass / 6 fail / 2 na, n=6 decided, over 8 traces on disk (duplicates). CORPUS, n_decided=6, failing=6.

**Paid run:** LangGraph watchdog **900.4 s, exit=124**, `final_status=timeout`, **no `state.json`**, `$0.053307`, `test_calc.py` present in workspace. Same stop rule as week 1. Leftovers none.

**After:** check became **live**, 0 pass / 12 fail / 5 na, 0% (n=12). `n` grew by duplicate backfills *and* one timeout run.

Wilson: pass 0/6 (0–39%) vs 0/12 (0–24%) **overlap**; fail 6/6 vs 12/12 **overlap**. One more run did **not** change the rate enough to notice. Liveness label thin→live *did* move — that is eyesight, not the agents.

## B6 — Full pipeline

With `unset` (not empty prefix): ruff + mypy 22 s green; `pytest tests/unit` **1666 passed** 68 s; Tier A 256 fail; `tests/unit/repo` 13 passed.

W6.S3.c1 with empty keys exported: 4 failed in `test_run_demo.py` (73ccfbd empty-key guard). Not caused by the check.

## Re-runs where wider scope caught a narrower change

| Change | Step | Gate (`tests/unit/evals` / Tier A) | Pipeline |
| --- | --- | --- | --- |
| mine.py only | green | green | — |
| tighten to 2 spans, 1-span pass fixture | — | **2 unit fails**; Tier A 257 fail (intended) | — |
| empty `OPENROUTER_API_KEY=` on `pytest tests/unit` | — | evals still green | **4 test_run_demo fails** |
| delete pass fixture | — | evals would fail if run; **Tier A gate exit 0** | repo pytest still green |
