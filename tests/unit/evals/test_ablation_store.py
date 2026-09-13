"""Ablation result store and staleness (R15)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from evals.arms.ablation_store import (
    AblationResult,
    save_result,
    staleness_of,
    status_rows,
    status_table,
)

pytestmark = pytest.mark.eval_unit


def test_never_measured_and_stale_flip(tmp_path: Path) -> None:
    rows = status_rows(root=tmp_path, current_model="new-model")
    assert all(r["status"] == "never measured" for r in rows)
    assert all(r["delta"] is None for r in rows)
    save_result(
        AblationResult(
            component="smoke_gate",
            model_id="old-model",
            model_snapshot_date="2026-01-01",
            measured_at=datetime.now(UTC),
            scenario_id="todo-api-beginner",
            n=3,
            delta={"fm_incidence": 0.1},
        ),
        root=tmp_path,
    )
    loaded_stale = status_rows(root=tmp_path, current_model="new-model")
    smoke = next(r for r in loaded_stale if r["component"] == "smoke_gate")
    assert smoke["status"] == "STALE"
    assert smoke["delta"] is None  # not presented as current evidence
    current = status_rows(root=tmp_path, current_model="old-model")
    smoke2 = next(r for r in current if r["component"] == "smoke_gate")
    assert smoke2["status"] == "current"
    assert smoke2["delta"] == {"fm_incidence": 0.1}
    table = status_table(tmp_path)
    assert "never measured" in table
    assert staleness_of(None) == "never measured"
