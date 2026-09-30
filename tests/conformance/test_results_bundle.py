"""The results bundle names the backend and both clocks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.conformance.conftest import BACKENDS

pytestmark = pytest.mark.parametrize("thin_run", BACKENDS, indirect=True)


def test_bundle_names_the_backend(thin_run) -> None:
    run_path = Path(str(thin_run.raw["output_dir"])) / "run.json"
    data = json.loads(run_path.read_text(encoding="utf-8"))
    assert data["backend"] == thin_run.backend_name
    assert data["started_at"]
    assert data["completed_at"]
    assert data["extra"]["model_tier"] == "local"
