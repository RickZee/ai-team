"""Statistics for backend comparison batches.

Why this exists: a green-rate like "1/5" reads as decisive and is not. The 95%
Wilson interval on 1/5 runs roughly 1%-72%, which overlaps almost any other
backend's interval at n=5. Publishing point estimates from small batches is how
a comparison table ends up asserting differences the data cannot support.

Everything here is pure and dependency-free so it can be unit-tested without
running a batch.
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass

# 1.959963985 = z for a two-sided 95% normal interval.
Z_95 = 1.959963985


@dataclass(frozen=True)
class Interval:
    """A point estimate with a confidence interval."""

    point: float
    low: float
    high: float

    def overlaps(self, other: Interval) -> bool:
        return self.low <= other.high and other.low <= self.high

    def as_pct(self) -> str:
        return f"{self.point * 100:.0f}% [{self.low * 100:.0f}–{self.high * 100:.0f}]"


def wilson_interval(successes: int, trials: int, z: float = Z_95) -> Interval:
    """Wilson score interval for a binomial proportion.

    Preferred over the normal approximation because it stays inside [0, 1] and
    behaves sanely at the extremes (0/5 and 5/5), which is exactly where small
    agent batches live.
    """
    if trials <= 0:
        return Interval(0.0, 0.0, 1.0)
    if successes < 0 or successes > trials:
        msg = f"successes={successes} out of range for trials={trials}"
        raise ValueError(msg)

    p = successes / trials
    denom = 1 + z**2 / trials
    center = (p + z**2 / (2 * trials)) / denom
    margin = (z * math.sqrt(p * (1 - p) / trials + z**2 / (4 * trials**2))) / denom
    return Interval(point=p, low=max(0.0, center - margin), high=min(1.0, center + margin))


def bootstrap_median_ci(
    values: list[float],
    *,
    iterations: int = 2000,
    z_pct: float = 95.0,
    seed: int = 0,
) -> Interval:
    """Percentile bootstrap CI for the median of a small sample.

    Deterministic by default (fixed seed) so a published table can be regenerated
    exactly. Timings are heavily skewed by retries, so the median plus a bootstrap
    interval says more than mean +/- stdev.
    """
    if not values:
        return Interval(0.0, 0.0, 0.0)
    if len(values) == 1:
        only = float(values[0])
        return Interval(only, only, only)

    rng = random.Random(seed)
    n = len(values)
    medians = [
        statistics.median([values[rng.randrange(n)] for _ in range(n)]) for _ in range(iterations)
    ]
    medians.sort()
    tail = (100.0 - z_pct) / 2.0
    lo_idx = max(0, int(iterations * tail / 100.0))
    hi_idx = min(iterations - 1, int(iterations * (100.0 - tail) / 100.0))
    return Interval(
        point=statistics.median(values),
        low=medians[lo_idx],
        high=medians[hi_idx],
    )


def verdict_is_supported(a: Interval, b: Interval) -> bool:
    """True only when two intervals do not overlap.

    The project rule: **no verdict where confidence intervals overlap.** If this
    returns False, the honest statement is "no significant difference at this n",
    not a ranking.
    """
    return not a.overlaps(b)


def min_n_for_separation(rate_a: float, rate_b: float, *, max_n: int = 200) -> int | None:
    """Smallest n at which two true green-rates would give non-overlapping intervals.

    Planning aid: answers "how many runs would this comparison actually need?"
    Returns None if separation is not reached within ``max_n``.
    """
    if not (0.0 <= rate_a <= 1.0 and 0.0 <= rate_b <= 1.0):
        msg = "rates must be in [0, 1]"
        raise ValueError(msg)
    for n in range(2, max_n + 1):
        ia = wilson_interval(round(rate_a * n), n)
        ib = wilson_interval(round(rate_b * n), n)
        if not ia.overlaps(ib):
            return n
    return None
