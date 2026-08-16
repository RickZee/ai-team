"""Unit tests for alignment math only (Phase 7.3 / R8) — no judge quality asserts."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from evals.alignment import (
    bias_corrected_rate,
    bootstrap_ci,
    cohens_kappa,
    confusion,
)
from evals.golden import GoldenLabel
from evals.judges.base import Verdict


def _verdict(unit_id: str, label: str) -> Verdict:
    return Verdict(
        judge_id="test-judge",
        prompt_hash="abc",
        model_id="m",
        provider="anthropic",
        trace_id="t",
        labeling_unit_id=unit_id,
        verdict=label,  # type: ignore[arg-type]
        reason="r",
        evidence_quote="q",
        evidence_sha256="0" * 64,
        single_vendor=False,
    )


def _label(unit_id: str, human: str) -> GoldenLabel:
    return GoldenLabel(
        labeling_unit_id=unit_id,
        trace_id="t",
        span_id="run",
        failure_mode_id="FM-001",
        human_label=human,  # type: ignore[arg-type]
        annotator="test",
        labeled_at=datetime.now(UTC),
        split="test",
    )


@pytest.mark.eval_unit
def test_confusion_hand_computed() -> None:
    # fail=present prediction. Matrix: TP=2, FP=1, TN=3, FN=1
    verdicts = [
        _verdict("a", "fail"),  # present → TP
        _verdict("b", "fail"),  # present → TP
        _verdict("c", "fail"),  # absent → FP
        _verdict("d", "pass"),  # absent → TN
        _verdict("e", "pass"),  # absent → TN
        _verdict("f", "pass"),  # absent → TN
        _verdict("g", "pass"),  # present → FN
        _verdict("h", "error"),  # excluded
    ]
    labels = [
        _label("a", "present"),
        _label("b", "present"),
        _label("c", "absent"),
        _label("d", "absent"),
        _label("e", "absent"),
        _label("f", "absent"),
        _label("g", "present"),
        _label("h", "present"),
    ]
    tp, fp, tn, fn = confusion(verdicts, labels)
    assert (tp, fp, tn, fn) == (2, 1, 3, 1)
    tpr = tp / (tp + fn)
    tnr = tn / (tn + fp)
    assert tpr == pytest.approx(2 / 3)
    assert tnr == pytest.approx(3 / 4)


@pytest.mark.eval_unit
def test_cohens_kappa_perfect_and_hand() -> None:
    assert cohens_kappa(10, 0, 10, 0) == pytest.approx(1.0)
    # From earlier matrix: tp=2,fp=1,tn=3,fn=1 → n=7
    # po = 5/7; pe = ((3/7)*(3/7))+((4/7)*(4/7))
    tp, fp, tn, fn = 2, 1, 3, 1
    po = 5 / 7
    pe = (3 / 7) * (3 / 7) + (4 / 7) * (4 / 7)
    expected = (po - pe) / (1 - pe)
    assert cohens_kappa(tp, fp, tn, fn) == pytest.approx(expected)


@pytest.mark.eval_unit
def test_bootstrap_ci_deterministic_under_seed() -> None:
    pairs = [(True, True), (False, False), (True, False), (False, True)] * 5

    def rate(sample: list[tuple[bool, bool]]) -> float:
        return sum(1 for p, a in sample if p == a) / len(sample)

    a = bootstrap_ci(pairs, rate, n_resamples=2000, seed=42)
    b = bootstrap_ci(pairs, rate, n_resamples=2000, seed=42)
    assert a == b
    assert a[0] <= a[1]
    # Different seeds may or may not diverge on tiny samples; determinism is the contract.
    c = bootstrap_ci(pairs * 3, rate, n_resamples=500, seed=1)
    d = bootstrap_ci(pairs * 3, rate, n_resamples=500, seed=1)
    assert c == d


@pytest.mark.eval_unit
def test_bias_corrected_rate_edges() -> None:
    # Suppression boundary: denom == 0.2 → None; denom just above → value
    assert bias_corrected_rate(0.5, tpr=0.6, tnr=0.6) is None  # denom=0.2
    assert bias_corrected_rate(0.5, tpr=0.59, tnr=0.6) is None  # denom=0.19
    # Identity when TPR = TNR = 1.0
    assert bias_corrected_rate(0.4, tpr=1.0, tnr=1.0) == pytest.approx(0.4)
    # Worked example: observed=0.5, tpr=0.9, tnr=0.8 → denom=0.7
    # p = (0.5 + 0.8 - 1) / 0.7 = 0.3 / 0.7
    assert bias_corrected_rate(0.5, tpr=0.9, tnr=0.8) == pytest.approx(0.3 / 0.7)
    # Clamp
    assert bias_corrected_rate(1.0, tpr=0.9, tnr=0.9) == pytest.approx(1.0)
