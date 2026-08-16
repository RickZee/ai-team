"""Unit tests for evals.sampling (task 2.2 / R2.3–R2.6)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from evals.cli import main
from evals.sampling import (
    SampleManifest,
    corpus_state_hash,
    sample,
    sample_extremes,
    sample_failed_only,
    sample_random,
    sample_stratified,
    sample_unlabeled,
    write_manifest,
)
from evals.store import TraceIndexRow

pytestmark = pytest.mark.eval_unit


def _row(
    trace_id: str,
    *,
    backend: str = "crewai",
    scenario_id: str = "s1",
    status: str = "complete",
    duration_s: float | None = 1.0,
    cost_usd: float | None = 0.01,
    retry_count: int = 0,
    label_count: int = 0,
) -> TraceIndexRow:
    return TraceIndexRow(
        trace_id=trace_id,
        scenario_id=scenario_id,
        backend=backend,
        status=status,
        git_sha="abc",
        started_at="2026-08-01T00:00:00+00:00",
        duration_s=duration_s,
        cost_usd=cost_usd,
        cost_source="unknown",
        span_count=1,
        error_count=0,
        retry_count=retry_count,
        file_count=0,
        label_count=label_count,
        tier="C",
        schema_version=1,
    )


def test_corpus_state_hash_order_independent() -> None:
    a = [_row("t2"), _row("t1")]
    b = [_row("t1"), _row("t2")]
    assert corpus_state_hash(a) == corpus_state_hash(b)


def test_random_same_seed_identical() -> None:
    rows = [_row(f"t{i}") for i in range(20)]
    assert sample_random(rows, 5, 42) == sample_random(rows, 5, 42)
    assert sample_random(rows, 5, 42) != sample_random(rows, 5, 43)


def test_failed_only_filters_status() -> None:
    rows = [
        _row("ok", status="complete"),
        _row("bad1", status="failed"),
        _row("bad2", status="killed"),
        _row("bad3", status="budget_abort"),
        _row("wait", status="awaiting_human"),
    ]
    ids = sample_failed_only(rows, 10, 0)
    assert set(ids) == {"bad1", "bad2", "bad3"}


def test_unlabeled_filters_label_count() -> None:
    rows = [
        _row("u1", label_count=0),
        _row("u2", label_count=0),
        _row("l1", label_count=2),
    ]
    ids = sample_unlabeled(rows, 10, 1)
    assert set(ids) == {"u1", "u2"}


def test_extremes_takes_ceil_n_over_3_per_metric() -> None:
    rows = [
        _row("d1", duration_s=100.0, cost_usd=0.0, retry_count=0),
        _row("d2", duration_s=90.0, cost_usd=0.0, retry_count=0),
        _row("c1", duration_s=0.0, cost_usd=50.0, retry_count=0),
        _row("c2", duration_s=0.0, cost_usd=40.0, retry_count=0),
        _row("r1", duration_s=0.0, cost_usd=0.0, retry_count=10),
        _row("r2", duration_s=0.0, cost_usd=0.0, retry_count=9),
        _row("mid", duration_s=1.0, cost_usd=1.0, retry_count=1),
    ]
    n = 6
    per = math.ceil(n / 3)
    assert per == 2
    ids = sample_extremes(rows, n, seed=0)
    assert "d1" in ids and "d2" in ids
    assert "c1" in ids and "c2" in ids
    assert "r1" in ids and "r2" in ids
    assert "mid" not in ids
    # Deduplicated list preserves first-seen order across metrics.
    assert len(ids) == len(set(ids))


def test_extremes_deduplicates_overlap() -> None:
    # One row wins all three metrics; second place differs per metric.
    rows = [
        _row("winner", duration_s=99.0, cost_usd=99.0, retry_count=99),
        _row("d2", duration_s=50.0, cost_usd=1.0, retry_count=1),
        _row("c2", duration_s=1.0, cost_usd=50.0, retry_count=1),
        _row("r2", duration_s=1.0, cost_usd=1.0, retry_count=50),
    ]
    ids = sample_extremes(rows, n=6, seed=0)
    assert ids.count("winner") == 1
    assert set(ids) == {"winner", "d2", "c2", "r2"}


def test_stratified_shortfall_recorded_and_filled() -> None:
    # Two strata: tiny (1) and large (10). Request n=6 → equal quota 3 each.
    rows = [_row("tiny", backend="a", scenario_id="x", status="failed")]
    rows += [_row(f"big{i}", backend="b", scenario_id="y", status="complete") for i in range(10)]
    selection, imbalances = sample_stratified(rows, n=6, seed=7)
    assert len(selection) == 6
    assert len(imbalances) == 1
    imb = imbalances[0]
    assert imb.stratum.backend == "a"
    assert imb.quota == 3
    assert imb.available == 1
    assert imb.shortfall == 2
    assert imb.filled == 2
    assert imb.donor.backend == "b"
    assert "tiny" in selection
    assert sum(1 for tid in selection if tid.startswith("big")) == 5


def test_sample_manifest_byte_identical(tmp_path: Path) -> None:
    rows = [_row(f"t{i}", status="complete" if i % 2 == 0 else "failed") for i in range(12)]
    m1 = sample(rows, "stratified", n=6, seed=42)
    m2 = sample(rows, "stratified", n=6, seed=42)
    p1 = write_manifest(m1, samples_root=tmp_path / "s1")
    p2 = write_manifest(m2, samples_root=tmp_path / "s2")
    assert p1.read_bytes() == p2.read_bytes()
    assert m1.model_dump() == m2.model_dump()


def test_sample_manifest_includes_imbalances_field() -> None:
    rows = [_row("only", backend="solo", scenario_id="s", status="failed")]
    rows += [_row(f"m{i}", backend="many", scenario_id="s", status="complete") for i in range(8)]
    manifest = sample(rows, "stratified", n=4, seed=1)
    assert isinstance(manifest, SampleManifest)
    assert manifest.imbalances
    dumped = manifest.model_dump(mode="json")
    assert "imbalances" in dumped
    assert dumped["imbalances"][0]["shortfall"] >= 1


def test_write_manifest_path(tmp_path: Path) -> None:
    rows = [_row("a"), _row("b"), _row("c")]
    manifest = sample(rows, "random", n=2, seed=9)
    path = write_manifest(manifest, samples_root=tmp_path)
    assert path == tmp_path / f"{manifest.sample_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["strategy"] == "random"
    assert data["seed"] == 9
    assert data["corpus_state_hash"] == corpus_state_hash(rows)
    assert set(data["selection"]).issubset({"a", "b", "c"})


def test_cli_sample_writes_manifest(tmp_path: Path) -> None:
    traces = tmp_path / "traces"
    samples = tmp_path / "samples"
    traces.mkdir()
    # Minimal index via TraceStore would need full Trace objects; seed rows through
    # sampling CLI after writing a tiny SQLite is heavy — exercise argparse + empty index.
    rc = main(
        [
            "sample",
            "--strategy",
            "random",
            "-n",
            "5",
            "--seed",
            "42",
            "--traces-root",
            str(traces),
            "--samples-root",
            str(samples),
        ]
    )
    assert rc == 0
    written = list(samples.glob("*.json"))
    assert len(written) == 1
    payload = json.loads(written[0].read_text(encoding="utf-8"))
    assert payload["strategy"] == "random"
    assert payload["seed"] == 42
    assert payload["selection"] == []


def test_unknown_strategy_raises() -> None:
    with pytest.raises(ValueError, match="unknown"):
        sample([_row("x")], "nope", n=1, seed=0)  # type: ignore[arg-type]
