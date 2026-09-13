"""Persist ablation results and report staleness (R15). Staleness never fails the gate."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from evals.arms.base import ABLATABLE_COMPONENTS

DEFAULT_RESULTS = Path("evals/results/ablations")
Staleness = Literal["current", "STALE", "never measured"]


class AblationResult(BaseModel):
    """One measured ablation, stamped with the model it was taken on."""

    component: str
    model_id: str
    model_snapshot_date: str
    measured_at: datetime
    scenario_id: str
    n: int
    delta: dict[str, Any] = Field(default_factory=dict)
    ci: dict[str, Any] = Field(default_factory=dict)


def result_path(component: str, root: Path | None = None) -> Path:
    """Return ``evals/results/ablations/<component>.json``."""
    safe = component.replace(".", "_")
    return (root or DEFAULT_RESULTS) / f"{safe}.json"


def save_result(result: AblationResult, root: Path | None = None) -> Path:
    """Persist one ablation result."""
    path = result_path(result.component, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result.model_dump(mode="json"), indent=2, default=str), encoding="utf-8"
    )
    return path


def load_result(component: str, root: Path | None = None) -> AblationResult | None:
    """Load a result or return None."""
    path = result_path(component, root)
    if not path.is_file():
        return None
    try:
        return AblationResult.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def default_model_id() -> str:
    """Configured default model for staleness comparison."""
    import os

    return os.environ.get("AI_TEAM_DEFAULT_MODEL") or os.environ.get(
        "AI_TEAM_MODEL_FULLSTACK", "configured-default"
    )


def staleness_of(result: AblationResult | None, *, current_model: str | None = None) -> Staleness:
    """``never measured`` / ``STALE`` / ``current``. Never fails a gate (R15.5)."""
    if result is None:
        return "never measured"
    model = current_model or default_model_id()
    if result.model_id != model:
        return "STALE"
    return "current"


def status_rows(
    *, root: Path | None = None, current_model: str | None = None
) -> list[dict[str, Any]]:
    """One row per ablatable component."""
    rows: list[dict[str, Any]] = []
    for component in sorted(ABLATABLE_COMPONENTS):
        result = load_result(component, root)
        state = staleness_of(result, current_model=current_model)
        rows.append(
            {
                "component": component,
                "status": state,
                "model_id": result.model_id if result else None,
                "measured_at": result.measured_at.isoformat() if result else None,
                "n": result.n if result else 0,
                "delta": result.delta if result and state == "current" else None,
            }
        )
    return rows


def status_table(root: Path | None = None) -> str:
    """Human-readable ablation status listing."""
    rows = status_rows(root=root)
    lines = ["component\tstatus\tmodel_id\tn", "---\t---\t---\t---"]
    for row in rows:
        lines.append(f"{row['component']}\t{row['status']}\t{row['model_id'] or '—'}\t{row['n']}")
    return "\n".join(lines) + "\n"
