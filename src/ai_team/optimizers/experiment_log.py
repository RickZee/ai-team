"""Append-only experiment log written to workspace/logs/experiments.jsonl."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class ExperimentRecord:
    iteration: int
    metric_value: float | None
    baseline: float | None
    kept: bool
    cost_usd: float
    snapshot_tag: str
    error: str | None = None
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    @property
    def improvement(self) -> float | None:
        if self.metric_value is not None and self.baseline:
            return round(
                (self.metric_value - self.baseline) / abs(self.baseline) * 100, 3
            )
        return None


def append_experiment(workspace: Path, record: ExperimentRecord) -> None:
    log_path = workspace / "logs" / "experiments.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as fh:
        fh.write(json.dumps(asdict(record)) + "\n")


def load_experiments(workspace: Path) -> list[ExperimentRecord]:
    log_path = workspace / "logs" / "experiments.jsonl"
    if not log_path.exists():
        return []
    records = []
    for line in log_path.read_text().splitlines():
        line = line.strip()
        if line:
            records.append(ExperimentRecord(**json.loads(line)))
    return records


def summarise_experiments(records: list[ExperimentRecord]) -> dict:
    if not records:
        return {}
    kept = [r for r in records if r.kept]
    metrics = [r.metric_value for r in records if r.metric_value is not None]
    return {
        "total": len(records),
        "kept": len(kept),
        "reverted": len(records) - len(kept),
        "best_metric": max(metrics) if metrics else None,
        "worst_metric": min(metrics) if metrics else None,
        "total_cost_usd": round(sum(r.cost_usd for r in records), 6),
    }
