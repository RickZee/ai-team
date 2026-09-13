# Harness alignment — CI / suite failures

Working log of every gate failure found while landing
`.kiro/specs/harness-alignment`, and what closed it. This is the record the
implementation journals (`2026-09-12-harness-alignment.md`,
`2026-09-12-harness-alignment-arms.md`) do not keep: they describe the feature,
not the red suite.

No GitHub Actions run exists for this change yet (uncommitted on 2026-09-13).
Rows marked **local** were reproduced with the same commands CI uses
(`pytest tests/unit`, `ruff`, `mypy`). Rows marked **risk** have not failed yet
and are the first things to read if the first Actions run is red.

## Closed (would have failed CI)

| # | Gate | Symptom | Cause | Fix |
| --- | --- | --- | --- | --- |
| 1 | Test | `test_check_sensitivity` ×4 (`CHK-acceptance-monotonic`, `CHK-premature-termination`, `CHK-verifier-independence`, `CHK-evaluator-capitulation`) | New checks were registered and in `ALL_CHECK_IDS`, so the mutation suite demanded a pass→fail flip that nobody wrote | Mutations in `tests/unit/evals/test_check_sensitivity.py` |
| 2 | Lint (N818) | `WallClockExpired`, `ClaimRefusal` | Ruff wants `*Error` suffix | Renamed to `WallClockExpiredError`, `ClaimRefusalError` |
| 3 | Test | `test_env_switch_is_case_sensitive_and_fails_open` | Spec inverted the switch: `AI_TEAM_DENY_NATIVE_TOOLS=TRUE` used to fail open | `.strip().lower()` in the hook; test now asserts deny |
| 4 | Test | `test_known_bypasses_are_not_caught_today` | R14 fail-closed parser closed the documented denylist gaps | Inverted to `test_known_bypasses_are_caught` |
| 5 | Test | `test_malformed_tool_input_does_not_raise` / `test_missing_fields_are_tolerated` on Bash | Empty command is undecomposable → deny (R14.3). Old tests expected `{}` | Write still `{}`; empty Bash now asserts deny |
| 6 | Test | `test_vendor_manifest_matches_tree` | `ruff format` rewrote the vendored quickstart | Restored pin `3313e97`; `evals/arms/vendor` excluded from Ruff and coverage |
| 7 | mypy | `evals/ladder_report.py` `float(Any \| None)`; `ui_smoke_tools` return/`Literal`; `signal.getsignal` always truthy | New modules typed against `mypy evals/` | Narrowed types; `hasattr(signal, "setitimer")` |
| 8 | Test | `test_model_layer_ratio_matches_yaml` | Essay says "four of the seventeen"; test looked for "four of the 17" | Spoken-word totals through seventeen |
| 9 | Test | `test_regression_demotes_and_prioritizes` | Loop terminates on all-pass *before* the first session, so a fully-passing list never ran R9 | Leave one item unsatisfied so the session (and regression) actually runs |
| 10 | Test | `test_r14_constructs[timeout 10 pytest -q]` | `timeout` unwrapper treated the duration as the command name | Skip a duration token after `timeout` |
| 11 | Test | `test_sleeping_arm` / dry-run plan | `resolve_plan` omitted `dry_run` | Flag set on the plan; `--execute` still required for spend |
| 12 | Coverage | Floor was 55 on `src/ai_team` only | Task 11.6 adds `evals` to the measured source and ratchets | CI `--cov=evals`; `fail_under = 60` (macOS unit run: **66%** combined; −6pt ubuntu variance) |
| 13 | Lint | `ruff format --check` would reformat `evals/checks/acceptance.py`, `context.py`, `evals/run_evals.py`, `error_handling.py` | New/touched files never formatted | `uv run ruff format` on those four |

Full unit suite after #1–#11: **1,478 passed / 4 failed**, then **20/20** sensitivity after #1. Combined line+branch **66%** (`src/ai_team` + `evals`, vendor omitted).

## Suite-isolation defects (not CI-red, would have corrupted the gate)

Found 2026-09-12; guards landed so they stay loud:

- A unit test rewrote a committed golden under `evals/golden/` (`VALIDATION_LOG` monkeypatched, `ALIGNMENT_DIR` not).
- Another test assumed `./workspace/` was empty.
- `ALL_CHECK_IDS` was a hand list: a new check could miss purity, sensitivity, and fixture suites while still sitting in the registry.

Guards: `tests/conftest.py` hashes `evals/golden/`, `evals/fixtures/traces/`, `evals/taxonomy/` for the session; `tests/unit/evals/test_suite_drift_guards.py` asserts registry ≡ `ALL_CHECK_IDS` ≡ fixtures, and no implemented FM still `reserved`.

## CI config this push changes

| File | Change |
| --- | --- |
| `.github/workflows/ci.yml` | 3.12 unit job: `--cov=evals` in addition to `src/ai_team` |
| `scripts/ci_unit_test.sh` | same `--cov=evals` so local pre-push matches |
| `pyproject.toml` | `fail_under` 55 → **60**; omit `evals/arms/vendor/*`; Ruff/mypy ignore the vendor tree |

## First-run risks (read this if Actions is red)

1. **`fail_under` on ubuntu-latest (Test 3.12).** Floor is exactly measured-minus-variance. If Linux branch coverage lands under 60%, do **not** silently drop the floor — record the ubuntu figure here and set `fail_under` to that number minus a small buffer.
2. **Lint `mypy src/` only.** Local typecheck also covered `evals/`. A `src/` regression can still sneak in from hooks / MCP / session loop.
3. **Ruff format** on the new modules and the vendored tree. Vendor is excluded; if format still touches it, the manifest test fails.
4. **`SIGALRM` wall-clock test** (`test_sleeping_arm_is_budget_exhausted`) on Linux CI. Same class as `test_run_demo.py`. If it flakes, the ceiling path needs a fake clock, not a real timer.
5. **Main-only jobs** (Integration, Web UI E2E) if this lands on `main`. This change is backend/evals; E2E should be untouched, but a `main` push still runs them.
6. **Security / pip-audit** — no new runtime deps. Playwright was already a test extra.

## Live spend (still not CI)

Tasks 4.3, 4.5, 5.4, 11.4 stay human-triggered. CI must not grow a billed arm.

## How to update this file

When a GitHub Actions job fails, add a row under **Closed** or a new **Open** section
with: run URL, job name, failing node, root cause, fix SHA. Do not delete rows —
the point is the trail.
