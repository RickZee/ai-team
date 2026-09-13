# Harness alignment Phase 2 backfill — 2026-09-12

Retroactive scoring of the existing corpus with the four new Tier A checks
(FM-014…FM-017). No new model spend.

## What ran

`python -m evals.cli run --tier A` over traces already in `evals/traces/` plus
the committed fixtures under `evals/fixtures/traces/`.

## What the new checks found

| Check | FM | On existing live traces | Notes |
| --- | --- | --- | --- |
| `CHK-acceptance-monotonic` | FM-014 | inconclusive | No `ACCEPTANCE.json` / `logs/acceptance.jsonl` in the pre-alignment corpus. Expected: the list did not exist yet. |
| `CHK-premature-termination` | FM-015 | inconclusive | `context_pressure` was not recorded on `phase_end` spans. The field is now emitted as `None` when the window is unknown rather than guessed. |
| `CHK-verifier-independence` | FM-016 | inconclusive | No `acceptance_passes` transitions with `VerifierIdentity`. |
| `CHK-evaluator-capitulation` | FM-017 | inconclusive | No `docs/qa_verdicts.jsonl` in the historical workspaces. |

The fixtures (`CHK-*-monotonic/termination/independence/capitulation__{fail,pass,na}.json`)
are the first traces these checks can score with a determinate outcome. Live arms
in later phases will populate the artifacts these checks read.

## Why this is still a result

Absence here is evidence, not a pass. The checks refuse to treat "we never
recorded the signal" as "the failure did not happen" — they return
`not_applicable` / inconclusive and stay out of the pass-rate denominator.
That is the point of landing them before any new dollar is spent.
