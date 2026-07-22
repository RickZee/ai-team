"""Tests for backend-comparison statistics.

The load-bearing claim these protect: at n=5, a "1/5 vs 5/5" split does **not**
support a ranking, because the Wilson intervals overlap. The batch runner must say
"no significant difference" rather than print a winner.
"""

from __future__ import annotations

import pytest

from scripts.batch_stats import (
    Interval,
    bootstrap_median_ci,
    min_n_for_separation,
    verdict_is_supported,
    wilson_interval,
)


class TestWilsonInterval:
    def test_point_estimate_is_the_raw_proportion(self) -> None:
        assert wilson_interval(1, 5).point == pytest.approx(0.2)

    def test_interval_contains_point(self) -> None:
        i = wilson_interval(1, 5)
        assert i.low <= i.point <= i.high

    def test_one_of_five_is_very_wide(self) -> None:
        # The headline critique: 1/5 is not "20%", it is "somewhere between
        # almost never and most of the time".
        i = wilson_interval(1, 5)
        assert i.low < 0.06
        assert i.high > 0.60

    def test_stays_inside_unit_range_at_extremes(self) -> None:
        for successes in (0, 5):
            i = wilson_interval(successes, 5)
            assert 0.0 <= i.low <= i.high <= 1.0

    def test_interval_narrows_as_n_grows(self) -> None:
        narrow = wilson_interval(50, 100)
        wide = wilson_interval(5, 10)
        assert (narrow.high - narrow.low) < (wide.high - wide.low)

    def test_zero_trials_is_maximally_uncertain(self) -> None:
        i = wilson_interval(0, 0)
        assert (i.low, i.high) == (0.0, 1.0)

    def test_successes_above_trials_rejected(self) -> None:
        with pytest.raises(ValueError, match="out of range"):
            wilson_interval(6, 5)


class TestVerdictRule:
    def test_one_of_five_vs_five_of_five_is_not_supported_at_n5(self) -> None:
        # This is the exact comparison the README used to assert as a ranking.
        langgraph = wilson_interval(1, 5)
        crewai = wilson_interval(5, 5)
        assert verdict_is_supported(langgraph, crewai) is False

    def test_clear_separation_at_large_n_is_supported(self) -> None:
        assert verdict_is_supported(wilson_interval(5, 100), wilson_interval(95, 100)) is True

    def test_overlap_is_symmetric(self) -> None:
        a, b = wilson_interval(1, 5), wilson_interval(4, 5)
        assert a.overlaps(b) == b.overlaps(a)

    def test_touching_intervals_count_as_overlapping(self) -> None:
        a = Interval(point=0.5, low=0.4, high=0.6)
        b = Interval(point=0.7, low=0.6, high=0.8)
        assert verdict_is_supported(a, b) is False


class TestBootstrapMedian:
    def test_point_is_the_sample_median(self) -> None:
        assert bootstrap_median_ci([1.0, 2.0, 3.0, 4.0, 5.0]).point == pytest.approx(3.0)

    def test_interval_brackets_the_median(self) -> None:
        ci = bootstrap_median_ci([10.0, 12.0, 11.0, 40.0, 13.0])
        assert ci.low <= ci.point <= ci.high

    def test_deterministic_for_reproducible_tables(self) -> None:
        vals = [3.0, 9.0, 4.0, 20.0, 5.0]
        assert bootstrap_median_ci(vals) == bootstrap_median_ci(vals)

    def test_single_value_has_degenerate_interval(self) -> None:
        ci = bootstrap_median_ci([7.0])
        assert (ci.point, ci.low, ci.high) == (7.0, 7.0, 7.0)

    def test_empty_sample_is_safe(self) -> None:
        assert bootstrap_median_ci([]).point == 0.0


class TestSamplePlanning:
    def test_reports_n_needed_to_separate_plausible_rates(self) -> None:
        n = min_n_for_separation(0.2, 1.0)
        assert n is not None
        # The practical point: separating these needs materially more than 5 runs.
        assert n > 5

    def test_identical_rates_never_separate(self) -> None:
        assert min_n_for_separation(0.5, 0.5, max_n=50) is None

    def test_rates_are_validated(self) -> None:
        with pytest.raises(ValueError, match=r"\[0, 1\]"):
            min_n_for_separation(1.5, 0.5)
