"""Unit tests for taxonomy propose + check fixture validation (tasks 5.3 / 5.5)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from evals.annotate import AnnotationRecord, append_annotation
from evals.checks.registry import get_check
from evals.checks.validation import (
    confusion_from_pairs,
    evaluate_check_on_fixtures,
    format_validation_report,
    validate_all_check_fms,
    validate_fm_checks,
)
from evals.cli import main
from evals.taxonomy.propose import cluster_tags, format_proposals, propose_from_annotations

pytestmark = pytest.mark.eval_unit


def test_propose_clusters_tags(tmp_path: Path) -> None:
    for tags in (["tool omit", "Tool-Omit"], ["spend loop"], ["spend_loop"]):
        append_annotation(
            AnnotationRecord(
                trace_id="t",
                sample_id="s",
                annotator="p",
                annotated_at=datetime.now(tz=UTC),
                tags=tags,
            ),
            annotations_root=tmp_path,
        )
    clusters = propose_from_annotations(annotations_root=tmp_path)
    keys = {c.canonical for c in clusters}
    assert "tool_omit" in keys
    assert "spend_loop" in keys
    text = format_proposals(clusters)
    assert "NOT auto-added" in text


def test_cluster_tags_marks_known_slugs() -> None:
    rec = AnnotationRecord(
        trace_id="t",
        sample_id="s",
        annotator="a",
        annotated_at=datetime.now(tz=UTC),
        tags=["tool_call_omission", "brand_new_failure"],
    )
    clusters = cluster_tags([rec])
    by_key = {c.canonical: c for c in clusters}
    assert by_key["tool_call_omission"].already_in_taxonomy is True
    assert by_key["brand_new_failure"].already_in_taxonomy is False


def test_confusion_basics() -> None:
    m = confusion_from_pairs([(True, True), (False, False), (True, False), (False, True)])
    assert (m.tp, m.fp, m.tn, m.fn) == (1, 1, 1, 1)
    assert m.tpr == 0.5
    assert m.tnr == 0.5


def test_each_fm_check_meets_fixture_thresholds() -> None:
    payload = validate_all_check_fms()
    assert payload["ok"], format_validation_report(payload)
    for block in payload["failure_modes"]:
        assert block["ok"], block


def test_validate_single_fm() -> None:
    block = validate_fm_checks("FM-001")
    assert block["ok"]
    assert block["checks"][0]["check_id"] == "CHK-tool-call-emitted"
    metrics = block["checks"][0]["metrics"]
    assert metrics["tpr"] == 1.0
    assert metrics["tnr"] == 1.0


def test_evaluate_check_direct() -> None:
    chk = get_check("CHK-spend-ceiling")
    assert chk is not None
    m = evaluate_check_on_fixtures(chk)
    assert m.tp == 1 and m.tn == 1 and m.fp == 0 and m.fn == 0


def test_cli_taxonomy_propose_and_checks_validate(tmp_path: Path) -> None:
    append_annotation(
        AnnotationRecord(
            trace_id="t1",
            sample_id="s",
            annotator="cli",
            annotated_at=datetime.now(tz=UTC),
            tags=["novel_tag"],
        ),
        annotations_root=tmp_path,
    )
    assert (
        main(["taxonomy", "propose", "--from-annotations", "--annotations-root", str(tmp_path)])
        == 0
    )
    assert main(["checks", "validate", "--fm", "FM-007"]) == 0
    assert main(["taxonomy", "coverage", "--require-examples"]) == 0
