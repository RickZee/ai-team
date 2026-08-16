"""Unit tests for cost normalization and BudgetLedger (R10)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from evals.cost import (
    BudgetLedger,
    load_pricing,
    normalize_cost,
    project_run_cost,
    project_suite_cost,
)
from evals.provenance import Provenance
from evals.store import TraceStore
from evals.trace.models import SCHEMA_VERSION, CostRecord, Trace

pytestmark = pytest.mark.eval_unit


def _prov(**kwargs: object) -> Provenance:
    base: dict[str, object] = {
        "git_sha": "abc",
        "git_dirty": False,
        "python_version": "3.12.0",
        "platform": "test",
        "harness_version": "0.1.0",
        "taxonomy_version": "1.0.0",
        "pricing_table_version": "2026-08-16",
        "model_ids": {},
    }
    base.update(kwargs)
    return Provenance(**base)  # type: ignore[arg-type]


def _trace(**kwargs: object) -> Trace:
    t0 = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)
    defaults: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "trace_id": "t1",
        "scenario_id": "smoke-test",
        "backend": "langgraph",
        "status": "complete",
        "started_at": t0,
        "ended_at": t0,
        "spans": [],
        "artifacts": [],
        "cost": CostRecord(usd=None, input_tokens=None, output_tokens=None, source="unknown"),
        "provenance": _prov(),
    }
    defaults.update(kwargs)
    return Trace(**defaults)  # type: ignore[arg-type]


def test_load_pricing_version() -> None:
    table = load_pricing()
    assert table.version == "2026-08-16"
    assert "deepseek/deepseek-v3" in table.models


def test_normalize_sdk_reported_passthrough() -> None:
    trace = _trace(
        cost=CostRecord(usd=0.12, input_tokens=10, output_tokens=5, source="sdk_reported")
    )
    out = normalize_cost(trace)
    assert out.source == "sdk_reported"
    assert out.usd == 0.12


def test_normalize_provider_usage_passthrough() -> None:
    trace = _trace(
        cost=CostRecord(usd=0.05, input_tokens=100, output_tokens=20, source="provider_usage")
    )
    out = normalize_cost(trace)
    assert out.source == "provider_usage"
    assert out.usd == pytest.approx(0.05)


def test_normalize_token_estimate_langgraph() -> None:
    """LangGraph-style: total tokens on input, no usd → token_estimate with usd."""
    trace = _trace(
        backend="langgraph",
        cost=CostRecord(
            usd=None, input_tokens=1_000_000, output_tokens=None, source="token_estimate"
        ),
        provenance=_prov(model_ids={"fullstack_developer": "deepseek/deepseek-v3"}),
    )
    out = normalize_cost(trace)
    assert out.source == "token_estimate"
    assert out.usd is not None
    assert out.usd > 0
    assert out.input_tokens is not None
    assert out.output_tokens is not None
    assert out.input_tokens + out.output_tokens == 1_000_000


def test_normalize_missing_model_is_unknown_not_zero() -> None:
    trace = _trace(
        cost=CostRecord(usd=None, input_tokens=1000, output_tokens=100, source="token_estimate"),
        provenance=_prov(model_ids={"dev": "totally-unknown-model-xyz"}),
    )
    out = normalize_cost(trace)
    assert out.source == "unknown"
    assert out.usd is None  # never silently zero


def test_normalize_no_tokens_unknown() -> None:
    trace = _trace(
        cost=CostRecord(usd=None, input_tokens=None, output_tokens=None, source="unknown")
    )
    out = normalize_cost(trace)
    assert out.source == "unknown"
    assert out.usd is None


def test_budget_ledger_aborts_exactly_at_ceiling() -> None:
    ledger = BudgetLedger(ceiling_usd=0.01)
    ledger.record(CostRecord(usd=0.006, input_tokens=1, output_tokens=1, source="sdk_reported"))
    assert not ledger.aborted
    assert not ledger.crossed()
    ledger.record(CostRecord(usd=0.004, input_tokens=1, output_tokens=1, source="sdk_reported"))
    assert ledger.crossed()
    assert ledger.aborted
    assert ledger.spent_usd == pytest.approx(0.01)


def test_budget_ledger_not_singleton() -> None:
    a = BudgetLedger(ceiling_usd=1.0)
    b = BudgetLedger(ceiling_usd=2.0)
    a.record(CostRecord(usd=0.5, input_tokens=None, output_tokens=None, source="sdk_reported"))
    assert a.spent_usd == 0.5
    assert b.spent_usd == 0.0


def test_project_suite_cost_smoke() -> None:
    total = project_suite_cost(
        scenario_ids=["smoke-test"],
        backends=["crewai", "langgraph"],
        k=3,
    )
    assert total == pytest.approx(0.04 * 2 * 3)


def test_project_run_cost_fallback(tmp_path: Path) -> None:
    store = TraceStore(root=tmp_path / "traces")
    usd = project_run_cost("todo-api-beginner", store=store)
    assert usd == pytest.approx(0.25)
