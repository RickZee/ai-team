# Build track — 2026-09-18-stranger

Throwaway branch in the test checkout: `course-test/2026-09-18-stranger` @ `a4bc571` (Accept baseline) after `f7c7068` (Add CHK-trace-has-spans).
Not merged, not pushed. Solution patch **not** applied first. `git apply --check` on **2cb0a45 = 0**.

Claimed W5.S4 time: 60 min. Actual B1–B4 ~25 min; B5 watchdog 900 s; B6 ruff 0.8 s + mypy 22 s + unit 62 s.

## B1 — Write the check without the patch

**Predicted:** `pytest tests/unit/evals` would still stay green (last run). Skill §9 said it should now go red.

**Changed:** typed `evals/checks/mine.py` from the page, then added wiring one failure at a time.

| Attempt | What I had | pytest tests/unit/evals | Did the message name the missing piece? |
| --- | --- | --- | --- |
| 0 | `mine.py` only | **1 failed, 429 passed** | **Yes.** `test_check_discovery.py` names `mine` and the import line. **F24 flipped.** |
| 1 | + registry import | 5 failed | **Yes** — coverage reads entry, ALL_CHECK_IDS, completeness, committed fail/pass fixtures. Gate without `--warn-only`: completeness exit 1, readable. |
| 2 | + coverage, builder, ALL_CHECK_IDS, mutation; no dump | 3 failed | Completeness / committed fixtures only. Dump is the remaining row. |
| 3 | dump + `cp` | **434 passed** | — |

Clean-tree `git apply --check course/solutions/week-5-check.patch` on 2cb0a45 → **exit 0**.

Diff: `my-check.diff`.

**Re-run matrix after B1:** evals pytest green; Tier A `182 → 228`; repo **13 passed** (discovery no longer lives here); CORPUS 0/4 n=4 thin.

## B2 — Make it fail on purpose

1. Skill `-k has_spans`: **434 deselected / 0 selected**. `-k trace-has-spans`: 4 passed.
2. Sabotage always-`passed()`. Caught ~6 s by the same four tests as last run (mutation, fail fixture, na fixture, `test_every_check_honours_its_own_fixtures`).
3. `git checkout -- evals/checks/mine.py`

## B3 — Tighten to two spans

**Predicted:** 228→257.

**Actual:** **257 failed.** Exact hit. Reverted without committing (B4 was completeness, not a tighter meaning).

## B4 — Baseline + sneak a regression

Already accepted at B1 (`a4bc571`). Deleted `CHK-trace-has-spans__pass.json`, ran **without** `--warn-only`: **exit 1**. `gate.md` names the missing pass fixture. Restored.

Still flipped vs stranger-3. Holds vs stranger-4.

## B5 — Live traces

**Before (wiped traces, `output/runs` backfill):** 0 pass / 4 fail, n=4, thin (four placeholder dry runs).

**Paid run:** LangGraph **watchdog 900.3 s, exit=124**, `timed_out=False`, `final_status=timeout`, **no `state.json`**, **$0.022245**, `test_calc.py` present. Leftovers none. R10, not a regression.

**After (wipe + backfill):** 0 pass / 4 fail / 1 na (killed). The timeout run exercised the abstain path. It did not add a CORPUS pass.

## B6 — Full pipeline

`ruff format --check` on learner files: **5 files already formatted**. F27 closed.
`mypy src`: clean.
`pytest tests/unit` with empty keys: **1692 passed**.

## Re-runs where wider scope caught a narrower change

| Change | Step | Gate | Pipeline |
| --- | --- | --- | --- |
| mine.py only | **evals pytest names mine** | — | — |
| registered, no fixtures | 5 unit fails | **Tier A exit 1 completeness** | — |
| wiring, no dump | 3 unit fails | completeness | — |
| always-pass sabotage | — | **4 unit fails** | — |
| delete pass fixture | — | **Tier A exit 1** | — |
| learner `_has_spans` builder | — | evals green | **ruff format green** (was red) |
