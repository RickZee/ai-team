"""Unit tests for ``scorecard_from_langgraph_state`` and ``scorecard_from_project_state``."""

from __future__ import annotations

from ai_team.core.results.writer import (
    scorecard_from_langgraph_state,
    scorecard_from_project_state,
)
from ai_team.flows.state import ProjectPhase, ProjectState
from ai_team.tools import test_tools as test_tools_mod


class TestScorecardFromLanggraphState:
    def test_complete_phase(self) -> None:
        sc = scorecard_from_langgraph_state(
            "run-a",
            {"current_phase": "complete", "metadata": {"team_profile": "backend-api"}},
        )
        assert sc.status == "complete"
        assert sc.run_id == "run-a"
        assert sc.current_phase == "complete"
        assert sc.team_profile == "backend-api"
        assert sc.error_count == 0
        assert sc.artifact_paths["state_json"] == "runs/run-a/state.json"

    def test_error_phase(self) -> None:
        sc = scorecard_from_langgraph_state(
            "run-b",
            {"current_phase": "error", "errors": [{"message": "x"}]},
        )
        assert sc.status == "error"
        assert sc.error_count == 1

    def test_partial_phase(self) -> None:
        sc = scorecard_from_langgraph_state("run-c", {"current_phase": "development"})
        assert sc.status == "partial"
        assert sc.current_phase == "development"

    def test_test_results_lint_and_tests_ok(self) -> None:
        state = {
            "current_phase": "testing",
            "test_results": {
                "passed": False,
                "lint": {"ok": False, "output": "bad"},
                "tests": {"ok": True, "output": "ok"},
            },
        }
        sc = scorecard_from_langgraph_state("tid", state)
        assert sc.lint_ok is False
        assert sc.test_passed is True
        assert "ruff_txt" in sc.artifact_paths
        assert "pytest_txt" in sc.artifact_paths
        assert sc.kpis.get("tests_passed_field") is False

    def test_guardrail_errors_collected(self) -> None:
        state = {
            "current_phase": "error",
            "errors": [
                {
                    "type": "GuardrailError",
                    "message": "blocked",
                    "guardrail": {"phase": "behavioral", "status": "fail"},
                }
            ],
        }
        sc = scorecard_from_langgraph_state("tid", state)
        assert len(sc.guardrails) >= 1
        assert sc.guardrails[0].get("phase") == "behavioral"

    def test_non_dict_errors_normalized(self) -> None:
        sc = scorecard_from_langgraph_state("x", {"errors": "not-a-list"})
        assert sc.error_count == 0


class TestScorecardFromProjectState:
    def test_complete_with_tests_and_duration(self) -> None:
        tr = test_tools_mod.TestRunResult(
            total=5,
            passed=5,
            failed=0,
            success=True,
        )
        st = ProjectState(
            project_id="p1",
            current_phase=ProjectPhase.COMPLETE,
            metadata={"team_profile": "full"},
        )
        st.test_results = tr
        sc = scorecard_from_project_state(
            "p1",
            st,
            status="complete",
            backend="crewai",
            duration_seconds=12.5,
        )
        assert sc.status == "complete"
        assert sc.run_id == "p1"
        assert sc.current_phase == "complete"
        assert sc.team_profile == "full"
        assert sc.backend == "crewai"
        assert sc.test_passed is True
        assert sc.kpis["duration_seconds"] == 12.5
        assert sc.kpis["tests_total"] == 5
        assert sc.kpis["tests_passed_count"] == 5
        assert sc.kpis["files_generated"] == 0

    def test_error_status_counts_errors(self) -> None:
        st = ProjectState(project_id="p2", current_phase=ProjectPhase.ERROR)
        st.add_error(ProjectPhase.TESTING, "test_fail", "failed", recoverable=False)
        sc = scorecard_from_project_state("p2", st, status="error", backend="crewai")
        assert sc.status == "error"
        assert sc.error_count == 1
        assert sc.test_passed is None
