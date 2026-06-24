#!/usr/bin/env python3
"""
Show persisted run-quality metrics and their trend over time.

Answers the audit's gap #3 question: "is the system getting better over time?"
Reads the ``performance_metrics`` table written at the end of each run by
``ai_team.memory.self_improvement_runtime.persist_run_metrics``.

Usage:
  poetry run python scripts/show_metrics.py                 # summary across all metrics
  poetry run python scripts/show_metrics.py --metric test_pass_rate --trend
  poetry run python scripts/show_metrics.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from ai_team.config.settings import get_settings
from ai_team.memory.memory_config import LongTermStore


def _store() -> LongTermStore:
    s = get_settings()
    return LongTermStore(
        sqlite_path=s.memory.sqlite_path,
        retention_days=s.memory.retention_days,
    )


def _trend_arrow(rows: list[dict[str, Any]]) -> str:
    """Compare the mean of the latest third of runs to the earliest third."""
    vals = [float(r["value"]) for r in rows]
    if len(vals) < 2:
        return "—"
    third = max(1, len(vals) // 3)
    early = sum(vals[:third]) / third
    late = sum(vals[-third:]) / third
    delta = late - early
    if abs(delta) < 1e-9:
        return "→ flat"
    return f"↑ +{delta:.3f}" if delta > 0 else f"↓ {delta:.3f}"


def main() -> int:
    p = argparse.ArgumentParser(description="Show persisted run-quality metrics.")
    p.add_argument("--metric", type=str, default=None, help="Filter to a single metric name.")
    p.add_argument("--trend", action="store_true", help="Show time-ordered values + trend.")
    p.add_argument("--limit", type=int, default=500, help="Max rows to read (default: 500).")
    p.add_argument("--json", dest="as_json", action="store_true", help="Emit JSON.")
    args = p.parse_args()

    store = _store()

    if args.trend or args.metric:
        rows = store.get_metrics_timeseries(metric_name=args.metric, limit=args.limit)
        if args.as_json:
            print(json.dumps(rows, indent=2, default=str))
            return 0
        if not rows:
            print("No metrics recorded yet. Run a project first.", file=sys.stderr)
            return 0
        by_metric: dict[str, list[dict[str, Any]]] = {}
        for r in rows:
            by_metric.setdefault(str(r["metric_name"]), []).append(r)
        for name, series in sorted(by_metric.items()):
            print(f"\n{name}  (n={len(series)})  trend: {_trend_arrow(series)}")
            for r in series:
                ts = str(r["created_at"])[:19]
                print(f"  {ts}  {float(r['value']):>10.4f}  [{r['model']}]")
        return 0

    summary = store.get_metrics_summary()
    if args.as_json:
        print(json.dumps(summary, indent=2, default=str))
        return 0
    if not summary:
        print("No metrics recorded yet. Run a project first.", file=sys.stderr)
        return 0
    print(f"{'metric':<22}{'backend':<16}{'avg':>12}{'runs':>8}")
    print("-" * 58)
    for row in sorted(summary, key=lambda r: (str(r["metric_name"]), str(r["model"]))):
        print(
            f"{str(row['metric_name']):<22}{str(row['model']):<16}"
            f"{float(row['avg_value']):>12.4f}{int(row['count']):>8}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
