"""Harness acceptance marks passing, failing, and unverified."""

from __future__ import annotations

from pathlib import Path

from ai_team.backends.common.acceptance import (
    Criterion,
    CriterionEvidence,
    apply_quality_gate_acceptance,
    evaluate,
)

from evals.trace.builder import TraceBuilder


def test_missing_evidence_is_never_passing() -> None:
    results = evaluate(
        [Criterion(id="add", description="adds")],
        {},
    )
    assert results[0].status == "unverified"


def test_passing_failing_and_unverified() -> None:
    criteria = [
        Criterion(id="add"),
        Criterion(id="lint"),
        Criterion(id="silent"),
    ]
    evidence = {
        "add": CriterionEvidence(tests_passed=True, lint_ok=True),
        "lint": CriterionEvidence(tests_passed=True, lint_ok=False),
    }
    results = {row.criterion_id: row.status for row in evaluate(criteria, evidence)}
    assert results == {"add": "passing", "lint": "failing", "silent": "unverified"}


def test_qa_reject_on_passing_evidence_is_one_disagreement_span(tmp_path: Path) -> None:
    apply_quality_gate_acceptance(
        tmp_path,
        tests_passed=True,
        qa_verdicts={"harness-tests": "reject"},
    )
    (tmp_path / "run.json").write_text(
        '{"backend":"langgraph","started_at":"2026-09-01T00:00:00+00:00",'
        '"project_id":"q","workspace_dir":"' + str(tmp_path) + '",'
        '"output_dir":"' + str(tmp_path) + '"}',
        encoding="utf-8",
    )
    trace = TraceBuilder(backend="langgraph", scenario={"id": "qa"}).from_workspace(tmp_path)
    spans = trace.spans_of("qa_disagreement")
    assert len(spans) == 1
    assert spans[0].payload["qa_verdict"] == "reject"


def test_september_pattern_records_an_accept_without_a_qa_tool(tmp_path: Path) -> None:
    """Passing tests and a QA agent with no accept tool still record an accept.

    September's LangGraph and CrewAI corpus had 0 accepts for this shape.
    """
    results = apply_quality_gate_acceptance(tmp_path, tests_passed=True, qa_verdicts={})
    assert any(row.status == "passing" for row in results)
