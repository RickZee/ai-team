"""Unit coverage for `evals/metrics.py` — the module that produces published numbers.

`compute_metrics` feeds `docs/COMPARISON_RESULTS.md` and every scorecard in the repo,
and it was the least-covered module in `evals/` (18% line). The branches that matter
here are not the arithmetic but the *guards*: division by zero, absent data reported as
`None` rather than `0`, and the `judge_provisional` flag that marks a single-vendor
judge's scores as unfalsifiable.

Every test below is a claim about a number that could end up in a post.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from evals.fixtures import EvalResult
from evals.metrics import _extract_total_tokens, compute_metrics, format_scorecard


def _scenario(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "description": "build a todo api",
        "budget_usd_max": 1.00,
        "expected": {"files": [], "test_files": [], "acceptance_criteria": []},
    }
    base.update(over)
    return base


def _result(**over: Any) -> EvalResult:
    base: dict[str, Any] = {
        "backend": "crewai",
        "scenario_id": "todo-api-beginner",
        "success": True,
        "current_phase": "complete",
    }
    base.update(over)
    return EvalResult(**base)


def _metrics(result: EvalResult, scenario: dict[str, Any] | None = None) -> dict[str, Any]:
    return compute_metrics(result, scenario or _scenario(), run_judge=False)


# ── Division guards ───────────────────────────────────────────────────────────


def test_pass_rate_is_none_when_no_tests_ran() -> None:
    """0 passed + 0 failed must be `None` ("we don't know"), never 0.0 ("all failed")."""
    m = _metrics(_result(test_results={"tests": {"passed": 0, "failed": 0}}))
    assert m["test_pass_rate"] is None


def test_pass_rate_is_none_when_test_results_absent() -> None:
    assert _metrics(_result(test_results={}))["test_pass_rate"] is None


def test_pass_rate_computed_from_counts() -> None:
    m = _metrics(_result(test_results={"tests": {"passed": 3, "failed": 1}}))
    assert m["test_pass_rate"] == pytest.approx(0.75)


def test_tokens_per_file_survives_zero_generated_files() -> None:
    """`max(len(files), 1)` is the guard; without it every failed run raises."""
    result = _result(
        generated_files=[],
        raw={
            "state": {"messages": [{"response_metadata": {"token_usage": {"total_tokens": 500}}}]}
        },
    )
    m = _metrics(result)
    assert m["total_tokens"] == 500
    assert m["tokens_per_file"] == pytest.approx(500.0)


def test_zero_tokens_reported_as_unknown_not_zero() -> None:
    """Documents a real edge: a run reporting 0 tokens is indistinguishable from no data.

    `_extract_total_tokens` returns `None` unless some message carried a non-zero count,
    and `tokens_per_file` then short-circuits on the falsy value. A genuinely 0-token run
    would be reported as unknown. Harmless today (no backend reports 0), but the
    behaviour should change deliberately, not by accident.
    """
    result = _result(
        raw={"state": {"messages": [{"response_metadata": {"token_usage": {"total_tokens": 0}}}]}}
    )
    m = _metrics(result)
    assert m["total_tokens"] is None
    assert m["tokens_per_file"] is None


# ── Budget ────────────────────────────────────────────────────────────────────


def test_within_budget_is_inclusive_at_the_ceiling() -> None:
    assert _metrics(_result(cost_usd=1.00))["within_budget"] is True


def test_over_budget_by_a_cent_is_false() -> None:
    assert _metrics(_result(cost_usd=1.01))["within_budget"] is False


def test_within_budget_unknown_when_cost_unreported() -> None:
    """A backend that reports no cost must not be credited with staying in budget."""
    assert _metrics(_result(cost_usd=None))["within_budget"] is None


# ── Artifact expectations ─────────────────────────────────────────────────────


def test_required_files_none_when_scenario_expects_none() -> None:
    assert _metrics(_result())["required_files_present"] is None


def test_required_files_matched_by_suffix() -> None:
    scenario = _scenario(
        expected={"files": ["app.py"], "test_files": [], "acceptance_criteria": []}
    )
    m = compute_metrics(_result(generated_files=["src/app.py"]), scenario, run_judge=False)
    assert m["required_files_present"] is True


def test_required_files_false_when_one_is_missing() -> None:
    scenario = _scenario(
        expected={"files": ["app.py", "models.py"], "test_files": [], "acceptance_criteria": []}
    )
    m = compute_metrics(_result(generated_files=["src/app.py"]), scenario, run_judge=False)
    assert m["required_files_present"] is False


def test_test_file_detection_defaults_to_test_prefix() -> None:
    """With no `test_files` patterns the default is the `test_` prefix, not "anything"."""
    assert _metrics(_result(generated_files=["tests/test_app.py"]))["test_file_present"] is True
    assert _metrics(_result(generated_files=["src/app.py"]))["test_file_present"] is False


def test_workspace_files_count_toward_expectations(tmp_path: Path) -> None:
    """Files on disk count even when the backend forgot to list them (FM-012 territory)."""
    (tmp_path / "app.py").write_text("x = 1\n")
    scenario = _scenario(
        expected={"files": ["app.py"], "test_files": [], "acceptance_criteria": []}
    )
    m = compute_metrics(
        _result(generated_files=[], workspace_dir=tmp_path), scenario, run_judge=False
    )
    assert m["required_files_present"] is True


def test_hallucination_count_unknown_without_a_workspace() -> None:
    assert _metrics(_result(workspace_dir=None))["hallucination_count"] is None


# ── Trajectory ────────────────────────────────────────────────────────────────


def test_guardrail_fail_and_warn_counted_separately() -> None:
    result = _result(
        guardrail_checks=[
            {"status": "fail"},
            {"status": "fail"},
            {"status": "warn"},
            {"status": "pass"},
            {},
        ]
    )
    m = _metrics(result)
    assert m["guardrail_fail_count"] == 2
    assert m["guardrail_warn_count"] == 1


def test_phase_count_reflects_history_length() -> None:
    m = _metrics(_result(phase_history=[{"phase": "plan"}, {"phase": "build"}], retry_count=3))
    assert m["phase_count"] == 2
    assert m["retry_count"] == 3


# ── Token extraction ──────────────────────────────────────────────────────────


def test_extract_tokens_sums_response_metadata() -> None:
    state = {
        "messages": [
            {"response_metadata": {"token_usage": {"total_tokens": 100}}},
            {"response_metadata": {"token_usage": {"total_tokens": 250}}},
        ]
    }
    assert _extract_total_tokens(state) == 350


def test_extract_tokens_falls_back_to_usage_metadata() -> None:
    assert _extract_total_tokens({"messages": [{"usage_metadata": {"total_tokens": 42}}]}) == 42


def test_extract_tokens_skips_non_dict_messages() -> None:
    state = {"messages": ["a string", None, {"usage_metadata": {"total_tokens": 7}}]}
    assert _extract_total_tokens(state) == 7


def test_extract_tokens_none_when_nothing_reported() -> None:
    assert _extract_total_tokens({}) is None
    assert _extract_total_tokens({"messages": []}) is None
    assert _extract_total_tokens({"messages": [{"response_metadata": {}}]}) is None


# ── Judge gating and the provisional flag ─────────────────────────────────────


class _StubJudge:
    """Minimal judge double — no network, deterministic verdicts."""

    def __init__(self, *, single_vendor: bool) -> None:
        self.identity = "stub/judge-1"
        self.is_single_vendor = single_vendor

    def check_all_criteria(self, criteria: list[str], evidence: str) -> dict[str, Any]:
        class _V:
            score = 0.8

        return {c: _V() for c in criteria}

    def score_goal_alignment(self, description: str, evidence: str) -> float:
        return 0.9


@pytest.fixture
def _no_workspace_io(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("evals.metrics.summarize_workspace", lambda ws: "## files\napp.py\n")
    monkeypatch.setattr("evals.metrics.count_hallucinations", lambda ws: 0)
    monkeypatch.setattr(
        "evals.metrics.run_pytest_in_workspace",
        lambda ws: {"returncode": 0, "passed": 1, "failed": 0, "output": "ok"},
    )


def test_judge_skipped_when_run_did_not_succeed(tmp_path: Path, _no_workspace_io: None) -> None:
    """A failed run gets no judge scores — grading a crash is not a measurement."""
    m = compute_metrics(
        _result(success=False, workspace_dir=tmp_path),
        _scenario(),
        judge=_StubJudge(single_vendor=False),
        run_judge=True,
    )
    assert m["acceptance_criteria_scores"] == {}
    assert m["goal_alignment"] is None
    assert m["judge_provisional"] is None


def test_judge_suppressed_by_env_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_workspace_io: None
) -> None:
    monkeypatch.setenv("EVAL_NO_JUDGE", "1")
    m = compute_metrics(
        _result(workspace_dir=tmp_path),
        _scenario(),
        judge=_StubJudge(single_vendor=False),
        run_judge=True,
    )
    assert m["judge_identity"] is None
    assert m["acceptance_criteria_mean"] is None


def test_single_vendor_judge_marks_scores_provisional(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_workspace_io: None
) -> None:
    """The honesty flag: a judge sharing a vendor with a backend cannot rule out
    self-preference, so its scores must be labelled provisional."""
    monkeypatch.delenv("EVAL_NO_JUDGE", raising=False)
    scenario = _scenario(
        expected={"files": [], "test_files": [], "acceptance_criteria": ["has tests", "has README"]}
    )
    m = compute_metrics(
        _result(workspace_dir=tmp_path),
        scenario,
        judge=_StubJudge(single_vendor=True),
        run_judge=True,
    )
    assert m["judge_provisional"] is True
    assert m["judge_single_vendor"] is True
    assert m["judge_identity"] == "stub/judge-1"
    assert m["acceptance_criteria_mean"] == pytest.approx(0.8)
    assert m["goal_alignment"] == pytest.approx(0.9)


def test_multi_vendor_judge_is_not_provisional(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_workspace_io: None
) -> None:
    monkeypatch.delenv("EVAL_NO_JUDGE", raising=False)
    m = compute_metrics(
        _result(workspace_dir=tmp_path),
        _scenario(),
        judge=_StubJudge(single_vendor=False),
        run_judge=True,
    )
    assert m["judge_provisional"] is False


def test_acceptance_mean_is_none_with_no_criteria(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_workspace_io: None
) -> None:
    """An empty criteria list must not average to 0.0 and read as a failing grade."""
    monkeypatch.delenv("EVAL_NO_JUDGE", raising=False)
    m = compute_metrics(
        _result(workspace_dir=tmp_path),
        _scenario(),
        judge=_StubJudge(single_vendor=True),
        run_judge=True,
    )
    assert m["acceptance_criteria_scores"] == {}
    assert m["acceptance_criteria_mean"] is None


# ── Scorecard rendering ───────────────────────────────────────────────────────


def test_scorecard_renders_unknowns_as_na() -> None:
    """Missing numbers must print `n/a`, never a misleading 0."""
    result = _result(cost_usd=None, wall_time_s=None)
    _metrics(result)
    card = format_scorecard(result)
    assert "n/a" in card
    assert "Backend: crewai" in card
    assert "0.00" not in card.split("── Cost")[1].split("── LLM")[0]


def test_scorecard_lists_each_judged_criterion() -> None:
    result = _result(cost_usd=0.25, wall_time_s=12.5)
    _metrics(result)
    result.judge_scores = {"has tests": 0.9, "has README": 0.4}
    card = format_scorecard(result)
    assert "[0.90] has tests" in card
    assert "[0.40] has README" in card
    assert "$0.2500" in card
    assert "12.5s" in card
