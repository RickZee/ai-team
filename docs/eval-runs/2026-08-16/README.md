# Eval run note — 2026-08-16

## Tier A (executed)

```bash
uv run python -m evals.cli run --tier A --warn-only --out evals/results/tier-a-local
```

- Spend: **$0.00**
- Corpus: committed fixtures under `evals/fixtures/traces/` (~336KB)
- Gate: `--warn-only` (task 9.4 soak not complete)

## Tier C (deferred — spends money)

Task 10.2 requires:

```bash
uv run python -m evals.cli run --tier C --k 5 --yes
```

with budget ≤ $5.00 (`AI_TEAM_EVAL_BUDGET_USD`). This was **not** run in the harness
scaffolding pass (explicit human-triggered spend). After a live run, commit
`report.json` / `report.md` here and record actual vs projected spend from design §5.1.

## Judge align (deferred — ≤ $1.00)

Advisory alignment fixtures live under `evals/golden/alignment/` with
`eligible_to_gate: false` until a human golden set exists and `judge validate` is run once.
