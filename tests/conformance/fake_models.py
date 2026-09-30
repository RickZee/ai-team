"""Load and replay the thin-slice script. The script is data; backends do not edit it."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

SCRIPT_PATH = Path(__file__).resolve().parent / "scripts" / "thin_slice.yaml"


def load_thin_slice(path: Path | None = None) -> dict[str, Any]:
    """Load the thin-slice YAML."""
    target = path or SCRIPT_PATH
    with target.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"thin slice script must be a mapping: {target}")
    return data


def replay(script: dict[str, Any], on_step: Callable[[dict[str, Any]], None]) -> None:
    """Hand each step to ``on_step``. The player does not know about a framework."""
    steps = script.get("steps") or []
    if not isinstance(steps, list):
        raise ValueError("thin slice steps must be a list")
    for step in steps:
        if isinstance(step, dict):
            on_step(step)
