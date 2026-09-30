"""Budget and wall-clock limits close the run record."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.conformance.conftest import BACKENDS, run_thin_slice


@pytest.mark.parametrize("backend_name", BACKENDS)
def test_budget_exceeded_closes_the_run(backend_name: str, tmp_path: Path) -> None:
    result = run_thin_slice(
        backend_name,
        tmp_path,
        run_budget_usd=0.25,
        force_spend_usd=1.0,
        skip_pytest=True,
    )
    data = json.loads(
        (Path(str(result.raw["output_dir"])) / "run.json").read_text(encoding="utf-8")
    )
    assert data["extra"]["final_status"] == "budget_exceeded"
    assert data["completed_at"]
    assert result.success is False


@pytest.mark.parametrize("backend_name", BACKENDS)
def test_timeout_closes_the_run(backend_name: str, tmp_path: Path) -> None:
    result = run_thin_slice(backend_name, tmp_path, wall_clock_s=0, skip_pytest=True)
    data = json.loads(
        (Path(str(result.raw["output_dir"])) / "run.json").read_text(encoding="utf-8")
    )
    assert data["extra"]["final_status"] == "timeout"
    assert data["completed_at"]
    assert result.success is False
