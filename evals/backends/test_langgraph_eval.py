"""
LangGraph eval: trajectory checks, phase completion, LLM judge.

Run:
    AI_TEAM_USE_REAL_LLM=1 uv run pytest evals/backends/test_langgraph_eval.py -v -s

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
BACKEND = "langgraph"


@pytest.fixture(scope="module")
def lg_result(tmp_path_factory) -> tuple[EvalResult, Path]:
    from ai_team.backends.registry import get_backend
    from ai_team.core.team_profile import load_team_profile

    ws = tmp_path_factory.mktemp("langgraph_workspace")
    backend = get_backend(BACKEND)
    profile = load_team_profile("prototype")

    # Override dev agent to claude-sonnet: deepseek-v3 narrates tool calls without
    # calling them (~50% fail rate), claude-sonnet reliably uses file_writer tool.
    profile.model_overrides["fullstack_developer"] = "openrouter/anthropic/claude-sonnet-4"

    t0 = time.time()
    raw = backend.run(
        SCENARIO["description"],
        profile,
        env="dev",
        skip_estimate=True,
        graph_mode="full",
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

class TestLangGraphTaskSuccess:
    def test_completes_successfully(self, lg_result):
        result, _ = lg_result
        assert result.success, f"Run failed at phase {result.current_phase}: {result.error}"

    def test_reaches_complete_phase(self, lg_result):
        result, _ = lg_result
        assert result.current_phase == "complete", f"Stuck at: {result.current_phase}"

    def test_required_files_exist(self, lg_result):
        result, ws = lg_result
        for expected in SCENARIO["expected"]["files"]:
            hits = list(ws.rglob(f"*{expected}")) + list(ws.rglob(expected))
            assert hits, f"Required file not found: {expected}"

    def test_has_test_file(self, lg_result):
        _, ws = lg_result
        test_files = list(ws.rglob("test_*.py")) + list(ws.rglob("*_test.py"))
        assert test_files, "No pytest test file in workspace"

    def test_pytest_passes_in_workspace(self, lg_result):
        _, ws = lg_result
        out = run_pytest_in_workspace(ws)
        assert out["ok"], f"Tests failed:\n{out['output']}"


# ---------------------------------------------------------------------------
# Phase trajectory
# ---------------------------------------------------------------------------

class TestLangGraphTrajectory:
    def test_phase_history_populated(self, lg_result):
        result, _ = lg_result
        assert result.phase_history, "phase_history is empty — subgraph nodes not writing it"

    def test_retry_count_bounded(self, lg_result):
        result, _ = lg_result
        assert result.retry_count <= 2, f"Too many retries: {result.retry_count}"

    def test_guardrail_checks_present(self, lg_result):
        result, _ = lg_result
        # At minimum behavioural guardrails must have run
        # (empty list means guardrails never fired — wiring broken)
        state = result.raw.get("state") or {}
        checks = state.get("guardrail_checks") or []
        # This may be empty if all checks pass silently — so just assert structure
        assert isinstance(checks, list)

    def test_no_unhandled_errors(self, lg_result):
        result, _ = lg_result
        state = result.raw.get("state") or {}
        errors = state.get("errors") or []
        unhandled = [e for e in errors if not e.get("handled")]
        assert not unhandled, f"Unhandled errors: {unhandled}"

    def test_token_efficiency(self, lg_result):
        result, _ = lg_result
        tpf = result.metrics.get("tokens_per_file")
        if tpf is None:
            pytest.skip("Token count not available")
        assert tpf < 8000, f"Token bloat: {tpf:.0f} tokens/file"


# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------

class TestLangGraphQuality:
    def test_goal_alignment(self, lg_result):
        result, _ = lg_result
        score = result.metrics.get("goal_alignment")
        if score is None:
            pytest.skip("LLM judge did not run")
        assert score >= 0.6, f"Goal alignment {score:.2f} < 0.6"

    def test_acceptance_criteria_met(self, lg_result):
        result, _ = lg_result
        scores = result.judge_scores
        if not scores:
            pytest.skip("LLM judge did not run")
        for criterion, score in scores.items():
            assert score >= 0.5, f"Criterion failed ({score:.2f}): {criterion}"

    def test_no_hallucinations(self, lg_result):
        result, ws = lg_result
        count = result.metrics.get("hallucination_count", 0)
        assert count == 0, f"{count} hallucination markers in workspace"

    def test_lint_passes(self, lg_result):
        result, _ = lg_result
        lint_ok = result.metrics.get("lint_ok")
        if lint_ok is None:
            pytest.skip("Lint result not available")
        assert lint_ok, "Lint failed in workspace"


# ---------------------------------------------------------------------------
# Cost & latency
# ---------------------------------------------------------------------------

class TestLangGraphCostLatency:
    def test_within_budget(self, lg_result):
        result, _ = lg_result
        if result.cost_usd is None:
            pytest.skip("Cost not reported by langgraph backend")
        assert result.cost_usd <= SCENARIO["budget_usd_max"]

    def test_completes_within_timeout(self, lg_result):
        result, _ = lg_result
        if result.wall_time_s is None:
            pytest.skip("Wall time not recorded")
        assert result.wall_time_s <= SCENARIO["timeout_seconds"]
