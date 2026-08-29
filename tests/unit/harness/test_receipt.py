"""Change receipts and cost_per_accepted_change."""

from __future__ import annotations

from pathlib import Path

from ai_team.harness.receipt import (
    ReceiptWriter,
    compute_cost_per_accepted_change,
    is_accepted_change,
    load_receipt,
)


def test_cost_per_accepted_zero_accepts() -> None:
    assert compute_cost_per_accepted_change(total_usd=2.0, accepted_changes=0) == 2.0


def test_cost_per_accepted_one() -> None:
    assert compute_cost_per_accepted_change(total_usd=2.0, accepted_changes=1) == 2.0


def test_rejected_smoke_not_accepted() -> None:
    assert (
        is_accepted_change(
            smoke={"ran": True, "success": False},
            required_ok=True,
        )
        is False
    )
    assert (
        is_accepted_change(
            smoke={"ran": True, "success": True},
            required_ok=True,
        )
        is True
    )
    assert (
        is_accepted_change(
            smoke={"ran": False, "skip_reason": "no app"},
            required_ok=True,
        )
        is True
    )


def test_writer_emits_json_and_md_without_smoke(tmp_path: Path) -> None:
    out = tmp_path / "output" / "runs" / "r1"
    rec = ReceiptWriter().write_from_run(
        output_dir=out,
        workspace=tmp_path / "ws",
        run_id="r1",
        backend="crewai",
        cost_usd=0.5,
        smoke={},
        required_ok=True,
    )
    assert rec.accepted is False
    assert (out / "receipt.json").is_file()
    assert (out / "receipt.md").is_file()
    loaded = load_receipt(out)
    assert loaded is not None
    assert loaded.run_id == "r1"
    assert loaded.cost_usd == 0.5
