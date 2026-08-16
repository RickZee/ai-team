"""Unit tests for golden set split + stratification helpers (task 5.4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from evals.cli import main
from evals.golden import (
    assign_split,
    class_counts,
    golden_stats_table,
    load_golden,
    make_label,
    make_labeling_unit_id,
    stratification_ok,
)

pytestmark = pytest.mark.eval_unit


def test_assign_split_deterministic() -> None:
    a = assign_split("unit-a")
    b = assign_split("unit-a")
    assert a == b
    assert a in {"dev", "test"}


def test_assign_split_rule_matches_design() -> None:
    """test iff sha256(id)%100 < 40."""
    import hashlib

    for uid in [f"id-{i}" for i in range(50)]:
        digest = hashlib.sha256(uid.encode()).hexdigest()
        expected = "test" if int(digest[:8], 16) % 100 < 40 else "dev"
        assert assign_split(uid) == expected


def test_make_labeling_unit_id_stable() -> None:
    assert make_labeling_unit_id("t", "span_1", "FM-001") == "t|span_1|FM-001"
    assert make_labeling_unit_id("t", None, "FM-001") == "t|run|FM-001"


def test_append_and_stats(tmp_path: Path) -> None:
    # Generate enough labels to exercise both splits and both classes.
    written = 0
    for i in range(40):
        label = "present" if i % 2 == 0 else "absent"
        unit = make_label(
            trace_id=f"trace-{i}",
            span_id="run",
            failure_mode_id="FM-099",
            human_label=label,  # type: ignore[arg-type]
            annotator="tester",
        )
        from evals.golden import append_golden

        append_golden(unit, golden_root=tmp_path)
        written += 1
    units = load_golden("FM-099", golden_root=tmp_path)
    assert len(units) == written
    cc = class_counts(units)
    assert cc["present"] + cc["absent"] == written
    ok, reason = stratification_ok(units)
    assert ok, reason
    table = golden_stats_table(golden_root=tmp_path)
    assert "FM-099" in table


def test_stratification_vacuous_when_empty() -> None:
    ok, reason = stratification_ok([])
    assert ok
    assert reason == "ok"


def test_cli_golden_label_batch(tmp_path: Path) -> None:
    batch = tmp_path / "labels.jsonl"
    batch.write_text(
        "\n".join(
            [
                '{"trace_id": "a", "span_id": "run", "human_label": "present"}',
                '{"trace_id": "b", "span_id": "run", "human_label": "absent"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    rc = main(
        [
            "golden",
            "label",
            "--fm",
            "FM-001",
            "--annotator",
            "t",
            "--batch-file",
            str(batch),
            "--golden-root",
            str(tmp_path),
        ]
    )
    assert rc == 0
    assert len(load_golden("FM-001", golden_root=tmp_path)) == 2
    assert main(["golden", "stats", "--golden-root", str(tmp_path)]) == 0
