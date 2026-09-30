"""Harness acceptance is recorded on the thin slice for every backend."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.conformance.conftest import BACKENDS

pytestmark = pytest.mark.parametrize("thin_run", BACKENDS, indirect=True)


def test_accepts_are_recorded(thin_run) -> None:
    path = Path(str(thin_run.raw["workspace_dir"])) / "logs" / "harness_acceptance.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert any(row["status"] == "passing" for row in data["results"])
