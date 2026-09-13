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

**Audited 2026-09-13.** The machinery below is implemented and typed. None of it has
run on real data. Full findings:
[`journal/2026-09-13-eval-methodology-audit.md`](journal/2026-09-13-eval-methodology-audit.md).
Remediation spec:
[`.kiro/specs/eval-methodology-alignment/`](../.kiro/specs/eval-methodology-alignment/).

### Corpus state (as of 2026-09-13)

| Measure | Value | Floor (spec R4) |
| --- | --- | --- |
| Indexed traces | 50 | ≥ 100 |
| Spans across all traces | **0** | — |
| Distinct backends | 1 (`crewai`) | ≥ 3 |
| Distinct scenario ids | 0 (all `unknown`) | ≥ 4 |
| Distinct statuses | 1 (`failed`) | ≥ 2 |
| Creation span | **1.97 seconds** | ≥ 14 days |
| Run workspaces on disk | 440 (221 empty, 219 artifacts-only) | — |
| Workspaces containing `logs/*.jsonl` | **0** | — |

Stamp: **`NON-REPRESENTATIVE`** — every floor unmet. No rate derived from this corpus
may be published (see [campaign/EVAL_GATE_STATUS.md](campaign/EVAL_GATE_STATUS.md)).

### Loop state

| Item | Status |
| --- | --- |
| Annotation TUI | Implemented (`evals/annotate.py`) — **never used on real traces** |
| Traces open-coded by a human | **0** (`evals/annotations/` is empty) |
| Failure modes derived from observation | **0 of 17** — FM-001…013 from the essay, FM-014…017 from external references |
| Taxonomy examples | Synthetic check fixtures (fail/pass), not production open-coding |
| Golden labels | **0** |
| Judge alignment | 1 prompt for 17 FMs; report is `n: 0`, `eligible_to_gate: false` |
| Check validation | Against 94 synthetic fixture fail/pass/na triples |
| Tier A corpus kind | **`FIXTURE-ONLY`** |

### Root cause (two parts)

**1. The corpus is built from the wrong tree.** `trace backfill` defaults to
`--workspace-root ./workspace` (`evals/cli.py:547`), which holds only the code the agents
generated. The harness's own run records live in `./output/runs/`:

| `output/runs/` | count |
| --- | --- |
| dated run directories | 211 |
| `run.json` — backend, workspace_dir, completed_at, final_status | 210 |
| `state.json` — actual cost, total tokens | 141 |
| `logs/costs.jsonl` | 60 |
| `receipt.json` + `receipt.md` | 8 |

Backends recorded: `langgraph` 148, `crewai` 1, `claude-agent-sdk` 1, unset 60. Date range
**2026-07-06 → 2026-09-13, a 69-day span.** Re-indexing from this tree is free and clears
four of the five floors above.

**2. Phase telemetry is requested from the model, not written by the harness.**

```
src/ai_team/backends/claude_agent_sdk_backend/agents/prompts.py:23
  7. Write phase transition entries to workspace/logs/phases.jsonl
```

`phases.jsonl` yields the phase and retry spans every trajectory check reasons over. Its
only code writer is `src/ai_team/harness/context_pressure.py` (added 2026-09-12, one
`phase_end` row). **Zero `phases.jsonl` files exist under `workspace/` or `output/runs/`.**
`audit.jsonl` and `costs.jsonl`, by contrast, have real code writers — phase records are the
single signal left to a prompt. Spec Phase 1 moves them into
`src/ai_team/harness/telemetry.py`, writing beside `run.json`, and deletes the prompt line.

When you run open coding: sample with
`uv run python -m evals.cli sample --strategy stratified -n 100 --seed 1`, annotate,
then `taxonomy propose --from-annotations`.

The first live LangGraph case to put through that loop (unlabeled as of
2026-09-13; not a published rate) is
[`eval-runs/2026-09-13-langgraph-smoke`](eval-runs/2026-09-13-langgraph-smoke/README.md).

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
  (task 9.4). **Campaign status:** still warn-only as of 2026-09-09 — see
  [campaign/EVAL_GATE_STATUS.md](campaign/EVAL_GATE_STATUS.md). Do not claim a hard
  gate in posts until that file says otherwise.
- **UI quality rubric** ([UI_QUALITY_RUBRIC.md](UI_QUALITY_RUBRIC.md)) is advisory.
  No gate, check, or judge reads it. Deterministic UI evidence is `run_ui_smoke`
  and the FM-006 extension of `CHK-runtime-smoke-present`.
