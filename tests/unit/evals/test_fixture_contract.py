"""
Regression: the Tier A gate must be able to fail.

Found on 2026-09-17 (`course/testing/runs/2026-09-17-stranger-3`, R12). A tester doing the
course's week 5 build track deleted a passing fixture and re-ran `evals.cli run --tier A`.
The gate exited 0. Investigation showed why: `evals/baselines/tier_a.json` stored one
collapsed outcome per check, and because the corpus carries a deliberate failing fixture for
every check, `baseline accept` had recorded `"fail"` for all twenty. The gate's only
deterministic-check rule is `baseline == "pass" and "fail" in current`, so the branch was
dead across the whole suite.

The fix does not adjust the baseline. It stops asking a baseline a question it cannot answer:
a fixture named `CHK-x__pass__fixture` *declares* what it should do, so the gate compares the
corpus with its own specification instead of with its own past.
"""

from __future__ import annotations

import pytest

from evals.aggregate import SuiteReport
from evals.checks.base import CheckResult
from evals.fixture_contract import (
    REQUIRED_OUTCOMES,
    ContractViolation,
    evaluate_fixture_contract,
    parse_expectation,
)
from evals.gate import Baseline, evaluate_gate

NOW = "2026-09-17T00:00:00Z"


def _result(check_id: str, trace_id: str, outcome: str) -> CheckResult:
    return CheckResult(check_id=check_id, failure_mode_id=None, trace_id=trace_id, outcome=outcome)


def _fixture_id(check_id: str, outcome: str) -> str:
    return f"{check_id}__{outcome}__fixture"


def _healthy_results(check_ids: tuple[str, ...] = ("CHK-a", "CHK-b")) -> list[CheckResult]:
    """Every check, over every fixture: its own three plus abstentions on the others."""
    want = {"pass": "pass", "fail": "fail", "na": "not_applicable"}
    traces = [(c, o) for c in check_ids for o in REQUIRED_OUTCOMES]
    out: list[CheckResult] = []
    for owner, outcome in traces:
        tid = _fixture_id(owner, outcome)
        for runner in check_ids:
            out.append(_result(runner, tid, want[outcome] if runner == owner else "not_applicable"))
    return out


def _report(results: list[CheckResult]) -> SuiteReport:
    from evals.provenance import collect

    return SuiteReport(
        run_id="t",
        tier="A",
        generated_at=NOW,
        check_results=results,
        provenance=collect(tier="A"),
    )


def _baseline() -> Baseline:
    return Baseline(
        tier="A",
        accepted_at=NOW,
        git_sha="deadbeef",
        reason="test",
        check_outcomes={"CHK-a": "fail", "CHK-b": "fail"},  # the real, useless shape
        suite_pass_pow_k=0.0,
    )


def _kinds(violations: list[ContractViolation]) -> list[str]:
    return sorted({v.kind for v in violations})


class TestParseExpectation:
    def test_reads_check_and_outcome(self) -> None:
        assert parse_expectation("CHK-draft-commit__pass__fixture") == ("CHK-draft-commit", "pass")

    @pytest.mark.parametrize(
        "trace_id",
        [
            "coverage__crewai__killed",  # the backend/status fixtures carry no expectation
            "2026-09-17_run_01",  # a real run
            "CHK-x__bogus__fixture",  # not one of the three outcomes
            "__pass__fixture",  # no check id
        ],
    )
    def test_traces_without_an_expectation_are_exempt(self, trace_id: str) -> None:
        assert parse_expectation(trace_id) is None


class TestHealthyCorpus:
    def test_a_correct_corpus_has_no_violations(self) -> None:
        assert evaluate_fixture_contract(_healthy_results()) == []

    def test_a_correct_corpus_passes_the_gate(self) -> None:
        d = evaluate_gate(_report(_healthy_results()), _baseline())
        assert d.passed and d.exit_code == 0


class TestExpectation:
    def test_check_failing_its_own_pass_fixture_is_a_regression(self) -> None:
        results = _healthy_results()
        for r in results:
            if r.check_id == "CHK-a" and r.trace_id == _fixture_id("CHK-a", "pass"):
                r.outcome = "fail"
        violations = evaluate_fixture_contract(results)
        assert _kinds(violations) == ["expectation"]
        assert violations[0].expected == "pass" and violations[0].actual == "fail"
        assert not evaluate_gate(_report(results), _baseline()).passed

    def test_check_passing_its_own_fail_fixture_is_a_regression(self) -> None:
        """The blind-check direction, which a pass→fail rule can never see."""
        results = _healthy_results()
        for r in results:
            if r.check_id == "CHK-a" and r.trace_id == _fixture_id("CHK-a", "fail"):
                r.outcome = "pass"
        assert _kinds(evaluate_fixture_contract(results)) == ["expectation"]
        assert not evaluate_gate(_report(results), _baseline()).passed

    def test_an_inverted_check_is_caught(self) -> None:
        """Swapping pass and fail keeps every count identical — counts would miss this."""
        results = _healthy_results()
        for r in results:
            if r.check_id != "CHK-a":
                continue
            if r.trace_id == _fixture_id("CHK-a", "pass"):
                r.outcome = "fail"
            elif r.trace_id == _fixture_id("CHK-a", "fail"):
                r.outcome = "pass"
        violations = evaluate_fixture_contract(results)
        assert len(violations) == 2
        assert not evaluate_gate(_report(results), _baseline()).passed

    def test_another_checks_result_on_this_fixture_is_not_constrained(self) -> None:
        """A fixture speaks only for the check it was built for."""
        results = _healthy_results()
        for r in results:
            if r.check_id == "CHK-b" and r.trace_id == _fixture_id("CHK-a", "pass"):
                r.outcome = "fail"
        assert evaluate_fixture_contract(results) == []


