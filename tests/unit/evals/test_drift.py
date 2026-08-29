"""Week-over-week receipt drift ($0, no network)."""

from __future__ import annotations

import json
from pathlib import Path

from evals.drift import compare_windows, drift_from_dirs, summarize_receipts


def _receipt(path: Path, *, fm: str | None, smoke: bool, cost: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "run_id": path.parent.name,
                "failure_ids": [fm] if fm else [],
                "smoke": {"success": smoke, "ran": True},
                "cost_usd": cost,
                "cost_per_accepted_change": cost,
            }
        ),
        encoding="utf-8",
    )


def test_drift_warns_on_rate_jump(tmp_path: Path) -> None:
    prev = tmp_path / "prev"
    cur = tmp_path / "cur"
    _receipt(prev / "a" / "receipt.json", fm=None, smoke=True, cost=0.1)
    _receipt(prev / "b" / "receipt.json", fm=None, smoke=True, cost=0.1)
    _receipt(cur / "c" / "receipt.json", fm="FM-001", smoke=False, cost=0.5)
    _receipt(cur / "d" / "receipt.json", fm="FM-001", smoke=False, cost=0.5)
    report = drift_from_dirs(cur, prev)
    assert report.current.n == 2
    assert report.previous.n == 2
    assert any("FM-001" in w for w in report.warnings)


def test_summarize_empty() -> None:
    win = summarize_receipts([])
    assert win.n == 0
    report = compare_windows(win, win)
    assert report.warnings == []
