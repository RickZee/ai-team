"""Gate evaluation against the R12.2 table."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from evals.aggregate import (
    GuardrailMetricRow,
    JudgeAlignmentSummary,
    SuiteCost,
    SuiteLatency,
    SuiteReport,
    assemble_suite_report,
    make_rate,
)
from evals.checks.base import CheckResult
from evals.gate import Baseline, accept_baseline, evaluate_gate
from evals.provenance import Provenance

pytestmark = pytest.mark.eval_unit

_PROV = Provenance(
    git_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    git_dirty=False,
    python_version="3.12.0",
    platform="test",
    harness_version="0.1.0",
    taxonomy_version="1.0.0",
    pricing_table_version="2026-08-16",
    tier="A",
)


def _baseline(**kwargs: object) -> Baseline:
    data: dict[str, object] = {
        "tier": "A",
        "accepted_at": datetime(2026, 8, 1, tzinfo=UTC),
        "git_sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "reason": "test",
        "check_outcomes": {"CHK-tool-call-emitted": "pass"},
        "guardrails": {"scope": {"recall": 0.95, "fpr": 0.05}},
        "judge_failure_rates": {"j1": 0.10},
        "suite_pass_pow_k": 1.0,
        "suite_cost_usd": 1.0,
        "cost_ceiling_usd": 5.0,
        "p95_latency_s": 10.0,
        "guardrail_recall_floor": 0.90,
        "guardrail_fpr_ceiling": 0.10,
    }
    data.update(kwargs)
    return Baseline.model_validate(data)


def _report(**kwargs: object) -> SuiteReport:
    check_results = kwargs.pop(
        "check_results",
        [
            CheckResult(
                check_id="CHK-tool-call-emitted",
                failure_mode_id="FM-001",
                trace_id="t1",
                outcome="pass",
            )
        ],
    )
    cell_outcomes = kwargs.pop("cell_outcomes", {("crewai", "smoke-test"): [True]})
    judges = kwargs.pop("judges", [])
    guardrails = kwargs.pop("guardrails", [])
    cost = kwargs.pop("cost", SuiteCost(total_usd=1.0, ceiling_usd=5.0))
    latency = kwargs.pop("latency", SuiteLatency(p95_s=10.0, n=1))
    return assemble_suite_report(
        run_id="gate_test",
        tier="A",
        check_results=list(check_results),  # type: ignore[arg-type]
        provenance=_PROV,
        cell_outcomes=dict(cell_outcomes),  # type: ignore[arg-type]
        judge_summaries=list(judges),  # type: ignore[arg-type]
        guardrails=list(guardrails),  # type: ignore[arg-type]
        cost=cost,  # type: ignore[arg-type]
        latency=latency,  # type: ignore[arg-type]
        generated_at=datetime(2026, 8, 16, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    ("case", "expect_exit", "bucket", "metric_substr"),
    [
        ("check_fail", 1, "regressions", "check:CHK-tool-call-emitted"),
        ("guardrail_recall", 1, "regressions", "guardrail:scope:recall"),
        ("guardrail_fpr", 1, "regressions", "guardrail:scope:fpr"),
        ("judge_rate", 1, "regressions", "judge:j1:failure_rate"),
        ("pass_pow_drop", 1, "regressions", "suite:pass_pow_k"),
        ("cost_ceiling", 1, "regressions", "suite:cost"),
        ("cost_warn", 0, "warnings", "suite:cost"),
        ("latency_warn", 0, "warnings", "suite:p95_latency"),
        ("clean", 0, None, None),
    ],
)
def test_gate_rows(
    case: str,
    expect_exit: int,
    bucket: str | None,
    metric_substr: str | None,
) -> None:
    baseline = _baseline()
    if case == "check_fail":
        report = _report(
            check_results=[
                CheckResult(
                    check_id="CHK-tool-call-emitted",
                    failure_mode_id="FM-001",
                    trace_id="t1",
                    outcome="fail",
                    evidence_span_ids=["span_9"],
                )
            ]
        )
    elif case == "guardrail_recall":
        report = _report(
            guardrails=[
                GuardrailMetricRow(name="scope", n=100, recall=0.5, fpr=0.05, provisional=False)
            ]
        )
    elif case == "guardrail_fpr":
        report = _report(
            guardrails=[
                GuardrailMetricRow(name="scope", n=100, recall=0.95, fpr=0.5, provisional=False)
            ]
        )
    elif case == "judge_rate":
        report = _report(
            judges=[
                JudgeAlignmentSummary(
                    judge_id="j1",
                    eligible_to_gate=True,
                    failure_rate=make_rate(20, 100).model_copy(update={"bias_corrected": 0.20}),
                )
            ]
        )
    elif case == "pass_pow_drop":
        report = _report(cell_outcomes={("crewai", "smoke-test"): [False]})
    elif case == "cost_ceiling":
        report = _report(cost=SuiteCost(total_usd=9.0, ceiling_usd=5.0))
    elif case == "cost_warn":
        report = _report(cost=SuiteCost(total_usd=1.30, ceiling_usd=5.0))
    elif case == "latency_warn":
        report = _report(latency=SuiteLatency(p95_s=20.0, n=1))
    else:
        report = _report()

    decision = evaluate_gate(report, baseline)
    assert decision.exit_code == expect_exit
    if bucket == "regressions":
        assert any(metric_substr in r.metric for r in decision.regressions)
    elif bucket == "warnings":
        assert any(metric_substr in w.metric for w in decision.warnings)


def test_harness_error_exit_2() -> None:
    decision = evaluate_gate(_report(), _baseline(), harness_error="cache miss")
    assert decision.exit_code == 2
    assert decision.passed is False


def test_no_baseline_advisory() -> None:
    decision = evaluate_gate(_report(), None)
    assert decision.exit_code == 0
    assert decision.warnings


def test_non_eligible_judge_suppressed_not_gated() -> None:
    report = _report(
        judges=[
            JudgeAlignmentSummary(
                judge_id="j1",
                eligible_to_gate=False,
                failure_rate=make_rate(90, 100).model_copy(update={"bias_corrected": 0.9}),
            )
        ]
    )
    decision = evaluate_gate(report, _baseline())
    assert decision.exit_code == 0
    assert any("j1" in s for s in decision.suppressed)
    assert not any(r.metric.startswith("judge:j1") for r in decision.regressions)


def test_provisional_guardrail_excluded() -> None:
    report = _report(
        guardrails=[GuardrailMetricRow(name="scope", n=3, recall=0.1, fpr=0.9, provisional=True)]
    )
    decision = evaluate_gate(report, _baseline())
    assert decision.exit_code == 0
    assert any("provisional" in s for s in decision.suppressed)


def test_accept_refuses_dirty(tmp_path: Path) -> None:
    report = _report()
    dirty = _PROV.model_copy(update={"git_dirty": True})
    with pytest.raises(RuntimeError, match="dirty"):
        accept_baseline(
            report,
            reason="nope",
            baselines_dir=tmp_path,
            provenance=dirty,
        )
    path = accept_baseline(
        report,
        reason="initial",
        baselines_dir=tmp_path,
        provenance=_PROV,
    )
    assert path.is_file()


def test_gate_decision_summary_markdown() -> None:
    decision = evaluate_gate(
        _report(
            check_results=[
                CheckResult(
                    check_id="CHK-tool-call-emitted",
                    failure_mode_id="FM-001",
                    trace_id="t1",
                    outcome="fail",
                    evidence_span_ids=["s0"],
                )
            ]
        ),
        _baseline(),
    )
    md = decision.summary_markdown()
    assert "Regressions" in md
    assert "CHK-tool-call-emitted" in md
