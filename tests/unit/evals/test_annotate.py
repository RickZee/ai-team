"""Unit tests for open-coding annotation TUI (task 5.1)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from evals.annotate import (
    AnnotationRecord,
    annotated_trace_ids,
    annotations_path,
    load_annotations,
    render_trace_card,
    run_annotate_session,
    run_batch_annotate,
    saturation_streak,
)
from evals.cli import main
from evals.sampling import SampleManifest, write_manifest
from tests.unit.evals.trace_fixtures import load_fixture

pytestmark = pytest.mark.eval_unit


def test_render_trace_card_has_core_sections() -> None:
    trace = load_fixture("CHK-tool-call-emitted", "fail")
    card = render_trace_card(trace)
    assert "trace_id:" in card
    assert "Phase timeline" in card
    assert "Spend" in card
    assert "File tree" in card
    assert "Spans" in card
    # R3.7: card must not include LLM suggestion chrome
    assert "suggestion" not in card.lower()
    assert "judge" not in card.lower()


def test_saturation_streak_resets_on_new_tag() -> None:
    def _rec(tags: list[str]) -> AnnotationRecord:
        return AnnotationRecord(
            trace_id="t",
            sample_id="s",
            annotator="a",
            annotated_at=datetime.now(tz=UTC),
            tags=tags,
        )

    assert saturation_streak([]) == 0
    assert saturation_streak([_rec(["loop"]), _rec([]), _rec([])]) == 2
    assert saturation_streak([_rec(["a"]), _rec(["a"]), _rec(["b"])]) == 0


def test_annotate_three_resume_skips(tmp_path: Path) -> None:
    """DoD: annotate 3, quit, resume → 3 skipped and file has exactly 3 lines."""
    fixtures = Path("evals/fixtures/traces")
    tids = [
        "CHK-tool-call-emitted__fail__fixture",
        "CHK-tool-call-emitted__pass__fixture",
        "CHK-spend-ceiling__fail__fixture",
    ]
    for tid in tids:
        assert (fixtures / f"{tid}.json").is_file()

    samples_root = tmp_path / "samples"
    ann_root = tmp_path / "annotations"
    manifest = SampleManifest(
        sample_id="test-sample-3",
        strategy="random",
        seed=0,
        n=3,
        filters={},
        corpus_state_hash="abc",
        selection=tids,
        imbalances=[],
    )
    write_manifest(manifest, samples_root=samples_root)

    batch = tmp_path / "batch.jsonl"
    batch.write_text(
        "\n".join(
            [
                '{"trace_id": "CHK-tool-call-emitted__fail__fixture", "note": "n1", "tags": ["omit"]}',
                '{"trace_id": "CHK-tool-call-emitted__pass__fixture", "note": "n2", "tags": []}',
                '{"trace_id": "CHK-spend-ceiling__fail__fixture", "note": "n3", "tags": ["spend"]}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    first = run_annotate_session(
        sample_id="test-sample-3",
        annotator="tester",
        samples_root=samples_root,
        annotations_root=ann_root,
        fixtures_root=fixtures,
        batch_file=batch,
    )
    assert first["written"] == 3
    assert first["skipped"] == 0
    path = annotations_path("tester", annotations_root=ann_root)
    assert path.read_text(encoding="utf-8").count("\n") == 3
    assert len(load_annotations(path)) == 3

    second = run_annotate_session(
        sample_id="test-sample-3",
        annotator="tester",
        samples_root=samples_root,
        annotations_root=ann_root,
        fixtures_root=fixtures,
        batch_file=batch,
    )
    assert second["written"] == 0
    assert second["skipped"] == 3
    assert second["line_count"] == 3
    assert len(annotated_trace_ids(path)) == 3


def test_cli_annotate_batch(tmp_path: Path) -> None:
    fixtures = Path("evals/fixtures/traces")
    tid = "CHK-interrupt-latency__fail__fixture"
    samples_root = tmp_path / "samples"
    ann_root = tmp_path / "annotations"
    write_manifest(
        SampleManifest(
            sample_id="cli-samp",
            strategy="random",
            seed=1,
            n=1,
            filters={},
            corpus_state_hash="x",
            selection=[tid],
            imbalances=[],
        ),
        samples_root=samples_root,
    )
    batch = tmp_path / "b.jsonl"
    batch.write_text(
        f'{{"trace_id": "{tid}", "tags": ["latency"], "note": "cli"}}\n',
        encoding="utf-8",
    )
    rc = main(
        [
            "annotate",
            "--sample",
            "cli-samp",
            "--annotator",
            "cli_user",
            "--batch-file",
            str(batch),
            "--samples-root",
            str(samples_root),
            "--annotations-root",
            str(ann_root),
            "--fixtures-root",
            str(fixtures),
        ]
    )
    assert rc == 0
    assert len(load_annotations(annotations_path("cli_user", annotations_root=ann_root))) == 1


def test_batch_helper_direct(tmp_path: Path) -> None:
    result = run_batch_annotate(
        sample_id="s",
        annotator="a",
        batch_items=[{"trace_id": "t1", "tags": ["x"]}, {"trace_id": "t2", "tags": ["x"]}],
        annotations_root=tmp_path,
    )
    assert result["written"] == 2
    assert result["saturation_streak"] == 1  # second tag not new
