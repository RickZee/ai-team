# Eval Methodology

Error-analysis-first methodology for the ai-team eval harness
([Husain & Shankar](https://eugeneyan.com/writing/eval-analysis/) style), as implemented
in `.kiro/specs/eval-harness/`.

## Principles

1. **Traces before scores.** Every run becomes an immutable Trace. Scoring is a pure
   function of traces (plus optional cached judge verdicts).
2. **Cheap detection first.** If a failure mode can be decided by code, it gets a
   Check. Judges are the exception.
3. **Binary over Likert.** Gating judges answer one yes/no question from a versioned
   prompt file. Continuous `LLMJudge.check()` scores remain for legacy callers but are
   deprecated for gates.
4. **Ground truth is human.** Open coding shows **no** LLM suggestions (R3.7). The
   golden `test` split is touched once per prompt version.
5. **Every rate carries `n` and a CI.** Wilson intervals on pass rates; bootstrap CIs
   on judge TPR/TNR.
6. **Errors are not failures.** A timed-out judge is `verdict: error`, excluded from
   denominators — never coerced to `fail`.

## Loop

```
workspace logs  →  Trace corpus  →  open coding (human)
                                 →  axial coding → taxonomy YAML
                                 →  deterministic checks
                                 →  golden labels (human) → judge align/validate
                                 →  SuiteReport → gate
```

## Golden set and splits

Labeling units are `(trace_id, span_id|"run", failure_mode_id)`. Split assignment is
deterministic:

```text
split = "test" if int(sha256(labeling_unit_id)[:8], 16) % 100 < 40 else "dev"
```

- `judge align` reads **dev** only (iterate prompts here).
- `judge validate` reads **test** only, once per `prompt_hash` unless `--allow-retest`.

Eligibility to gate requires TPR ≥ 0.90, TNR ≥ 0.90, κ ≥ 0.70, n ≥ 100 on test.
Below that, judges are **advisory** only.

## Bias correction

Given observed judge positive rate `p̂` and validated TPR/TNR:

```text
p = (p̂ + TNR − 1) / (TPR + TNR − 1)   clamped to [0, 1]
```

When `TPR + TNR − 1 ≤ 0.2`, the correction is suppressed (unstable) and the report
shows the raw rate only.

## Open-coding status (honest)

Task **5.2** (annotate ≥100 production traces to saturation) is **human work** and was
**not** performed by the implementing agent. Model-labeled ground truth would make
every downstream number meaningless.

Current state:

| Item | Status |
| --- | --- |
| Annotation TUI | Implemented (`evals/annotate.py`) |
| Backfilled live corpus | 50 traces indexed (of ~315 workspaces); sample seed=1 selected 50 with shortfall noted in imbalances |
| Taxonomy examples | Synthetic check fixtures (fail/pass), not production open-coding |
| Judge alignment | Advisory fixtures only — no live $ align run |
| Check validation | Against fixture fail/pass pairs |

When you run open coding: sample with
`uv run python -m evals.cli sample --strategy stratified -n 100 --seed 1`, annotate,
then `taxonomy propose --from-annotations`.

## Limitations

- **Single annotator** (benevolent dictator) — no multi-rater κ on labels yet.
- **Small live corpus / unknown scenario_ids** on many backfilled demo workspaces.
- **Anthropic vendor-overlap confound** for Claude Agent SDK backend when judges also
  use Anthropic — single-vendor verdicts cannot settle cross-backend comparisons (R7.6).
- **Judges are advisory** until a human golden set + budgeted `judge validate` clears
  the bar (`evals/golden/alignment/*.json` records `eligible_to_gate: false`).
- **All seeded FMs use `detection: check`** in v1; none are `manual` or `judge` yet.
  Retiring unsupported FMs awaits real open coding.
- **Guardrail corpora** below `min_cases` are reported as **provisional** and excluded
  from gating.
- **Tier C live validation** (≤$5) and **judge align** (≤$1) are human-triggered spend
  and were not executed in the scaffolding PR; see `docs/eval-runs/`.
- **Gate soak:** CI runs Tier A with `--warn-only` until a week of green nightlies
  (task 9.4).
