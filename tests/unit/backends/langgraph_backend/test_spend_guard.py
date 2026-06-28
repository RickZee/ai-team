"""Tests for the per-run spend guard (G4): aborts runaway crash/retry loops."""

from __future__ import annotations

import pytest
from ai_team.backends.langgraph_backend.graphs import spend_guard as sg
from ai_team.backends.langgraph_backend.graphs.spend_guard import (
    BudgetExceededError,
    current_spend,
    record_usage,
    reset_spend_guard,
)


@pytest.fixture(autouse=True)
def _clean_state() -> None:
    """Each test starts from a known budget."""
    reset_spend_guard(1.0)


class TestSpendAccumulation:
    def test_records_cost_and_tokens(self) -> None:
        record_usage(0.10, 500)
        record_usage(0.05, 250)
        snap = current_spend()
        assert snap["spent_usd"] == pytest.approx(0.15)
        assert snap["total_tokens"] == 750
        assert snap["calls"] == 2

    def test_reset_clears_counters(self) -> None:
        record_usage(0.30, 100)
        reset_spend_guard(2.0)
        snap = current_spend()
        assert snap["spent_usd"] == 0.0
        assert snap["total_tokens"] == 0
        assert snap["calls"] == 0
        assert snap["budget_usd"] == 2.0

    def test_negative_cost_clamped(self) -> None:
        record_usage(-5.0, -10)
        snap = current_spend()
        assert snap["spent_usd"] == 0.0
        assert snap["total_tokens"] == 0


class TestBudgetCeiling:
    def test_raises_when_exceeded(self) -> None:
        record_usage(0.60)
        with pytest.raises(BudgetExceededError) as exc:
            record_usage(0.50)  # cumulative 1.10 > 1.00
        assert "exceeded budget" in str(exc.value)

    def test_does_not_raise_at_or_below_budget(self) -> None:
        record_usage(0.50)
        record_usage(0.50)  # exactly 1.00, not over
        assert current_spend()["spent_usd"] == pytest.approx(1.0)

    def test_zero_budget_disables_ceiling(self) -> None:
        reset_spend_guard(0.0)
        record_usage(100.0)  # huge spend, no raise
        record_usage(100.0)
        assert current_spend()["spent_usd"] == pytest.approx(200.0)

    def test_env_default_budget(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(sg.DEFAULT_BUDGET_ENV, "0.25")
        reset_spend_guard()  # None → resolves from env
        record_usage(0.20)
        with pytest.raises(BudgetExceededError):
            record_usage(0.10)  # 0.30 > 0.25

    def test_bad_env_falls_back_to_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(sg.DEFAULT_BUDGET_ENV, "not-a-number")
        reset_spend_guard()
        assert current_spend()["budget_usd"] == sg.DEFAULT_BUDGET_USD


class TestNonRetryableSemantics:
    """The abort must bypass the phase nodes' ``except Exception`` retry handlers."""

    def test_not_caught_by_except_exception(self) -> None:
        reset_spend_guard(0.001)
        caught_as_exception = False
        try:
            try:
                record_usage(0.01)
            except Exception:  # noqa: BLE001 - deliberately broad, mirrors phase nodes
                caught_as_exception = True
        except BudgetExceededError:
            pass
        assert caught_as_exception is False, "budget abort must bypass except Exception"

    def test_is_base_exception(self) -> None:
        assert issubclass(BudgetExceededError, BaseException)
        assert not issubclass(BudgetExceededError, Exception)
