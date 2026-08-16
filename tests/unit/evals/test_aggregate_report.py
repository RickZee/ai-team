"""Unit tests for SuiteReport aggregation (Phase 8)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from evals.aggregate import (
    JudgeVerdictRecord,
    SuiteReport,
    assemble_suite_report,
    make_rate,
)
from evals.alignment import bias_corrected_rate
from evals.checks.base import CheckResult
from evals.provenance import Provenance
from evals.report import (
    render_html,
    render_markdown,
    render_summary,
    report_json_without_generated_at,
    write_report,
)

pytestmark = pytest.mark.eval_unit

_GOLDEN = Path(__file__).resolve().parents[2] / "fixtures" / "evals" / "report.json"

_PROV = Provenance(
    git_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    git_dirty=False,
    python_version="3.12.0",
    platform="test-platform",
    harness_version="0.1.0",
    taxonomy_version="1.0.0",
    pricing_table_version="2026-08-16",
    tier="A",
)


def test_suite_report_schema_roundtrip() -> None:
    """SuiteReport dumps/loads via JSON schema without error."""
    report = assemble_suite_report(
        run_id="schema_test",
        tier="A",
        check_results=[],
        provenance=_PROV,
        generated_at=datetime(2026, 8, 16, tzinfo=UTC),
    )
    raw = report.model_dump_json()
    loaded = SuiteReport.model_validate_json(raw)
    assert loaded.run_id == "schema_test"
    assert SuiteReport.model_json_schema()["title"] == "SuiteReport"


def test_golden_report_fixture_matches_schema() -> None:
    """Committed golden report.json validates and is stable under re-dump."""
    assert _GOLDEN.is_file(), f"missing golden fixture {_GOLDEN}"
    data = json.loads(_GOLDEN.read_text(encoding="utf-8"))
    report = SuiteReport.model_validate(data)
    # Re-serialize with sort_keys and compare to golden (already sort_keys)
    rerendered = json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    assert rerendered == _GOLDEN.read_text(encoding="utf-8")


def test_make_rate_wilson_and_format() -> None:
    rate = make_rate(2, 3)
    assert rate.n == 3
    assert rate.value == pytest.approx(2 / 3)
    assert 0.0 <= rate.ci_low <= rate.value <= rate.ci_high <= 1.0
    assert "n=3" in rate.format()
    assert "95% CI" in rate.format()


def test_bias_corrected_beside_raw() -> None:
    """Raw and bias-corrected sit side by side; weak judges suppress correction."""
    assert bias_corrected_rate(0.5, 1.0, 1.0) == pytest.approx(0.5)
    assert bias_corrected_rate(0.5, 0.55, 0.55) is None  # denom 0.1 ≤ 0.2

    results = [
        CheckResult(
            check_id="CHK-tool-call-emitted",
            failure_mode_id="FM-001",
            trace_id="t1",
            outcome="fail",
            evidence_span_ids=["span_0000"],
        ),
        CheckResult(
            check_id="CHK-tool-call-emitted",
            failure_mode_id="FM-001",
            trace_id="t2",
            outcome="pass",
        ),
    ]
    from evals.aggregate import JudgeAlignmentSummary

    report = assemble_suite_report(
        run_id="bias",
        tier="A",
        check_results=results,
        provenance=_PROV,
        judge_summaries=[
            JudgeAlignmentSummary(
                judge_id="fm-001",
                eligible_to_gate=True,
                tpr=1.0,
                tnr=1.0,
                failure_rate=make_rate(1, 2),
            )
        ],
        generated_at=datetime(2026, 8, 16, tzinfo=UTC),
    )
    fm = next(x for x in report.failure_mode_incidence if x.failure_mode_id == "FM-001")
    assert fm.raw.value == pytest.approx(0.5)
    assert fm.raw.bias_corrected == pytest.approx(0.5)


def test_r76_single_vendor_indeterminate() -> None:
    report = assemble_suite_report(
        run_id="r76",
        tier="A",
        check_results=[],
        provenance=_PROV,
        cell_outcomes={
            ("crewai", "smoke-test"): [True],
            ("claude-agent-sdk", "smoke-test"): [True],
        },
        judge_verdicts=[
            JudgeVerdictRecord(
                judge_id="j1",
                trace_id="t",
                verdict="pass",
                single_vendor=True,
                vendor="anthropic",
            )
        ],
        generated_at=datetime(2026, 8, 16, tzinfo=UTC),
    )
    assert any(c.status == "indeterminate" for c in report.comparisons)
    assert report.verdict == "indeterminate"
    assert all(c.outcome == "indeterminate" for c in report.scorecard)


def test_suppressed_section_for_non_eligible_judges() -> None:
    from evals.aggregate import JudgeAlignmentSummary

    report = assemble_suite_report(
        run_id="sup",
        tier="A",
        check_results=[],
        provenance=_PROV,
        judge_summaries=[
            JudgeAlignmentSummary(
                judge_id="advisory-judge",
                eligible_to_gate=False,
                suppression_reason="κ below floor",
            )
        ],
        generated_at=datetime(2026, 8, 16, tzinfo=UTC),
    )
    assert any("advisory-judge" in s for s in report.suppressed)


def test_layer_incidence_present() -> None:
    results = [
        CheckResult(
            check_id="CHK-tool-call-emitted",
            failure_mode_id="FM-001",
            trace_id="t1",
            outcome="fail",
        ),
        CheckResult(
            check_id="CHK-provider-error-rate",
            failure_mode_id="FM-009",
            trace_id="t1",
            outcome="fail",
        ),
    ]
    report = assemble_suite_report(
        run_id="layers",
        tier="A",
        check_results=results,
        provenance=_PROV,
        generated_at=datetime(2026, 8, 16, tzinfo=UTC),
    )
    layers = {L.layer for L in report.layer_incidence}
    assert layers == {"model", "framework", "harness", "provider"}
    model = next(L for L in report.layer_incidence if L.layer == "model")
    assert model.fail_count >= 1


def test_report_emitters_from_golden(tmp_path: Path) -> None:
    report = SuiteReport.model_validate_json(_GOLDEN.read_text(encoding="utf-8"))
    paths = write_report(report, out_dir=tmp_path)
    assert paths["report.json"].is_file()
    assert paths["report.md"].is_file()
    assert paths["report.html"].is_file()
    assert paths["summary.txt"].is_file()
    summary = paths["summary.txt"].read_text(encoding="utf-8")
    assert summary.count("\n") <= 20

    html = paths["report.html"].read_text(encoding="utf-8")
    assert "<svg" in html
    assert "cdn." not in html.lower()
    assert "<script src=" not in html.lower()
    assert 'link rel="stylesheet"' not in html.lower()
    # xmlns is allowed; block external http(s) resource URLs beyond SVG xmlns
    for token in ("https://cdn", "http://cdn", "unpkg.com", "jsdelivr"):
        assert token not in html

    md = render_markdown(report)
    assert "## 1. Headline verdict" in md
    assert "## 5. Reliability budget by layer" in md
    assert "## 11. Provenance" in md
    # Failed checks name trace_id + span_id
    assert "trace_fail_001" in md
    assert "span_0001" in md

    assert "eval[A]" in render_summary(report)
    assert render_html(report).startswith("<!DOCTYPE html>")


def test_format_scorecard_still_importable() -> None:
    from evals.fixtures import EvalResult
    from evals.metrics import format_scorecard
    from evals.report import format_scorecard as reexported

    assert format_scorecard is reexported
    result = EvalResult(
        backend="crewai",
        scenario_id="smoke-test",
        success=True,
        current_phase="complete",
        metrics={"required_files_present": True},
    )
    text = format_scorecard(result)
    assert "Backend: crewai" in text


def test_report_json_without_generated_at(tmp_path: Path) -> None:
    report = SuiteReport.model_validate_json(_GOLDEN.read_text(encoding="utf-8"))
    write_report(report, out_dir=tmp_path)
    canonical = report_json_without_generated_at(tmp_path / "report.json")
    assert "generated_at" not in json.loads(canonical)
