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
    kwargs: dict[str, Any] = {
        "skip_estimate": True,
        "workspace_dir": str(ws),
        "run_label": SCENARIO_ID,
    }
    if name == "langgraph":
        kwargs["graph_mode"] = "full"

    # Give 1.5x the scenario budget so slow backends don't get killed mid-run
    timeout_s = max(int(SCENARIO.get("timeout_seconds", 600) * 1.5), 600)
    print(f"\n[eval] starting {name} (timeout={timeout_s}s)", flush=True)
    t0 = time.time()

    import multiprocessing
    import queue as _queue

    def _worker(q: multiprocessing.Queue) -> None:  # type: ignore[type-arg]
        try:
            result = backend.run(SCENARIO["description"], profile, env="dev", **kwargs)
            # Serialize to plain dict before putting on queue — avoids pickling
            # complex crewai/langgraph objects which cause RecursionError
            import json as _json
            import sys as _sys

            # Strip non-serializable crewai objects before json.dumps to avoid
            # infinite recursion in FlowOutput / circular ref structures.
            safe_keys = {
                "state",
                "thread_id",
                "project_id",
                "success",
                "cost_usd",
                "generated_files",
                "test_results",
                "workspace",
                "team_profile",
                "agents",
                "phases",
                "session_id",
                "usage",
                "requirements",
                "architecture",
                "deployment_config",
            }
            safe_raw = {k: v for k, v in result.raw.items() if k in safe_keys}
            old_limit = _sys.getrecursionlimit()
            _sys.setrecursionlimit(500)
            try:
                raw_dict = _json.loads(_json.dumps(safe_raw, default=str))
            except Exception:
                raw_dict = {k: str(v) for k, v in safe_raw.items()}
            finally:
                _sys.setrecursionlimit(old_limit)
            q.put(("ok", {"raw": raw_dict, "success": result.success, "error": result.error}))
        except Exception as exc:
            q.put(("err", str(exc)))

    q: multiprocessing.Queue = multiprocessing.Queue()  # type: ignore[type-arg]
    proc = multiprocessing.Process(target=_worker, args=(q,), daemon=True)
    proc.start()
    proc.join(timeout=timeout_s)

    if proc.is_alive():
        proc.kill()
        proc.join()
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

    try:
        status, payload = q.get_nowait()
    except _queue.Empty:
        status, payload = "err", "no result in queue"

    if status == "err":
        wall = time.time() - t0
        print(f"[eval] {name} ERROR: {payload}", flush=True)
        return EvalResult(
            backend=name,
            scenario_id=SCENARIO_ID,
            success=False,
            current_phase="error",
            wall_time_s=wall,
            error=str(payload),
        )
    serialized = payload  # {"raw": dict, "success": bool, "error": str|None}

    wall = time.time() - t0
    print(f"[eval] {name} finished in {wall:.0f}s", flush=True)

    raw_dict = {**serialized["raw"], "success": serialized["success"]}
    result = eval_result_from_run(name, SCENARIO_ID, raw_dict, workspace_dir=ws, wall_time_s=wall)
    if result.cost_usd is None:
        result.cost_usd = serialized["raw"].get("cost_usd")
    compute_metrics(result, SCENARIO, judge=_JUDGE, run_judge=True)
    _results.append(result)
    return result


@pytest.fixture(scope="module", params=BACKENDS)
def backend_result(request, tmp_path_factory) -> tuple[EvalResult, Path]:
    name = request.param
    ws = tmp_path_factory.mktemp(name.replace("-", "_"))
    result = _run_backend(name, ws)
    print(f"\n{'=' * 60}")
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
        rows.append(
            {
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
            }
        )

    path = save_comparison_report(rows, tag=SCENARIO_ID)

    # Print side-by-side summary table
    _print_comparison_table(rows)
    print(f"\nReport saved: {path}")


def _print_comparison_table(rows: list[dict]) -> None:
    if not rows:
        return
    cols = [
        "backend",
        "success",
        "goal_alignment",
        "test_passed",
        "hallucination_count",
        "retry_count",
        "cost_usd",
        "wall_time_s",
    ]
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
