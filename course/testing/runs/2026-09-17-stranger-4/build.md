# Build track — 2026-09-17-stranger-4

Throwaway branch in the test checkout: `course-test/2026-09-17-stranger-4` @ `5040e77` (Accept baseline) after `a9b0901` (Add CHK-trace-has-spans).
Not merged, not pushed. Solution patch **not** applied first. `git apply --check` on **3c6cee5 = 0**; fails on the dirty/already-applied tree (expected).

Claimed W5.S4 time: 60 min. Actual B1–B4 ~35 min; B5 paid 448.7 s; B6 ruff format check 0.1 s (red).

## B1 — Write the check without the patch

**Predicted:** `pytest tests/unit/evals` would now fail and name `mine.py`, because F24 was the point of `e93a0ca`.

**Changed:** typed `evals/checks/mine.py` from the page, then added wiring one failure at a time.

| Attempt | What I had | pytest | Did the message name the missing piece? |
| --- | --- | --- | --- |
| 0a | `mine.py` only | **evals: 423 passed** | **No.** Discovery does not live here. Skill B1 and the page's first pytest still use this folder. |
| 0b | `mine.py` only | **repo: 1 failed, 15 passed** | **Yes.** `test_every_check_module_is_imported_by_ensure_checks_loaded` names `mine` and the exact import line in `registry.py`. |
| 1 | + `import evals.checks.mine` | evals 5 failed (no fixtures); **Tier A without `--warn-only` exit 1** | **Yes, completeness.** `fixture:completeness:CHK-trace-has-spans` — no committed pass/fail/na fixture. Last run this path was silence. |
| 2 | dump + remaining wiring | **427 passed**; repo **16 passed**; Tier A 228 fail `--warn-only` exit 0 | — |

Clean-tree `git apply --check course/solutions/week-5-check.patch` on 3c6cee5 → **exit 0**.

Diff of my B1 wiring: `my-check.diff`.

**Re-run matrix after B1:** evals pytest green; Tier A `182 → 228` fails; repo 16 passed; pipeline not yet.

## B2 — Make it fail on purpose

1. Skill `-k has_spans` still selects nothing (hyphen in the id). Retry `-k trace-has-spans` works.
2. Sabotage: `return passed(...)` always. Caught in ~6 s by **4** tests:
   - `test_mutation_flips_pass_to_fail[CHK-trace-has-spans]`
   - `test_check_fixture_outcome[fail-…]`
   - `test_check_fixture_outcome[na-…]`
   - **new:** `test_every_check_honours_its_own_fixtures` (fixture contract)
3. Reverted.

## B3 — Tighten to two spans

**Predicted:** suite 228→257 fails. Same 29 one-span fixtures as last run.

**Actual:** **257 failed.** Exact hit. Reverted without committing the tighten (B4 was about completeness, not a tighter meaning).

CORPUS still had no trace that exercises one-span vs two-span as a pass — FIXTURE-ONLY vs CORPUS in the page's own words.

## B4 — Baseline + sneak a regression

- `baseline accept --reason "add CHK-trace-has-spans"` → commit `5040e77`.
- Deleted `CHK-trace-has-spans__pass.json`, ran **without** `--warn-only`: **exit 1**.
- `gate.md`: `fixture:completeness:CHK-trace-has-spans has no committed pass fixture. Every check needs all three outcomes, including a reason to abstain.`
- Restored the file.

**Last run (ffaaa2d): gate blocked regression? No. exit 0.** **This run: Yes. exit 1.** R12 flipped.

## B5 — Live traces

**Before (W6.S2):** `CHK-trace-has-spans` thin, 0 pass / 2 fail, n=2 (killed 25 s preflights labelled failed).

**Paid run:** LangGraph **complete 448.7 s**, retry=0, **$0.024647**, `test_calc.py` at workspace root, leftovers none. After `unset`, the key check passed (the F23 re-check).

**After:** check 1 pass / 4 fail, n=5 (backfill also rebuilt the two killed runs under new hashes — R13, not new). First CORPUS pass I have seen on this check. Wilson still overlaps; the "0 → 1 pass" is visible as a count, not as a CI.

## B6 — Full pipeline

`ruff format --check` on the learner files: **Would reformat `tests/unit/evals/trace_fixtures.py`**. Exit 1. Concurrent leftover listed in `.meta` was B5, not a leak (final `ps` = none).

`pytest tests/unit` with empty keys (W6.S3): **1688 passed**. That is F26 closed.

## Re-runs where wider scope caught a narrower change

| Change | Step | Gate (`tests/unit/evals` / Tier A) | Pipeline |
| --- | --- | --- | --- |
| mine.py only | evals **green** | — | **repo pytest names mine** |
| registered, no fixtures | evals 5 fail | **Tier A exit 1 completeness** | — |
| always-pass sabotage | — | **4 unit fails** including fixture contract | — |
| delete pass fixture | — | **Tier A gate exit 1** (flipped) | — |
| learner `_has_spans` builder | — | evals green | **ruff format --check red** |
| empty `OPENROUTER_API_KEY=` on `pytest tests/unit` | — | — | **1688 passed** (was 4 fails) |
