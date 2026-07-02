"""Per-run spend-guard isolation (SHOWCASE_PLAN step 2.1).

Regression: the spend guard was a process-global singleton — concurrent
Compare-tab runs reset each other's accumulation mid-run and combined spend
counted against whichever budget was set last (observed live 2026-07-01:
back-to-back spend_guard_reset lines from 3 backends in one process).
"""

from __future__ import annotations

import threading

import pytest
from ai_team.core.spend_guard import (
    BudgetExceededError,
    current_spend,
    record_usage,
    reset_spend_guard,
)


class TestPerRunIsolation:
    def test_two_threads_have_independent_budgets(self) -> None:
        """Each thread's run enforces its own ceiling; no cross-contamination."""
        results: dict[str, object] = {}
        barrier = threading.Barrier(2)

        def run_a() -> None:
            reset_spend_guard(1.0, run_id="run-a")
            barrier.wait()  # both runs reset before either records
            try:
                record_usage(0.5)
                record_usage(0.4)  # 0.9 total — under run A's $1 budget
                results["a"] = "ok"
            except BudgetExceededError:
                results["a"] = "aborted"

        def run_b() -> None:
            reset_spend_guard(0.1, run_id="run-b")
            barrier.wait()
            try:
                record_usage(0.2)  # over run B's $0.10 budget
                results["b"] = "ok"
            except BudgetExceededError:
                results["b"] = "aborted"

        ta, tb = threading.Thread(target=run_a), threading.Thread(target=run_b)
        ta.start(), tb.start()
        ta.join(5), tb.join(5)

        # Pre-fix behavior: run B's reset (last) wiped A's state; A's $0.9
        # counted against B's $0.10 ceiling and both saw each other's spend.
        assert results["a"] == "ok", "run A aborted against a budget that isn't its own"
        assert results["b"] == "aborted", "run B's own $0.10 ceiling did not fire"

    def test_registry_reads_by_run_id_cross_thread(self) -> None:
        def worker() -> None:
            reset_spend_guard(5.0, run_id="registry-run")
            record_usage(0.25, total_tokens=1234)

        t = threading.Thread(target=worker)
        t.start()
        t.join(5)

        snap = current_spend(run_id="registry-run")
        assert snap["spent_usd"] == pytest.approx(0.25)
        assert snap["total_tokens"] == 1234
        assert snap["calls"] == 1

    def test_unknown_run_id_returns_zeros(self) -> None:
        snap = current_spend(run_id="never-existed")
        assert snap["spent_usd"] == 0.0
        assert snap["calls"] == 0

    def test_legacy_global_fallback_still_enforces(self) -> None:
        """Contexts that call reset without threads keep old behavior."""
        reset_spend_guard(0.1)
        with pytest.raises(BudgetExceededError):
            record_usage(0.2)
