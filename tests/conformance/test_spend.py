"""Spend is recorded and current_spend names a source."""

from __future__ import annotations

import pytest
from ai_team.core.spend_guard import current_spend

from tests.conformance.conftest import BACKENDS

pytestmark = pytest.mark.parametrize("thin_run", BACKENDS, indirect=True)


def test_spend_has_a_source(thin_run) -> None:
    snap = current_spend(run_id=str(thin_run.raw["run_id"]))
    assert snap.get("source")
    assert snap.get("calls", 0) >= 1