class TestCompleteness:
    def test_deleting_a_pass_fixture_fails_the_gate(self) -> None:
        """The exact R12 scenario: on 2026-09-17 this exited 0."""
        gone = _fixture_id("CHK-a", "pass")
        results = [r for r in _healthy_results() if r.trace_id != gone]

        violations = evaluate_fixture_contract(results)
        assert _kinds(violations) == ["completeness"]
        assert violations[0].check_id == "CHK-a"
        assert "pass" in violations[0].message

        decision = evaluate_gate(_report(results), _baseline())
        assert not decision.passed
        assert decision.exit_code == 1

    def test_a_check_with_no_fixtures_at_all_is_caught(self) -> None:
        """The half-wired new check from week 5's build track."""
        results = [
            *_healthy_results(),
            _result("CHK-new", _fixture_id("CHK-a", "pass"), "not_applicable"),
        ]
        violations = [v for v in evaluate_fixture_contract(results) if v.check_id == "CHK-new"]
        assert len(violations) == 1
        assert violations[0].actual == "none"


class TestUniqueness:
    def test_a_duplicated_trace_warns_but_does_not_fail(self) -> None:
        """Deleting someone's committed fixtures is a human decision, not the gate's."""
        results = _healthy_results()
        dupe = _fixture_id("CHK-a", "pass")
        results += [r.model_copy() for r in results if r.trace_id == dupe]

        violations = evaluate_fixture_contract(results)
        assert _kinds(violations) == ["uniqueness"]
        assert not violations[0].gating

        decision = evaluate_gate(_report(results), _baseline())
        assert decision.passed
        assert any(w.metric.startswith("fixture:uniqueness") for w in decision.warnings)


class TestGroundTruthNeedsNoBaseline:
    def test_contract_still_fails_with_no_baseline_on_disk(self) -> None:
        gone = _fixture_id("CHK-a", "pass")
        results = [r for r in _healthy_results() if r.trace_id != gone]
        decision = evaluate_gate(_report(results), None)
        assert not decision.passed
        assert decision.exit_code == 1

    def test_no_baseline_is_still_only_advisory_for_drift(self) -> None:
        decision = evaluate_gate(_report(_healthy_results()), None)
        assert decision.passed
        assert any("advisory" in w.message for w in decision.warnings)


class TestTheCommittedCorpus:
    """The guard that keeps this true, run against the real fixtures on every commit."""

    @staticmethod
    def _real_results() -> list[CheckResult]:
        import json
        from pathlib import Path

        from evals.checks import all_checks, ensure_checks_loaded
        from evals.trace.models import Trace

        ensure_checks_loaded()
        traces_dir = Path(__file__).resolve().parents[3] / "evals" / "fixtures" / "traces"
        traces = [
            Trace.model_validate(json.loads(p.read_text(encoding="utf-8")))
            for p in sorted(traces_dir.glob("*.json"))
        ]
        return [c.run(t) for t in traces for c in all_checks(tier="A")]

    def test_every_check_honours_its_own_fixtures(self) -> None:
        bad = [
            v for v in evaluate_fixture_contract(self._real_results()) if v.kind == "expectation"
        ]
        assert not bad, "\n".join(v.message for v in bad)

    def test_every_check_has_all_three_fixtures(self) -> None:
        bad = [
            v for v in evaluate_fixture_contract(self._real_results()) if v.kind == "completeness"
        ]
        assert not bad, "\n".join(v.message for v in bad)


class TestScopeOfCompleteness:
    def test_a_live_corpus_report_owes_no_fixtures(self) -> None:
        """A real run is not replaying the corpus, so it has nothing to be complete about."""
        results = [
            _result("CHK-a", "2026-09-17_run_01", "pass"),
            _result("CHK-b", "2026-09-17_run_01", "not_applicable"),
        ]
        assert evaluate_fixture_contract(results) == []
        assert evaluate_gate(_report(results), _baseline()).passed
