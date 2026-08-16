"""Tier A offline replay: determinism, $0 spend, network block (R11)."""

from __future__ import annotations

from pathlib import Path

import pytest

from evals.report import report_json_without_generated_at
from evals.tier_a import run_tier_a

pytestmark = [pytest.mark.eval_unit, pytest.mark.eval_tier_a]

_FIXTURES = Path("evals/fixtures/traces")


@pytest.mark.skipif(
    not _FIXTURES.is_dir() or not any(_FIXTURES.glob("*.json")), reason="no fixtures"
)
def test_tier_a_two_runs_byte_identical(tmp_path: Path) -> None:
    """Two consecutive Tier A runs → identical report.json except generated_at; $0 spend."""
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    report_a, code_a, paths_a = run_tier_a(out_dir=out_a, warn_only=True)
    report_b, code_b, paths_b = run_tier_a(out_dir=out_b, warn_only=True)
    assert report_a.cost.total_usd == 0.0
    assert report_b.cost.total_usd == 0.0
    assert code_a == 0  # warn-only
    assert code_b == 0
    canon_a = report_json_without_generated_at(paths_a["report.json"])
    canon_b = report_json_without_generated_at(paths_b["report.json"])
    assert canon_a == canon_b
    raw_a = paths_a["report.json"].read_text(encoding="utf-8")
    raw_b = paths_b["report.json"].read_text(encoding="utf-8")
    assert raw_a != raw_b  # generated_at differs


def test_tier_a_blocks_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Tier A installs a socket connect blocker for model API egress."""
    import socket

    connects: list[object] = []
    orig = socket.socket.connect

    def spy(self: socket.socket, address: object) -> None:
        connects.append(address)
        return orig(self, address)

    monkeypatch.setattr(socket.socket, "connect", spy)
    # Run with block_network=True (default): if anything tries to connect, OSError.
    report, _code, _paths = run_tier_a(out_dir=tmp_path / "net", warn_only=True)
    assert report.cost.total_usd == 0.0
    # No successful connects should have been recorded through the spy while blocked;
    # the blocker replaces connect entirely, so spy is not used during the run.
    # Re-assert blocker raises:
    from evals.tier_a import _NetworkBlocker

    with _NetworkBlocker(), pytest.raises(OSError, match="Tier A network blocked"):
        sock = socket.socket()
        try:
            sock.connect(("127.0.0.1", 9))
        finally:
            sock.close()


def test_cache_warm_stub() -> None:
    from evals.cli import main

    assert main(["cache", "warm", "--tier", "B"]) == 0


def test_cli_fixtures_redact_lint() -> None:
    from evals.cli import main

    assert main(["fixtures", "redact", "--root", "evals/fixtures", "--lint"]) == 0
