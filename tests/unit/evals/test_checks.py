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
