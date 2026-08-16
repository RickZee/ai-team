"""Budget ceiling abort in the eval runner (R10.3) — no live API calls."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from evals.cost import BudgetLedger
from evals.run_evals import SuiteContext, _run_single, _write_partial_report
from evals.store import TraceStore
from evals.trace.models import CostRecord

pytestmark = pytest.mark.eval_unit


def test_budget_ceiling_aborts_after_first_run_writes_partial_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With a $0.01 ceiling, the second backend is skipped_budget; report is partial."""
    store = TraceStore(root=tmp_path / "traces")
    ctx = SuiteContext(
        tier="B",
        k=1,
        budget=BudgetLedger(ceiling_usd=0.01),
        store=store,
        pricing_version="2026-08-16",
        yes=True,
        no_judge=True,
        verbose=False,
    )

    class _FakeProc:
        def __init__(self) -> None:
            self.stdout = iter(["ok\n"])

        def wait(self) -> int:
            return 0

    def fake_popen(*_a: Any, **_k: Any) -> _FakeProc:
        return _FakeProc()

    call_count = {"n": 0}

    def fake_emit(**kwargs: Any) -> str:
        call_count["n"] += 1
        # First run burns the entire ceiling so remaining runs abort.
        ctx.budget.record(
            CostRecord(
                usd=0.02,
                input_tokens=100,
                output_tokens=10,
                source="sdk_reported",
            )
        )
        return f"fake-trace-{call_count['n']}"

    monkeypatch.setattr("evals.run_evals.subprocess.Popen", fake_popen)
    monkeypatch.setattr("evals.run_evals._emit_trace", fake_emit)
    monkeypatch.setattr("evals.run_evals._RESULTS_DIR", tmp_path / "results")

    first = _run_single("crewai", "smoke-test", ctx)
    assert first.status == "complete"
    assert ctx.budget.aborted is True

    second = _run_single("langgraph", "smoke-test", ctx)
    assert second.status == "skipped_budget"
    assert any(s["status"] == "skipped_budget" for s in ctx.skipped)

    report = _write_partial_report(ctx, "smoke-test")
    assert report.is_file()
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["aborted"] is True
    assert data["spent_usd"] >= 0.01
    statuses = [o["status"] for o in data["outcomes"]]
    assert "complete" in statuses
    assert "skipped_budget" in statuses
    assert data["skipped_budget"]


def test_projection_requires_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    from evals.run_evals import _confirm_budget_projection

    monkeypatch.delenv("CI", raising=False)
    assert _confirm_budget_projection(3.0, 5.0, yes=False) is False
    assert _confirm_budget_projection(3.0, 5.0, yes=True) is True
    assert _confirm_budget_projection(1.0, 5.0, yes=False) is True

    monkeypatch.setenv("CI", "true")
    assert _confirm_budget_projection(3.0, 5.0, yes=False) is True
