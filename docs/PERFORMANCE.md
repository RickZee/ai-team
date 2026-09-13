# Performance and operating envelope

This document states how fast a run is, how much it costs, and what breaks
first. It is **not** a claim that the system is horizontally scalable.

**Last updated:** 2026-09-13. Live multi-backend numbers are human-triggered
(task 9.1, $25 cap) and are not in this file until that run is recorded.
Mock-LLM timings are not published here — the deleted `performance_report.md`
showed why: they read like performance data and measured nothing.

## Regeneration

```bash
# Offline envelope checks (retention, no model):
uv run pytest tests/unit/core/results/test_cleanup.py -k prune

# Live benchmark (human-triggered, spend guard, $25 cap) — not run from agents:
# AI_TEAM_BENCHMARK_FULL=1 uv run pytest tests/performance -m performance
```

## Operating envelope

| Limit | Value | Source | What would lift it (not built) |
| --- | --- | --- | --- |
| Process model | Single process | `ai-team-web` | Worker pool |
| Run registry | In-memory `RunState.runs`, wiped on restart (SQLite `RunStore` is best-effort) | `ui/web/server.py` | Persistent run store |
| Concurrent runs | Bounded by the process and provider rate limits; Compare starts three backends | server Compare path | Queue |
| Disk | `workspace/` and `output/runs/` grow without bound until pruned | this doc | Object storage |
| Spend | `AI_TEAM_RUN_BUDGET_USD` (default $5) | spend guard | — |
| Wall clock | `CREWAI_HARD_TIMEOUT_SECONDS` (default 900) plus per-phase timeouts | settings | — |

Retention: `uv run ai-team prune --older-than-days 14`. Idempotent. Demo/quickstart
paths are unaffected because they create new run ids.

## Honest gaps

- No published live benchmark in this file yet (task 9.1 is human-triggered spend).
- Eight mock benchmark tests under `tests/performance/` were removed from the
  "published numbers" story; they remain as optional live probes behind
  `AI_TEAM_BENCHMARK_FULL=1` and do not write committed artifacts.
