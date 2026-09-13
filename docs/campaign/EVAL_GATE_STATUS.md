# Eval gate status

**Last verified:** 2026-09-13 · **Verified against:** `.github/workflows/ci.yml`,
`.github/workflows/eval-nightly.yml`, `evals/traces/index.db`

This file is the single source of truth for what the eval gate does and does not
do. [`EVAL_METHODOLOGY.md`](../EVAL_METHODOLOGY.md) and
[`posts/harness-map.md`](../posts/harness-map.md) both point here. **Do not claim
a hard gate, or a measured quality rate, in a post, README badge, deck, or
showcase page unless the corresponding row below says you can.**

## Current state

| Question | Answer | Evidence |
| --- | --- | --- |
| Is Tier A running in CI? | **Yes**, every PR | `ci.yml:236` job `eval-tier-a` |
| Does Tier A cost anything? | **No — $0.00**, no secrets required | `ci.yml:264`, offline replay |
| Does Tier A block a merge? | **No.** `--warn-only` | `ci.yml:264`; flip deferred by task 9.4 |
| What does Tier A score? | **94 synthetic fixtures** (`__pass` / `__fail` / `__na`) across 21 checks under `evals/fixtures/traces/` | `ls evals/fixtures/traces/` |
| Does a green Tier A mean `ai-team` works? | **No.** It means the check code behaves as written. | see *Corpus kind* below |
| Is the nightly Tier B cron running? | **No.** Cron commented out; `workflow_dispatch` only | `eval-nightly.yml:10–20` |
| Are any judges gating? | **No.** All advisory. | `evals/golden/alignment/*.json` → `eligible_to_gate: false` |
| Have any judges been validated? | **No.** One prompt exists; its alignment report is `n: 0` | `fm-001-tool-call-omission.json` |
| Is there a human-labeled golden set? | **No.** `evals/golden/` holds no labels | `golden stats` |
| Has any trace been open-coded? | **No.** `evals/annotations/` is empty | `ls -A evals/annotations/` |
| Does the corpus read the run-record tree? | **No.** Backfill defaults to `./workspace`; 210 run records unread in `./output/runs/` | `evals/cli.py:547` |

## Corpus kind

Every rate this repo can currently produce is **`FIXTURE-ONLY`**.

| Kind | Source | What a pass rate means | Available today |
| --- | --- | --- | --- |
| `FIXTURE-ONLY` | `evals/fixtures/traces/` | the check code behaves as written | **yes** |
| `CORPUS` | indexed traces from real runs | the system behaved this way on this sample | no — see below |
| `LIVE` | a budgeted tier run just executed | the system behaves this way now | no — unspent |

The indexed corpus as of 2026-09-13: **50 traces, 0 spans, 1 backend (`crewai`),
1 scenario id (`unknown`), 1 status (`failed`), created within a 1.97-second
window** — built from `workspace/`, while 210 run records covering three backends and
69 days sit unread in `output/runs/`. It fails every diversity floor proposed in
[`eval-methodology-alignment` R4](../../.kiro/specs/eval-methodology-alignment/requirements.md).
Nothing derived from it may be reported as a `CORPUS` rate.

## What has to be true before the gate flips

The flip removes `--warn-only` from `ci.yml:264`. Preconditions, in order:

1. **The corpus reads `output/runs/`** — where the run records already are
   ([spec task 2.4](../../.kiro/specs/eval-methodology-alignment/tasks.md), free).
2. **Phase telemetry is harness-owned** — `phases.jsonl` written by harness code on the
   execution path, not requested from the agent (spec Phase 1).
3. **The corpus clears its floors** — ≥100 indexable traces, ≥3 backends,
   ≥4 scenario ids, ≥2 statuses, ≥14-day span (spec Phase 2).
4. **A week of green nightlies** on a real corpus, not on fixtures
   (`eval-harness` task 9.4 — the original condition, unchanged).
5. **Judges, if any gate**, clear TPR ≥ 0.90, TNR ≥ 0.90, κ ≥ 0.70, n ≥ 100 on the
   held-out test split (spec R12.4).

None of the five is met. **Status: warn-only, indefinitely, and correctly so.**

## Claim rules for external material

Anything published from this work — LinkedIn, X, Substack, showcase page, deck —
follows three rules:

1. **Every rate carries its corpus kind and its `n`.** A rate without `n` is a
   defect in the claim, not a rounding of it.
2. **"$0 per-PR eval gate in CI" is true and publishable.** "Our agents pass 94%
   of evals" is not, in any phrasing, until a `CORPUS` rate exists.
3. **The gap is the story.** Describing the harness as finished and fed would be a
   worse claim than describing it as built and starving — and the second one is
   the interesting half.
