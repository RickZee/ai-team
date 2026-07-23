# Performance Report

**This is a generated artifact and is not kept in version control with real data.**

The committed copy used to hold numbers from a *mock-LLM* run — all timings near
zero — which read like performance data but measured nothing. That was misleading, so
the report is now generated on demand and git-ignored.

To produce a real one:

```bash
AI_TEAM_BENCHMARK_FULL=1 uv run pytest tests/performance/ -v -s --tb=short
```

This writes `docs/performance_report.md` (overwriting this placeholder locally) and
`docs/benchmark_results.json`, each stamped with the UTC time, the commit SHA, and
whether it was a real-LLM run. Neither is committed — regenerate against the commit
you care about.

For the backend comparison numbers (green-rate, wall-clock, spend, with confidence
intervals), see [COMPARISON_RESULTS.md](COMPARISON_RESULTS.md) and
`scripts/run_smoke_batch.py`.
