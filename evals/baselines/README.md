# Accepted eval baselines.

Class: **accepted**. `tier_a.json` is blessed with date, git sha, and a `reason`.
Regenerate with:

```bash
uv run python -m evals.cli run --tier A --out evals/results/local-tier-a
uv run python -m evals.cli baseline accept --tier A --reason "…"
```

The working tree must be clean for `baseline accept`.
