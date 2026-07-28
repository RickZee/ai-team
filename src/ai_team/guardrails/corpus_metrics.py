"""Precision/recall accounting for guardrail evaluation against a labeled corpus.

Guardrail thresholds in this project were historically tuned on a single run — a
scope floor moved 0.25 -> 0.15 off one batch's readings. That is exactly the n=1
mistake the comparison side of the project warns against, applied to the defense
layer. This module lets a change to a guardrail be scored against a corpus of
human-labeled cases instead, so "I lowered the false-positive rate" becomes a number
you can check rather than a hope.

Convention:
    * A guardrail *firing* (returning ``fail``) is a "positive" prediction.
    * A case labeled ``fail`` is a real violation (condition positive).
    * ``warn`` and ``pass`` both count as "did not fire" — the guardrail let it
      through, which is the correct outcome for a benign case.

So a **false positive** is the guardrail failing a benign case (the journal's
recurring pain), and a **false negative** is it passing a real violation (a security
hole walking through). Both matter; the corpus tracks them separately.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConfusionCounts:
    true_positive: int = 0
    false_positive: int = 0
    true_negative: int = 0
    false_negative: int = 0

    @property
    def total(self) -> int:
        return self.true_positive + self.false_positive + self.true_negative + self.false_negative

    @property
    def precision(self) -> float:
        """Of the cases the guardrail fired on, how many were real? (1.0 if it never fired.)"""
        fired = self.true_positive + self.false_positive
        return self.true_positive / fired if fired else 1.0

    @property
    def recall(self) -> float:
        """Of the real violations, how many did it catch? (1.0 if there were none.)"""
        real = self.true_positive + self.false_negative
        return self.true_positive / real if real else 1.0

    @property
    def false_positive_rate(self) -> float:
        """Of the benign cases, how many did it wrongly fire on? (0.0 if there were none.)"""
        benign = self.false_positive + self.true_negative
        return self.false_positive / benign if benign else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0


def classify(*, fired: bool, is_real_violation: bool) -> str:
    """Return which confusion-matrix cell a single outcome lands in."""
    if fired and is_real_violation:
        return "true_positive"
    if fired and not is_real_violation:
        return "false_positive"
    if not fired and is_real_violation:
        return "false_negative"
    return "true_negative"


def score(outcomes: list[tuple[bool, bool]]) -> ConfusionCounts:
    """Tally ``(fired, is_real_violation)`` outcomes into confusion counts."""
    cells = {
        "true_positive": 0,
        "false_positive": 0,
        "true_negative": 0,
        "false_negative": 0,
    }
    for fired, is_real in outcomes:
        cells[classify(fired=fired, is_real_violation=is_real)] += 1
    return ConfusionCounts(**cells)


def format_report(name: str, counts: ConfusionCounts) -> str:
    """One-line human summary for CI logs and PR pastes."""
    return (
        f"{name}: n={counts.total} "
        f"precision={counts.precision:.2f} recall={counts.recall:.2f} "
        f"FPR={counts.false_positive_rate:.2f} f1={counts.f1:.2f} "
        f"(TP={counts.true_positive} FP={counts.false_positive} "
        f"FN={counts.false_negative} TN={counts.true_negative})"
    )
