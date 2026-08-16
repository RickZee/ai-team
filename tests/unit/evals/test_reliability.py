"""Unit tests for reliability metrics (R9), including Wilson CI exact values."""

from __future__ import annotations

import pytest

from evals.reliability import (
    CellResult,
    cell_summary,
    indistinguishable,
    is_flaky,
    pass_at_k,
    pass_pow_k,
    pass_rate,
    wilson_ci,
)

pytestmark = pytest.mark.eval_unit


@pytest.mark.parametrize(
    ("successes", "n", "expected"),
    [
        (3, 3, (0.438, 1.000)),
        (2, 3, (0.208, 0.939)),
        (0, 3, (0.000, 0.562)),
        (95, 100, (0.888, 0.978)),
    ],
)
def test_wilson_ci_published_values(successes: int, n: int, expected: tuple[float, float]) -> None:
    lo, hi = wilson_ci(successes, n)
    assert round(lo, 3) == expected[0]
    assert round(hi, 3) == expected[1]


def test_wilson_ci_n_zero() -> None:
    assert wilson_ci(0, 0) == (0.0, 0.0)


def test_pass_at_k_and_pow() -> None:
    assert pass_at_k([False, False, True]) == 1.0
    assert pass_at_k([False, False, False]) == 0.0
    assert pass_pow_k([True, True, True]) == 1.0
    assert pass_pow_k([True, False, True]) == 0.0
    assert pass_at_k([]) == 0.0
    assert pass_pow_k([]) == 0.0


def test_pass_rate() -> None:
    assert pass_rate([True, False, True]) == pytest.approx(2 / 3)
    assert pass_rate([]) == 0.0


def test_is_flaky() -> None:
    assert is_flaky([True, False, True]) is True
    assert is_flaky([True, True, True]) is False
    assert is_flaky([False, False]) is False
    assert is_flaky([]) is False


def test_indistinguishable_overlapping_cis() -> None:
    a = CellResult(successes=2, n=3)
    b = CellResult(successes=3, n=3)
    assert indistinguishable(a, b) is True


def test_indistinguishable_separated() -> None:
    a = CellResult(successes=0, n=100)
    b = CellResult(successes=95, n=100)
    assert indistinguishable(a, b) is False


def test_cell_summary_includes_n_and_ci() -> None:
    summary = cell_summary([True, True, False])
    assert summary["n"] == 3
    assert summary["successes"] == 2
    assert summary["flaky"] is True
    lo, hi = summary["wilson_ci"]  # type: ignore[misc]
    assert round(lo, 3) == 0.208
    assert round(hi, 3) == 0.939
