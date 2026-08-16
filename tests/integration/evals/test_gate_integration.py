"""Integration: gate rows + exit codes (R16.2 / R12.2)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from evals.aggregate import SuiteCost, SuiteLatency, assemble_suite_report
from evals.checks.base import CheckResult
from evals.gate import Baseline, accept_baseline, evaluate_gate, load_baseline
from evals.provenance import Provenance

pytestmark = [pytest.mark.integration, pytest.mark.eval_unit]

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


def _report(**kwargs: object):
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
    return assemble_suite_report(
        run_id="gate_integ",
        tier="A",
        check_results=list(check_results),  # type: ignore[arg-type]
        provenance=_PROV,
        cell_outcomes={("crewai", "smoke-test"): [True, True, True]},
        cost=SuiteCost(total_usd=0.0, ceiling_usd=5.0),
        latency=SuiteLatency(p95_s=1.0, n=1),
        generated_at=datetime(2026, 8, 16, tzinfo=UTC),
    )


def test_gate_exit_codes_pass_regress_and_dirty_refuse(tmp_path: Path) -> None:
    baseline_report = _report()
    accept_baseline(
        baseline_report,
        reason="integ baseline",
        baselines_dir=tmp_path,
        provenance=_PROV,
    )
    baseline = load_baseline("A", baselines_dir=tmp_path)
    assert isinstance(baseline, Baseline)

    d0 = evaluate_gate(baseline_report, baseline)
    assert d0.exit_code == 0
    assert d0.passed

    regress = _report(
        check_results=[
            CheckResult(
                check_id="CHK-tool-call-emitted",
                failure_mode_id="FM-001",
                trace_id="t-fail",
                outcome="fail",
                evidence_span_ids=["span_0000"],
                evidence_text="omission",
            )
        ]
    )
    d1 = evaluate_gate(regress, baseline)
    assert d1.exit_code == 1
    assert not d1.passed
    assert d1.regressions

    with pytest.raises(RuntimeError, match="dirty"):
        accept_baseline(
            baseline_report,
            reason="nope",
            baselines_dir=tmp_path / "dirty",
            provenance=_PROV.model_copy(update={"git_dirty": True}),
        )
