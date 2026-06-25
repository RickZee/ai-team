"""
CrewAI eval using crewai.experimental.evaluation.

Run:
    AI_TEAM_USE_REAL_LLM=1 uv run pytest evals/backends/test_crewai_eval.py -v -s

Requires OPENROUTER_API_KEY.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from evals.fixtures import (
    EvalResult,
    eval_result_from_run,
    load_scenario,
    run_pytest_in_workspace,
)
from evals.metrics import compute_metrics, format_scorecard

pytestmark = pytest.mark.skipif(
    not os.environ.get("AI_TEAM_USE_REAL_LLM"),
    reason="Set AI_TEAM_USE_REAL_LLM=1 to run real-LLM evals",
)

SCENARIO = load_scenario("smoke-test")
BACKEND = "crewai"


@pytest.fixture(scope="module")
def crewai_result(tmp_path_factory) -> tuple[EvalResult, Path]:
    from ai_team.backends.registry import get_backend
    from ai_team.core.team_profile import load_team_profile

    ws = tmp_path_factory.mktemp("crewai_workspace")
    backend = get_backend(BACKEND)
    profile = load_team_profile("prototype")

    t0 = time.time()
    raw = backend.run(
        SCENARIO["description"],
        profile,
        env="dev",
        skip_estimate=True,
        workspace_dir=str(ws),
    )
    wall = time.time() - t0

    result = eval_result_from_run(
        BACKEND, SCENARIO["id"], {**raw.raw, "success": raw.success}, workspace_dir=ws, wall_time_s=wall
    )
    compute_metrics(result, SCENARIO, run_judge=True)
    print("\n" + format_scorecard(result))
    return result, ws


# ---------------------------------------------------------------------------
# Task success
# ---------------------------------------------------------------------------

class TestCrewAITaskSuccess:
    def test_completes_successfully(self, crewai_result):
        result, _ = crewai_result
        assert result.success, f"Run failed: {result.error}"

    def test_required_files_exist(self, crewai_result):
        result, ws = crewai_result
        for expected in SCENARIO["expected"]["files"]:
            hits = list(ws.rglob(f"*{expected}")) + list(ws.rglob(expected))
            assert hits, f"Required file not found: {expected}"

    def test_has_test_file(self, crewai_result):
        result, ws = crewai_result
        test_files = list(ws.rglob("test_*.py")) + list(ws.rglob("*_test.py"))
        assert test_files, "No pytest test file found in workspace"

    def test_pytest_passes_in_workspace(self, crewai_result):
        _, ws = crewai_result
        out = run_pytest_in_workspace(ws)
        assert out["ok"], f"Tests failed:\n{out['output']}"

    def test_pass_rate_meets_threshold(self, crewai_result):
        _, ws = crewai_result
        out = run_pytest_in_workspace(ws)
        min_rate = SCENARIO["expected"]["test_pass_rate_min"]
        assert out["pass_rate"] >= min_rate, (
            f"Pass rate {out['pass_rate']:.0%} < {min_rate:.0%}"
        )


# ---------------------------------------------------------------------------
# Quality — crewai.experimental.evaluation
# ---------------------------------------------------------------------------

class TestCrewAIExperimentalEval:
    """Use CrewAI's built-in evaluators on the agent trajectory captured during run."""

    def test_goal_alignment_via_llm_judge(self, crewai_result):
        result, ws = crewai_result
        m = result.metrics
        score = m.get("goal_alignment")
        if score is None:
            pytest.skip("LLM judge did not run")
        assert score >= 0.6, f"Goal alignment {score:.2f} < 0.6"

    def test_acceptance_criteria_met(self, crewai_result):
        result, ws = crewai_result
        scores = result.judge_scores
        if not scores:
            pytest.skip("LLM judge did not run")
        for criterion, score in scores.items():
            assert score >= 0.5, f"Criterion failed ({score:.2f}): {criterion}"

    def test_no_hallucinations(self, crewai_result):
        result, ws = crewai_result
        count = result.metrics.get("hallucination_count", 0)
        assert count == 0, f"{count} hallucination patterns found in workspace"


# ---------------------------------------------------------------------------
# Cost & latency
# ---------------------------------------------------------------------------

class TestCrewAICostLatency:
    def test_within_budget(self, crewai_result):
        result, _ = crewai_result
        if result.cost_usd is None:
            pytest.skip("Cost not reported by backend")
        assert result.cost_usd <= SCENARIO["budget_usd_max"], (
            f"Cost ${result.cost_usd:.4f} > budget ${SCENARIO['budget_usd_max']}"
        )

    def test_completes_within_timeout(self, crewai_result):
        result, _ = crewai_result
        if result.wall_time_s is None:
            pytest.skip("Wall time not recorded")
        assert result.wall_time_s <= SCENARIO["timeout_seconds"], (
            f"Timed out: {result.wall_time_s:.1f}s > {SCENARIO['timeout_seconds']}s"
        )


# ---------------------------------------------------------------------------
# Trajectory
# ---------------------------------------------------------------------------

class TestCrewAITrajectory:
    def test_retry_count_bounded(self, crewai_result):
        result, _ = crewai_result
        assert result.retry_count <= 2, f"Too many retries: {result.retry_count}"

    def test_guardrail_false_positives_zero(self, crewai_result):
        result, _ = crewai_result
        # guardrail_fail_count > 0 is fine if run still succeeds (retry resolved it)
        # A false-positive that killed a valid run would show as success=False
        if not result.success:
            fails = result.metrics.get("guardrail_fail_count", 0)
            assert fails == 0, f"Guardrail falsely blocked a valid run ({fails} fails)"
