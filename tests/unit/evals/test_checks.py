"""Per-check fail / pass / not_applicable tests against fixture traces (3.3–3.5)."""

from __future__ import annotations

import pytest

from evals.checks.registry import get_check
from tests.unit.evals.trace_fixtures import ALL_CHECK_IDS, dump_all_fixtures, load_fixture

pytestmark = pytest.mark.eval_unit


@pytest.fixture(scope="module", autouse=True)
def _ensure_fixture_files() -> None:
    dump_all_fixtures()


@pytest.mark.parametrize("check_id", ALL_CHECK_IDS)
@pytest.mark.parametrize(
    ("outcome", "expected"),
    [("fail", "fail"), ("pass", "pass"), ("na", "not_applicable")],
)
def test_check_fixture_outcome(check_id: str, outcome: str, expected: str) -> None:
    chk = get_check(check_id)
    assert chk is not None, f"check not registered: {check_id}"
    trace = load_fixture(check_id, outcome)  # type: ignore[arg-type]
    result = chk.run(trace)
    assert result.outcome == expected, (
        f"{check_id} {outcome}: got {result.outcome} "
        f"evidence={result.evidence_text!r} detail={result.detail!r}"
    )
    assert result.check_id == check_id
    assert result.trace_id == trace.trace_id


def test_metric_agreement_prefers_receipt() -> None:
    from evals.checks.registry import get_check
    from tests.unit.evals.trace_fixtures import load_fixture

    chk = get_check("CHK-metric-source-agreement")
    assert chk is not None
    trace = load_fixture("CHK-metric-source-agreement", "pass").model_copy(deep=True)
    # Events lie; receipt matches artifacts.
    n_files = len(trace.files())
    trace.raw_result = {
        **trace.raw_result,
        "event_metrics": {"file_count": 999, "cost_usd": trace.cost.usd},
        "receipt": {"file_count": 999, "cost_usd": trace.cost.usd},
    }
    _ = n_files
    result = chk.run(trace)
    assert result.outcome == "pass", result.evidence_text


def test_crewai_complete_without_smoke_fails() -> None:
    from evals.checks.registry import get_check
    from tests.unit.evals.trace_fixtures import load_fixture

    chk = get_check("CHK-runtime-smoke-present")
    assert chk is not None
    trace = load_fixture("CHK-runtime-smoke-present", "fail")
    assert trace.backend == "crewai"
    assert chk.run(trace).outcome == "fail"
