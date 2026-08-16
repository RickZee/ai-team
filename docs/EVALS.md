# Evals

How we measure whether ai-team actually works — not just that unit tests pass.

The v1 harness separates **execution** from **scoring** at a Trace boundary: backends
write workspaces; the harness builds immutable traces; deterministic checks (and
optional cached judges) score offline. Per-PR Tier A costs **$0.00**.

Aspirational / not-yet-implemented material (role-eval backlog, older sketches) lives in
[`EVALS_ROADMAP.md`](./EVALS_ROADMAP.md). Methodology and limitations:
[`EVAL_METHODOLOGY.md`](./EVAL_METHODOLOGY.md). Package quickstart: [`../evals/README.md`](../evals/README.md).

---

## Tiers

| Tier | Trigger | Spend | What runs |
| --- | --- | --- | --- |
| **A** | Every PR (`eval-tier-a` CI job, `--warn-only` during soak) | $0.00 | Replay `evals/fixtures/traces/` → checks + guardrail corpus + cached judges + report + gate |
| **B** | Nightly / on demand (`eval-nightly.yml`) | ≤ $2.00 | Live smoke scenarios, k≈3, budget ledger |
| **C** | Manual pre-release | ≤ $5.00 hard ceiling | Full matrix; human-triggered |

```bash
# Tier A (offline, deterministic)
uv run python -m evals.cli run --tier A --warn-only

# Live runner (existing; emits traces)
AI_TEAM_USE_REAL_LLM=1 uv run python -m evals.run_evals --compare --no-judge --tier B --k 1 --budget-usd 2.00 --yes
```

---

## What is implemented

| Layer | Location | Notes |
| --- | --- | --- |
| Trace capture | `evals/trace/`, `evals/store.py` | From `logs/*.jsonl` + workspace; backfill via CLI |
| Sampling | `evals/sampling.py` | random / stratified / extremes / failed-only / unlabeled |
| Taxonomy | `evals/taxonomy/failure_modes.yaml` | FM-001…FM-010 ↔ [failure-taxonomy essay](./posts/failure-taxonomy.md) |
| Deterministic checks | `evals/checks/` | 13 checks bound to FMs; Tier A |
| Annotation TUI | `evals/annotate.py` | Open coding; **no LLM suggestions** (R3.7) |
| Golden / alignment | `evals/golden.py`, `evals/alignment.py` | Split discipline; judges advisory until human labels + live align |
| Guardrail eval | `evals/guardrail_eval.py` | Reuses `ai_team.guardrails.corpus_metrics` |
| Binary judges | `evals/judges/` | Versioned prompt files + verdict cache; continuous `LLMJudge` deprecated for gating |
| Reliability | `evals/reliability.py` | pass@k, pass^k, Wilson CI |
| Cost / budget | `evals/cost.py`, `evals/pricing.yaml` | `BudgetLedger` per suite run (not a singleton) |
| Aggregate / report | `evals/aggregate.py`, `evals/report.py` | json / md / html / summary.txt |
| Gate | `evals/gate.py`, `evals/baselines/` | Exit 0 / 1 / 2; baseline accept refuses dirty git |
| Legacy scorecard | `evals/metrics.py::format_scorecard` | Still the terminal one-pager |
| Backend pytest clients | `evals/backends/test_*_eval.py` | Still runnable; emit into workspaces consumed as traces |

---

## Scenarios

Contracts live in `evals/scenarios/*.json` (smoke, todo-api, role-oriented demos, etc.).
Tier A scores committed fixture traces, not live scenario execution.

---

## Failure modes (machine + essay)

| ID | Slug | Detection |
| --- | --- | --- |
| FM-001 | tool_call_omission | CHK-tool-call-emitted |
| FM-002 | self_triggering_retry_loop | CHK-phase-repeat-bounded, CHK-listener-self-trigger |
| FM-003 | runtime_coupling_starvation | CHK-interrupt-latency |
| FM-004 | run_id_collision | CHK-workspace-isolation |
| FM-005 | guardrail_false_positive | CHK-guardrail-fp-budget |
| FM-006 | runtime_verification_gap | CHK-runtime-smoke-present |
| FM-007 | unbounded_spend | CHK-spend-ceiling |
| FM-008 | metric_source_drift | CHK-metric-source-agreement |
| FM-009 | provider_dialect_mismatch | CHK-provider-error-rate |
| FM-010 | gate_environment_mismatch | CHK-gate-env-fidelity |

Essay: [Ten Ways Multi-Agent Systems Actually Fail](./posts/failure-taxonomy.md).
Machine taxonomy: [`evals/taxonomy/failure_modes.yaml`](../evals/taxonomy/failure_modes.yaml).
Coverage table: [`evals/taxonomy/COVERAGE.md`](../evals/taxonomy/COVERAGE.md).

---

## CI

- `eval-tier-a` in `.github/workflows/ci.yml` — no secrets, `--warn-only` until soak complete
- `.github/workflows/eval-nightly.yml` — Tier B when API secrets present; skips neutrally otherwise

Hard gate flip (remove `--warn-only`) is deferred until nightlies are green for a week
(task 9.4).
