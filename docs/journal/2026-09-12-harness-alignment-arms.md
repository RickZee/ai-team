# Harness alignment arms — 2026-09-12

In-repo implementation of `.kiro/specs/harness-alignment` Phases 3–11, **without**
the human-triggered live spends (tasks 4.3, 4.5, 5.4, 11.4).

## What landed

- Arms: `solo`, `harnessed_solo`, `reference` (vendored
  `anthropics/claude-quickstarts/autonomous-coding` @ `3313e97`), `ai_team`,
  and `ai_team_ablated:<component>`.
- Ladder CLI defaults to `--dry-run`; `--execute` is required for any live call.
  Sweep ceiling $25, checked before the first arm starts.
- Four new Tier A checks already backfilled (see
  `2026-09-12-harness-alignment.md`). Report refuses MIXED-MODEL / UNDERPOWERED
  comparisons without flags.
- Session loop, contract gate, and bash allowlist ship **off by default**.

## Live spend (not run)

| Task | Arm | Ceiling | Status |
| --- | --- | --- | --- |
| 4.3 | solo | $3 | not run |
| 4.5 | harnessed_solo | $6 | not run |
| 5.4 | reference | $8 | not run |
| 11.4 | full ladder n≥3 | $25 | not run |

Deltas `solo → harnessed_solo` and `harnessed_solo → ai_team` are therefore
**never measured**. The ablation store lists every component as
`never measured`. That is reported as such, not as a zero delta.

## Bash allowlist FP budget (R14.5 / 10.3)

The fail-closed parser is on (it closed the documented denylist bypasses).
The *per-role allowlist* is off (`AI_TEAM_BASH_ALLOWLIST` unset).

No live guardrail-corpus delta was collected in this change — enabling the
allowlist by default would be a preference, not a measurement. Decision:
**keep default-off** until `CHK-guardrail-fp-budget` is re-run on the fixture
corpus with the allowlist active.

## Punchline rewrite (task 11.5)

The taxonomy essay's "one of ten was the model" line is now **four of
seventeen**. FM-014, FM-015, and FM-017 are `layer: model`. That count is
computed from `evals/taxonomy/failure_modes.yaml`, not typed by hand. The
honest framing: the instruments improved; these failures were already
happening and were previously invisible.
