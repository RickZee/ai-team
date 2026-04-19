"""Metric configuration and extraction for the AutoOptimizer loop."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel


class MetricConfig(BaseModel):
    """Defines what to measure and how to measure it."""

    name: str
    evaluation_command: str
    direction: Literal["maximize", "minimize"] = "maximize"
    # If set, parse stdout as JSON and extract this dot-path key (e.g. "results.rps_mean")
    json_key: str | None = None
    success_threshold: float | None = None
    # Seconds before the eval command is killed
    timeout: int = 300

    def better(self, new: float, current: float) -> bool:
        """Return True if *new* is an improvement over *current*."""
        if self.direction == "maximize":
            return new > current
        return new < current

    def meets_threshold(self, value: float) -> bool:
        if self.success_threshold is None:
            return True
        if self.direction == "maximize":
            return value >= self.success_threshold
        return value <= self.success_threshold


def extract_metric(cfg: MetricConfig, workspace: Path) -> float | None:
    """
    Run cfg.evaluation_command inside workspace and parse the metric value.

    The command is a trusted, user-supplied eval script (not agent-generated input),
    so shell=True is acceptable here. Agent-generated edits are in src/ only.
    """
    try:
        result = subprocess.run(  # noqa: S602
            cfg.evaluation_command,
            shell=True,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=cfg.timeout,
        )
        output = result.stdout.strip()
        if not output:
            return None
        if cfg.json_key:
            data = json.loads(output)
            return float(_nested_get(data, cfg.json_key))
        # Fallback: last non-empty line is the metric value
        lines = [ln for ln in output.splitlines() if ln.strip()]
        return float(lines[-1]) if lines else None
    except (subprocess.TimeoutExpired, ValueError, KeyError, json.JSONDecodeError):
        return None


def load_metric_config(path: Path) -> MetricConfig:
    data = yaml.safe_load(path.read_text())
    return MetricConfig.model_validate(data)


def _nested_get(d: dict, key: str):
    """Dot-notation access: 'results.p99_ms' → d['results']['p99_ms']."""
    for part in key.split("."):
        d = d[part]
    return d
