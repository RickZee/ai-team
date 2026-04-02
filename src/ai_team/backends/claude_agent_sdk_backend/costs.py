"""Phase-oriented budget defaults and cost log helpers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PHASE_BUDGETS_USD: dict[str, float] = {
    "planning": 3.0,
    "development": 10.0,
    "testing": 3.0,
    "deployment": 2.0,
}


def default_total_budget_usd() -> float:
    """Sum of default per-phase budgets (orchestrator ceiling)."""
    return float(sum(PHASE_BUDGETS_USD.values()))


def append_cost_log(
    workspace: Path,
    *,
    phase: str,
    cost_usd: float | None,
    usage: dict[str, Any] | None,
) -> None:
    """Append one JSON line to ``workspace/logs/costs.jsonl``."""
    log_dir = workspace / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "costs.jsonl"
    row = {
        "phase": phase,
        "cost_usd": cost_usd,
        "usage": usage or {},
        "timestamp": datetime.now(UTC).isoformat(),
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


def read_cost_log(workspace: Path) -> list[dict[str, Any]]:
    """Load ``workspace/logs/costs.jsonl`` as a list of dict rows."""
    path = workspace / "logs" / "costs.jsonl"
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                rows.append(obj)
        except json.JSONDecodeError:
            continue
    return rows


def total_logged_cost_usd(workspace: Path) -> float:
    """Sum numeric ``cost_usd`` fields from the cost log."""
    total = 0.0
    for row in read_cost_log(workspace):
        v = row.get("cost_usd")
        if isinstance(v, bool) or v is None:
            continue
        try:
            total += float(v)
        except (TypeError, ValueError):
            continue
    return total


def remaining_budget_usd(workspace: Path, ceiling_usd: float) -> float:
    """``ceiling_usd`` minus :func:`total_logged_cost_usd` (floored at 0)."""
    return max(0.0, float(ceiling_usd) - total_logged_cost_usd(workspace))


def cost_comparison_markdown(
    workspace: Path,
    *,
    crewai_estimate_usd: float | None = None,
    ceiling_usd: float | None = None,
) -> str:
    """Short markdown summary for logs or UI (Claude actual vs optional CrewAI estimate)."""
    actual = total_logged_cost_usd(workspace)
    lines = [
        "## Cost summary",
        "",
        f"- **Logged spend (Claude runs):** ${actual:.4f}",
    ]
    if ceiling_usd is not None:
        lines.append(f"- **Ceiling:** ${float(ceiling_usd):.4f}")
        lines.append(f"- **Remaining (by log):** ${remaining_budget_usd(workspace, float(ceiling_usd)):.4f}")
    if crewai_estimate_usd is not None:
        lines.append(f"- **CrewAI estimate (reference):** ${float(crewai_estimate_usd):.4f}")
        lines.append(
            f"- **Delta (actual − estimate):** ${actual - float(crewai_estimate_usd):.4f}"
        )
    lines.append("")
    return "\n".join(lines)
