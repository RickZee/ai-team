"""Mutation sensitivity: passing fixtures flipped to fail (task 3.6 / design §7.2)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from evals.checks.registry import get_check
from evals.trace.models import Span
from tests.unit.evals.trace_fixtures import ALL_CHECK_IDS, load_fixture

pytestmark = pytest.mark.eval_unit


def _mutate(check_id: str):
    """Return a mutated copy of the passing fixture that should fail the check."""
    trace = load_fixture(check_id, "pass").model_copy(deep=True)

    if check_id == "CHK-tool-call-emitted":
        trace.spans = [s for s in trace.spans if s.type != "tool_use"]
        trace.artifacts = []
        for s in trace.spans:
            if s.type == "phase_end":
                s.payload["output"] = "```python\nx=1\n```"
        return trace

    if check_id == "CHK-phase-repeat-bounded":
        base = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)
        extras = [
            Span(
                span_id=f"span_m{i:02d}",
                type="phase_start",
                t_start=base + timedelta(seconds=10 + i),
                t_end=base + timedelta(seconds=10 + i),
                phase="development",
                agent_role="fullstack_developer",
            )
            for i in range(5)
        ]
        trace.spans = list(trace.spans) + extras
        return trace

    if check_id == "CHK-listener-self-trigger":
        trace.raw_result = {**trace.raw_result, "listener_self_triggers": ["retry_development"]}
        return trace

    if check_id == "CHK-interrupt-latency":
        for s in trace.spans:
            if s.type == "human_interrupt":
                s.payload["surfaced_at"] = "2026-08-01T14:00:00+00:00"
        return trace

    if check_id == "CHK-workspace-isolation":
        trace.raw_result = {
            **trace.raw_result,
            "suite_workspace_dirs": ["/tmp/same", "/tmp/same"],
        }
        trace.workspace_dir = "/tmp/same"
        return trace

    if check_id == "CHK-guardrail-fp-budget":
        for s in trace.spans:
            if s.type == "guardrail_check":
                s.payload["outcome"] = "fail"
        return trace

    if check_id == "CHK-runtime-smoke-present":
        trace.spans = [s for s in trace.spans if s.type != "smoke_probe"]
        return trace

    if check_id == "CHK-spend-ceiling":
        trace.cost.usd = 99.0
        trace.raw_result = {**trace.raw_result, "scenario": {"budget_usd_max": 0.5}}
        return trace

    if check_id == "CHK-metric-source-agreement":
        trace.raw_result = {
            **trace.raw_result,
            "event_metrics": {"file_count": 0, "cost_usd": trace.cost.usd},
        }
        return trace

    if check_id == "CHK-provider-error-rate":
        base = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)
        trace.spans = list(trace.spans) + [
            Span(
                span_id="span_err",
                type="error",
                t_start=base,
                t_end=base,
                payload={"status_code": 400, "message": "provider dialect"},
            )
        ]
        return trace

    if check_id == "CHK-gate-env-fidelity":
        for s in trace.spans:
            if s.type == "error":
                s.payload["message"] = "ModuleNotFoundError: No module named 'flask_sqlalchemy'"
        trace.raw_result = {
            **trace.raw_result,
            "requirements_txt": "flask_sqlalchemy==3.1\n",
        }
        return trace

    if check_id == "CHK-required-artifacts":
        trace.artifacts = []
        return trace

    if check_id == "CHK-hallucination-density":
        trace.raw_result = {
            **trace.raw_result,
            "hallucination_count": 3,
            "max_hallucinations": 0,
        }
        return trace

    raise AssertionError(f"no mutation defined for {check_id}")


@pytest.mark.parametrize("check_id", ALL_CHECK_IDS)
def test_mutation_flips_pass_to_fail(check_id: str) -> None:
    chk = get_check(check_id)
    assert chk is not None
    passing = load_fixture(check_id, "pass")
    assert chk.run(passing).outcome == "pass"
    mutated = _mutate(check_id)
    result = chk.run(mutated)
    assert (
        result.outcome == "fail"
    ), f"{check_id} mutation did not fail: {result.outcome} {result.evidence_text}"
