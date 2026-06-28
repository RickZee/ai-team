"""Compare summary helpers shared by web-facing Python clients (TUI)."""

from __future__ import annotations

import re
from typing import Any, Callable, Literal


def parse_elapsed_seconds(elapsed: str) -> int:
    """Parse monitor elapsed strings like ``2m 30s`` into seconds."""
    minutes = re.search(r"(\d+)m", elapsed or "")
    seconds = re.search(r"(\d+)s", elapsed or "")
    return (int(minutes.group(1)) * 60 if minutes else 0) + (
        int(seconds.group(1)) if seconds else 0
    )


def best_column_key(
    rows: list[dict[str, Any]],
    extract: Callable[[dict[str, Any]], int | float],
    prefer: Literal["min", "max"],
) -> str | None:
    """Return the row key with the best numeric metric."""
    if not rows:
        return None
    best = rows[0]
    best_val = extract(best)
    for row in rows[1:]:
        val = extract(row)
        if prefer == "min" and val < best_val:
            best, best_val = row, val
        elif prefer == "max" and val > best_val:
            best, best_val = row, val
    return str(best.get("key"))


def build_compare_verdict(
    rows: list[dict[str, Any]],
    metrics: list[tuple[str, Literal["min", "max"], Callable[[dict[str, Any]], float]]],
) -> str:
    """Build a one-line verdict string from summary rows."""
    active = [r for r in rows if not r.get("failed")]
    parts: list[str] = []
    for label, prefer, extract in metrics:
        best_key = best_column_key(active, extract, prefer)
        if not best_key:
            continue
        winner = next((r for r in active if r.get("key") == best_key), None)
        if winner:
            direction = "lowest" if prefer == "min" else "highest"
            parts.append(f"{winner.get('label', best_key)}: {direction} {label}")
    return "; ".join(parts)


def monitor_metric_rows(monitor: dict[str, Any]) -> dict[str, Any]:
    """Extract comparable metrics from a serialized monitor snapshot."""
    metrics = monitor.get("metrics") or {}
    return {
        "elapsed": monitor.get("elapsed", "—"),
        "elapsed_sec": parse_elapsed_seconds(str(monitor.get("elapsed", ""))),
        "phase": monitor.get("phase", "—"),
        "cost_usd": monitor.get("cost_usd"),
        "tokens": monitor.get("token_estimate") or 0,
        "tasks_completed": metrics.get("tasks_completed", 0),
        "tasks_failed": metrics.get("tasks_failed", 0),
        "files": metrics.get("files_generated", 0),
        "guardrails_passed": metrics.get("guardrails_passed", 0),
        "guardrails_failed": metrics.get("guardrails_failed", 0),
        "tests_passed": metrics.get("tests_passed", 0),
        "tests_failed": metrics.get("tests_failed", 0),
        "retries": metrics.get("retries", 0),
    }
