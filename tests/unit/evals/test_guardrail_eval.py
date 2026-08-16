"""Unit tests for guardrail corpus eval (Phase 6 / R6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from evals.corpora.format import GuardrailCase, load_corpus
from evals.guardrail_eval import (
    GuardrailEvaluator,
    evaluate_guardrail,
    invoke_scope_relevance,
    is_provisional,
    load_thresholds,
    scope_relevance_sweep_values,
)


@pytest.mark.eval_unit
def test_scope_relevance_corpus_has_taxonomy_benign_anchors() -> None:
    path = Path("evals/corpora/guardrails/scope_relevance.jsonl")
    cases = load_corpus(path)
    ids = {c.case_id for c in cases}
    assert "tax5-qa-vocab-test-coverage-suite-validation" in ids
    assert "tax5-conftest-standard-pytest-file" in ids
    anchors = [c for c in cases if c.case_id.startswith("tax5-")]
    assert all(c.label == "benign" for c in anchors)


@pytest.mark.eval_unit
def test_guardrail_case_round_trip() -> None:
    case = GuardrailCase(
        case_id="x",
        input={"task_output": "hi", "original_requirements": "req"},
        label="benign",
        source="synthetic",
    )
    restored = GuardrailCase.model_validate_json(case.model_dump_json())
    assert restored == case


@pytest.mark.eval_unit
def test_evaluator_uses_corpus_metrics_and_marks_provisional() -> None:
    thresholds = load_thresholds()["scope_relevance"]
    corpus = load_corpus(Path("evals/corpora/guardrails/scope_relevance.jsonl"))
    result = evaluate_guardrail("scope_relevance", corpus, thresholds=thresholds)
    assert "precision=" in result.report_line
    assert "recall=" in result.report_line
    assert "FPR=" in result.report_line
    # Corpus is below min_cases / minority class floor → provisional
    assert is_provisional(corpus, thresholds) is True
    assert result.provisional is True
    assert result.gate_fail is False  # provisional never gates


@pytest.mark.eval_unit
def test_sweep_marks_configured_floor() -> None:
    corpus = load_corpus(Path("evals/corpora/guardrails/scope_relevance.jsonl"))
    evaluator = GuardrailEvaluator("scope_relevance", invoke_scope_relevance)
    values = scope_relevance_sweep_values()
    assert values[0] == pytest.approx(0.05)
    assert values[-1] == pytest.approx(0.50)
    curve = evaluator.sweep(corpus, "min_relevance", values)
    assert len(curve) == len(values)
    assert all(isinstance(c.total, int) for _, c in curve)
