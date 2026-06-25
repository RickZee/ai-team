"""
Cross-backend comparison: runs the same scenario on all three backends,
computes all metrics, prints a side-by-side scorecard, and writes a JSON report.

Run:
    AI_TEAM_USE_REAL_LLM=1 uv run pytest evals/test_backend_comparison.py -v -s

Or via CLI:
    AI_TEAM_USE_REAL_LLM=1 uv run python -m evals.run_evals --compare
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import pytest

from evals.fixtures import (
    EvalResult,
    LLMJudge,
    eval_result_from_run,
    load_scenario,
    run_pytest_in_workspace,
    save_comparison_report,
)
from evals.metrics import compute_metrics, format_scorecard

pytestmark = pytest.mark.skipif(
    not os.environ.get("AI_TEAM_USE_REAL_LLM"),
    reason="Set AI_TEAM_USE_REAL_LLM=1 to run real-LLM evals",
)

SCENARIO_ID = os.environ.get("EVAL_SCENARIO", "smoke-test")
SCENARIO = load_scenario(SCENARIO_ID)
BACKENDS = ["crewai", "langgraph", "claude-agent-sdk"]

# Shared judge so we don't create multiple Anthropic clients
_JUDGE = LLMJudge()

# Collect results for the final report
_results: list[EvalResult] = []


def _run_backend(name: str, ws: Path) -> EvalResult:
    from ai_team.backends.registry import get_backend
    from ai_team.core.team_profile import load_team_profile

    backend = get_backend(name)
    profile = load_team_profile("prototype")
    kwargs: dict[str, Any] = {"skip_estimate": True, "workspace_dir": str(ws)}
    if name == "langgraph":
        kwargs["graph_mode"] = "full"

    timeout_s = SCENARIO.get("timeout_seconds", 600)
    print(f"\n[eval] starting {name} (timeout={timeout_s}s)", flush=True)
    t0 = time.time()

    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(backend.run, SCENARIO["description"], profile, env="dev", **kwargs)
        try:
            raw = future.result(timeout=timeout_s)
        except concurrent.futures.TimeoutError:
            wall = time.time() - t0
            print(f"[eval] {name} TIMED OUT after {wall:.0f}s", flush=True)
            return EvalResult(
                backend=name,
                scenario_id=SCENARIO_ID,
                success=False,
                current_phase="timeout",
                wall_time_s=wall,
                error=f"Backend timed out after {timeout_s}s",
            )

    wall = time.time() - t0
    print(f"[eval] {name} finished in {wall:.0f}s", flush=True)

    result = eval_result_from_run(
        name, SCENARIO_ID, raw.raw, workspace_dir=ws, wall_time_s=wall
    )
    if result.cost_usd is None:
        result.cost_usd = raw.raw.get("cost_usd")
    compute_metrics(result, SCENARIO, judge=_JUDGE, run_judge=True)
    _results.append(result)
    return result


@pytest.fixture(scope="module", params=BACKENDS)
def backend_result(request, tmp_path_factory) -> tuple[EvalResult, Path]:
    name = request.param
    ws = tmp_path_factory.mktemp(name.replace("-", "_"))
    result = _run_backend(name, ws)
    print(f"\n{'='*60}")
    print(format_scorecard(result))
    return result, ws


# ---------------------------------------------------------------------------
# Universal assertions (parameterised across all backends)
# ---------------------------------------------------------------------------

class TestAllBackendsComplete:
    def test_success(self, backend_result):
        result, _ = backend_result
        assert result.success, f"{result.backend} failed: {result.error}"

    def test_files_produced(self, backend_result):
        result, ws = backend_result
        py_files = list(ws.rglob("*.py"))
        assert py_files, f"{result.backend}: no Python files produced"

    def test_pytest_passes(self, backend_result):
        result, ws = backend_result
        out = run_pytest_in_workspace(ws)
        assert out["ok"], f"{result.backend} tests failed:\n{out['output']}"

    def test_no_hallucinations(self, backend_result):
        result, ws = backend_result
        count = result.metrics.get("hallucination_count", 0)
        assert count == 0, f"{result.backend}: {count} hallucination markers"

    def test_goal_alignment_threshold(self, backend_result):
        result, _ = backend_result
        score = result.metrics.get("goal_alignment")
        if score is None:
            pytest.skip("Judge did not run")
        assert score >= 0.6, f"{result.backend} goal alignment {score:.2f} < 0.6"

    def test_retry_count(self, backend_result):
        result, _ = backend_result
        assert result.retry_count <= 3, f"{result.backend}: too many retries ({result.retry_count})"


# ---------------------------------------------------------------------------
# Final report (runs after all parameterised tests)
# ---------------------------------------------------------------------------

def pytest_sessionfinish(session: Any, exitstatus: Any) -> None:
    """Write comparison JSON after the session regardless of pass/fail."""
    if not _results:
        return

    rows = []
    for r in _results:
        rows.append({
            "backend": r.backend,
            "scenario": r.scenario_id,
            "success": r.success,
            "current_phase": r.current_phase,
            "metrics": r.metrics,
            "judge_scores": r.judge_scores,
            "wall_time_s": r.wall_time_s,
            "cost_usd": r.cost_usd,
            "generated_files": r.generated_files,
            "retry_count": r.retry_count,
            "error": r.error,
        })

    path = save_comparison_report(rows, tag=SCENARIO_ID)

    # Print side-by-side summary table
    _print_comparison_table(rows)
    print(f"\nReport saved: {path}")


def _print_comparison_table(rows: list[dict]) -> None:
    if not rows:
        return
    cols = ["backend", "success", "goal_alignment", "test_passed", "hallucination_count",
            "retry_count", "cost_usd", "wall_time_s"]
    header = "  ".join(f"{c:<22}" for c in cols)
    print("\n" + "=" * len(header))
    print("BACKEND COMPARISON")
    print("=" * len(header))
    print(header)
    print("-" * len(header))
    for row in rows:
        m = row.get("metrics") or {}
        vals = [
            str(row.get("backend", ""))[:22],
            str(row.get("success", ""))[:22],
            f"{m.get('goal_alignment', 'n/a')}"[:22],
            str(m.get("test_passed", "n/a"))[:22],
            str(m.get("hallucination_count", "n/a"))[:22],
            str(m.get("retry_count", "n/a"))[:22],
            f"{row.get('cost_usd') or 'n/a'}"[:22],
            f"{row.get('wall_time_s') or 'n/a'}"[:22],
        ]
        print("  ".join(f"{v:<22}" for v in vals))
    print("=" * len(header))
