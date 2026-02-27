"""
Execution time profiling and benchmarks for AI-Team crews and full flow.

Benchmarks each crew independently, full flow for Demo 1, bottlenecks, hardware
profiles, and token estimation. Results written to docs/benchmark_results.json and
docs/performance_report.md. Run with real LLM via AI_TEAM_BENCHMARK_FULL=1 or
AI_TEAM_USE_REAL_LLM=1.
"""

from __future__ import annotations

import cProfile
import io
import json
import os
import pstats
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest

# Demo 1 spec (beginner complexity) — same as E2E test
DEMO1_SPEC = """Create a simple Flask REST API with:
 - GET /health endpoint returning {status: ok, version: 1.0}
 - GET /items returning a list of items from in-memory storage
 - POST /items accepting {name: str} and adding to the list
 - Proper error handling (400 for bad input, 404 for not found)
 - Unit tests with pytest covering all endpoints and edge cases
 - Requirements.txt and Dockerfile"""

# Phase budgets in seconds (from prompt)
PHASE_BUDGETS = {
    "requirements": 60,
    "architecture": 120,
    "development": 240,
    "qa": 120,
    "deployment": 60,
}


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English/code."""
    return max(0, len(text) // 4)


@pytest.mark.performance
class TestCrewBenchmarks:
    """Benchmark each crew independently: wall time and token estimate."""

    def test_benchmark_planning_crew(
        self,
        benchmark_collector: Dict[str, Any],
        run_real_benchmarks: bool,
    ) -> None:
        """RequirementsCrew + ArchitectureCrew (PlanningCrew): input -> RequirementsDocument + ArchitectureDocument."""
        t0 = time.perf_counter()
        token_in = _estimate_tokens(DEMO1_SPEC)
        token_out = 0
        try:
            if run_real_benchmarks:
                from ai_team.crews.planning_crew import kickoff as planning_kickoff
                from ai_team.flows.main_flow import _parse_planning_output

                result = planning_kickoff(DEMO1_SPEC, verbose=False)
                req, arch, _ = _parse_planning_output(result)
                if req:
                    token_out += _estimate_tokens(req.model_dump_json())
                if arch:
                    token_out += _estimate_tokens(arch.model_dump_json())
            else:
                # Mock path: no LLM; record structure only
                from ai_team.models.architecture import ArchitectureDocument
                from ai_team.models.requirements import RequirementsDocument

                req = RequirementsDocument(
                    project_name="Benchmark",
                    description="Flask API",
                )
                arch = ArchitectureDocument(
                    system_overview="Flask API",
                    components=[],
                    technology_stack=[],
                )
                token_out = _estimate_tokens(req.model_dump_json()) + _estimate_tokens(arch.model_dump_json())
        finally:
            wall_s = time.perf_counter() - t0

        benchmark_collector.setdefault("crews", {})["PlanningCrew"] = {
            "wall_time_seconds": round(wall_s, 3),
            "token_input_estimate": token_in,
            "token_output_estimate": token_out,
            "agent_think_time_seconds": 0,  # Would need CrewAI callbacks
            "tool_call_time_seconds": 0,
        }
        benchmark_collector["meta"]["run_real"] = run_real_benchmarks

    def test_benchmark_development_crew(
        self,
        benchmark_collector: Dict[str, Any],
        run_real_benchmarks: bool,
    ) -> None:
        """DevelopmentCrew: requirements + architecture -> code files."""
        from ai_team.models.architecture import ArchitectureDocument, Component, TechnologyChoice
        from ai_team.models.development import CodeFile
        from ai_team.models.requirements import RequirementsDocument

        req = RequirementsDocument(project_name="Bench", description="Flask API")
        arch = ArchitectureDocument(
            system_overview="Flask API",
            components=[Component(name="API", responsibilities="REST")],
            technology_stack=[TechnologyChoice(name="Flask", category="backend", justification="Simple")],
        )
        t0 = time.perf_counter()
        token_in = _estimate_tokens(req.model_dump_json()) + _estimate_tokens(arch.model_dump_json())
        token_out = 0
        try:
            if run_real_benchmarks:
                from ai_team.crews.development_crew import kickoff as dev_kickoff

                code_files, _ = dev_kickoff(req, arch, verbose=False, memory=False)
                for cf in code_files or []:
                    token_out += _estimate_tokens(getattr(cf, "content", "") or "")
            else:
                code_files = [
                    CodeFile(path="app.py", content="from flask import Flask\napp = Flask(__name__)\n", language="python", description="App"),
                ]
                token_out = sum(_estimate_tokens(c.content) for c in code_files)
        finally:
            wall_s = time.perf_counter() - t0

        benchmark_collector.setdefault("crews", {})["DevelopmentCrew"] = {
            "wall_time_seconds": round(wall_s, 3),
            "token_input_estimate": token_in,
            "token_output_estimate": token_out,
            "agent_think_time_seconds": 0,
            "tool_call_time_seconds": 0,
        }

    def test_benchmark_testing_crew(
        self,
        benchmark_collector: Dict[str, Any],
        run_real_benchmarks: bool,
    ) -> None:
        """QACrew (TestingCrew): code files -> test results."""
        from ai_team.models.development import CodeFile

        code_files = [
            CodeFile(path="app.py", content="from flask import Flask\napp = Flask(__name__)\n", language="python", description="App"),
            CodeFile(path="test_app.py", content="import pytest\n", language="python", description="Tests"),
        ]
        t0 = time.perf_counter()
        token_in = sum(_estimate_tokens(c.content) for c in code_files)
        token_out = 0
        try:
            if run_real_benchmarks:
                from ai_team.crews.testing_crew import kickoff as testing_kickoff

                out = testing_kickoff(code_files, verbose=False, memory=False)
                if out.raw_outputs:
                    token_out = sum(_estimate_tokens(r) for r in out.raw_outputs)
            else:
                token_out = 500
        finally:
            wall_s = time.perf_counter() - t0

        benchmark_collector.setdefault("crews", {})["QACrew"] = {
            "wall_time_seconds": round(wall_s, 3),
            "token_input_estimate": token_in,
            "token_output_estimate": token_out,
            "agent_think_time_seconds": 0,
            "tool_call_time_seconds": 0,
        }

    def test_benchmark_deployment_crew(
        self,
        benchmark_collector: Dict[str, Any],
        run_real_benchmarks: bool,
    ) -> None:
        """DeploymentCrew: code + architecture + test results -> deployment config."""
        from ai_team.models.architecture import ArchitectureDocument
        from ai_team.models.development import CodeFile
        from ai_team.tools.test_tools import TestRunResult

        code_files: List[CodeFile] = [
            CodeFile(path="app.py", content="from flask import Flask\n", language="python", description="App"),
        ]
        arch = ArchitectureDocument(system_overview="Flask API", components=[], technology_stack=[])
        test_results = TestRunResult(
            total=5, passed=5, failed=0, errors=0, skipped=0, warnings=0,
            duration_seconds=1.0, line_coverage_pct=80.0, branch_coverage_pct=None,
            per_file_coverage=[], raw_output="ok", success=True,
        )
        t0 = time.perf_counter()
        token_out = 0
        try:
            if run_real_benchmarks:
                from ai_team.crews.deployment_crew import DeploymentCrew

                crew = DeploymentCrew(verbose=False)
                result = crew.kickoff(code_files, arch, test_results)
                raw = getattr(result, "raw", "") or ""
                token_out = _estimate_tokens(raw)
            else:
                token_out = 300
        finally:
            wall_s = time.perf_counter() - t0

        benchmark_collector.setdefault("crews", {})["DeploymentCrew"] = {
            "wall_time_seconds": round(wall_s, 3),
            "token_input_estimate": 0,
            "token_output_estimate": token_out,
            "agent_think_time_seconds": 0,
            "tool_call_time_seconds": 0,
        }


@pytest.mark.performance
class TestFullFlowBenchmark:
    """Benchmark full flow for Demo 1; flag phases exceeding budget."""

    def test_benchmark_full_flow_demo1(
        self,
        benchmark_collector: Dict[str, Any],
        run_real_benchmarks: bool,
    ) -> None:
        """Full flow for Demo 1 spec; phase-by-phase breakdown; flag over-budget phases."""
        phase_times: Dict[str, float] = {}
        total_start = time.perf_counter()
        try:
            if run_real_benchmarks:
                from ai_team.flows.human_feedback import MockHumanFeedbackHandler
                from ai_team.flows.main_flow import AITeamFlow

                flow = AITeamFlow(feedback_handler=MockHumanFeedbackHandler(default_response="Proceed as-is"))
                flow.state.project_description = DEMO1_SPEC
                flow.kickoff()
                total_s = time.perf_counter() - total_start
                phase_times["total"] = total_s
                # Per-phase times: infer from crew benchmarks (run in same session)
                crews = benchmark_collector.get("crews", {})
                phase_times["requirements_architecture"] = crews.get("PlanningCrew", {}).get("wall_time_seconds", 0)
                phase_times["development"] = crews.get("DevelopmentCrew", {}).get("wall_time_seconds", 0)
                phase_times["qa"] = crews.get("QACrew", {}).get("wall_time_seconds", 0)
                phase_times["deployment"] = crews.get("DeploymentCrew", {}).get("wall_time_seconds", 0)
            else:
                total_s = time.perf_counter() - total_start
                phase_times["total"] = total_s
                for k in ("requirements_architecture", "development", "qa", "deployment"):
                    phase_times[k] = 0.0
        finally:
            pass

        benchmark_collector["full_flow"] = {
            "demo": "Demo 1 (beginner)",
            "total_seconds": round(phase_times.get("total", 0), 2),
            "expected_under_10_minutes": 600,
            "phases": phase_times,
        }
        benchmark_collector["phase_times_seconds"] = phase_times

        # Flag over-budget
        budgets = {"requirements": 60, "architecture": 120, "development": 240, "qa": 120, "deployment": 60}
        req_arch = phase_times.get("requirements_architecture", 0)
        if req_arch > budgets["requirements"] + budgets["architecture"]:
            benchmark_collector.setdefault("bottlenecks", []).append(
                f"Planning (requirements+architecture) exceeded budget: {req_arch:.1f}s"
            )
        for phase, budget in budgets.items():
            val = phase_times.get(phase) or phase_times.get(f"{phase}_seconds", 0)
            if val > budget:
                benchmark_collector.setdefault("bottlenecks", []).append(
                    f"Phase {phase} exceeded budget ({budget}s): {val:.1f}s"
                )


@pytest.mark.performance
class TestBottlenecks:
    """Identify bottlenecks via cProfile; report slowest agents/tools/retries."""

    def test_bottleneck_profiling(
        self,
        benchmark_collector: Dict[str, Any],
    ) -> None:
        """Use cProfile on a minimal crew creation + kickoff path; report top functions."""
        prof = cProfile.Profile()
        prof.enable()
        try:
            from ai_team.crews.planning_crew import create_planning_crew

            crew = create_planning_crew(verbose=False, memory=False)
            _ = crew.agents
            _ = crew.tasks
        finally:
            prof.disable()

        stream = io.StringIO()
        ps = pstats.Stats(prof, stream=stream)
        ps.sort_stats(pstats.SortKey.CUMULATIVE)
        ps.print_stats(15)
        report = stream.getvalue()
        # Store summary line for report
        lines = [l for l in report.splitlines() if l.strip()][:20]
        benchmark_collector.setdefault("bottlenecks", []).append(
            "Profile (top cumulative): " + "; ".join(lines[:5])
        )
        benchmark_collector["profile_summary"] = "\n".join(lines[:25])


@pytest.mark.performance
class TestHardwareProfiles:
    """Record OpenRouter models per role (from OpenRouterSettings)."""

    def test_hardware_profiles(
        self,
        benchmark_collector: Dict[str, Any],
    ) -> None:
        """Record active models per role from OpenRouterSettings (AI_TEAM_ENV)."""
        from ai_team.config.models import OpenRouterSettings

        settings = OpenRouterSettings()
        env = getattr(settings, "ai_team_env", None)
        env_name = str(env.value) if env else "dev"

        role_models: Dict[str, str] = {}
        for role in ("manager", "product_owner", "architect", "backend_dev", "frontend_dev", "devops", "cloud", "qa"):
            role_models[role] = settings.get_model_for_role(role).model_id

        benchmark_collector.setdefault("hardware_profiles", {})["openrouter"] = {
            "env": env_name,
            "models_per_role": role_models,
        }


@pytest.mark.performance
class TestTokenEstimation:
    """Token usage estimation and projected API cost."""

    def test_token_estimation(
        self,
        benchmark_collector: Dict[str, Any],
    ) -> None:
        """Approximate tokens in/out per agent; project cost if OpenAI equivalent; local-first savings."""
        crews = benchmark_collector.get("crews", {})
        total_in = sum(c.get("token_input_estimate", 0) for c in crews.values())
        total_out = sum(c.get("token_output_estimate", 0) for c in crews.values())
        # Rough OpenAI equivalent: $0.01/1K input, $0.03/1K output (example)
        cost_per_1k_in = 0.01
        cost_per_1k_out = 0.03
        projected_usd = (total_in / 1000) * cost_per_1k_in + (total_out / 1000) * cost_per_1k_out
        benchmark_collector["token_estimation"] = {
            "total_input_tokens_estimate": total_in,
            "total_output_tokens_estimate": total_out,
            "projected_openai_equivalent_usd": round(projected_usd, 4),
            "local_first_note": "Ollama/local runs avoid API cost; only hardware/electricity.",
        }


@pytest.mark.performance
def test_save_benchmark_results(
    benchmark_collector: Dict[str, Any],
    benchmark_results_dir: Path,
) -> None:
    """Ensure collector is ready for session teardown to write docs/benchmark_results.json."""
    # Teardown in conftest writes the files; this test just ensures we have minimal structure
    assert "crews" in benchmark_collector or "meta" in benchmark_collector
    # Optionally write here for immediate visibility (conftest also writes at session end)
    if benchmark_collector.get("crews") or benchmark_collector.get("full_flow"):
        benchmark_results_dir.mkdir(parents=True, exist_ok=True)
        json_path = benchmark_results_dir / "benchmark_results.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(benchmark_collector, f, indent=2)
