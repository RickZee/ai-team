"""Reliability metrics for k-run eval cells (R9)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class CellResult:
    """Aggregated outcomes for one backend × scenario cell."""

    successes: int
    n: int

    @classmethod
    def from_outcomes(cls, outcomes: Sequence[bool]) -> CellResult:
        """Build a cell from a sequence of boolean trial outcomes."""
        return cls(successes=sum(1 for o in outcomes if o), n=len(outcomes))


def pass_at_k(outcomes: Sequence[bool]) -> float:
    """``pass@k``: 1.0 if any trial succeeded, else 0.0 (R9.1)."""
    if not outcomes:
        return 0.0
    return float(any(outcomes))


def pass_pow_k(outcomes: Sequence[bool]) -> float:
    """``pass^k``: 1.0 if every trial succeeded, else 0.0 (R9.1)."""
    if not outcomes:
        return 0.0
    return float(all(outcomes))


def pass_rate(outcomes: Sequence[bool]) -> float:
    """Fraction of successful trials (R9.1)."""
    if not outcomes:
        return 0.0
    return sum(1 for o in outcomes if o) / len(outcomes)


def wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score 95% confidence interval for a binomial proportion (R9.4).

    Args:
        successes: Number of successes (``0 ≤ successes ≤ n``).
        n: Number of trials.
        z: Standard-normal critical value (default 1.96 → ~95%).

    Returns:
        ``(lower, upper)`` clipped to ``[0, 1]``. Returns ``(0.0, 0.0)`` when
        ``n == 0``.
    """
    if n <= 0:
        return (0.0, 0.0)
    if successes < 0 or successes > n:
        raise ValueError(f"successes must be in [0, n]; got {successes}/{n}")

    p_hat = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    centre = (p_hat + z2 / (2.0 * n)) / denom
    spread = (z / denom) * math.sqrt(p_hat * (1.0 - p_hat) / n + z2 / (4.0 * n * n))
    lower = max(0.0, centre - spread)
    upper = min(1.0, centre + spread)
    return (lower, upper)


def is_flaky(outcomes: Sequence[bool]) -> bool:
    """True when ``0 < pass_rate < 1`` (R9.3)."""
    if not outcomes:
        return False
    successes = sum(1 for o in outcomes if o)
    return 0 < successes < len(outcomes)


def _overlaps(a: tuple[float, float], b: tuple[float, float]) -> bool:
    """True when closed intervals *a* and *b* overlap."""
    return a[0] <= b[1] and b[0] <= a[1]


def indistinguishable(a: CellResult, b: CellResult) -> bool:
    """True when Wilson CIs overlap — difference not meaningful at this n (R9.5)."""
    return _overlaps(wilson_ci(a.successes, a.n), wilson_ci(b.successes, b.n))


def cell_summary(outcomes: Sequence[bool]) -> dict[str, float | int | bool | tuple[float, float]]:
    """Build a report-ready summary dict for one cell (includes ``n`` and CI)."""
    cell = CellResult.from_outcomes(outcomes)
    lo, hi = wilson_ci(cell.successes, cell.n)
    return {
        "n": cell.n,
        "successes": cell.successes,
        "pass_at_k": pass_at_k(outcomes),
        "pass_pow_k": pass_pow_k(outcomes),
        "pass_rate": pass_rate(outcomes),
        "wilson_ci": (lo, hi),
        "flaky": is_flaky(outcomes),
    }
