"""Integration: Tier A determinism + network isolation (R16.2 / R11.5)."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from evals.report import report_json_without_generated_at
from evals.tier_a import run_tier_a

pytestmark = [pytest.mark.integration, pytest.mark.eval_tier_a]

_FIXTURES = Path("evals/fixtures/traces")


@pytest.mark.skipif(
    not _FIXTURES.is_dir() or not any(_FIXTURES.glob("*.json")),
    reason="precondition: no Tier A fixture traces",
)
def test_tier_a_two_runs_deterministic(tmp_path: Path) -> None:
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    report_a, code_a, paths_a = run_tier_a(out_dir=out_a, warn_only=True)
    report_b, code_b, paths_b = run_tier_a(out_dir=out_b, warn_only=True)
    assert report_a.cost.total_usd == 0.0
    assert report_b.cost.total_usd == 0.0
    assert code_a == 0
    assert code_b == 0
    assert report_json_without_generated_at(paths_a["report.json"]) == (
        report_json_without_generated_at(paths_b["report.json"])
    )


@pytest.mark.skipif(
    not _FIXTURES.is_dir() or not any(_FIXTURES.glob("*.json")),
    reason="precondition: no Tier A fixture traces",
)
def test_tier_a_under_socket_monkeypatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Full Tier A run while socket.connect raises (R16.2 network isolation)."""

    def _blocked(self: socket.socket, address: object) -> None:
        raise OSError(f"Tier A integration network blocked: {address!r}")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", lambda *_a, **_k: 1)

    report, code, _paths = run_tier_a(out_dir=tmp_path / "net", warn_only=True)
    assert report.cost.total_usd == 0.0
    assert code == 0
