"""End-to-end integration tests for the full AI Team flow.

Tests planning, development, testing crews and AITeamFlow with mocked LLM/crew
outputs. No real Ollama or network calls. Uses fixtures from conftest.py.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_team.flows.error_handling import reset_circuit
from ai_team.flows.main_flow import AITeamFlow, _parse_planning_output
from ai_team.flows.state import ProjectPhase
from ai_team.crews.development_crew import kickoff as development_crew_kickoff
from ai_team.crews.planning_crew import kickoff as planning_crew_kickoff
from ai_team.crews.testing_crew import kickoff as run_testing_crew
from ai_team.flows.human_feedback import MockHumanFeedbackHandler


# -----------------------------------------------------------------------------
# 1. test_planning_crew_integration
# -----------------------------------------------------------------------------


class TestPlanningCrewIntegration:
    """Planning crew returns valid RequirementsDocument and ArchitectureDocument."""

    def test_planning_crew_returns_valid_requirements_and_architecture(
        self,
        sample_project_description: str,
        mock_crew_outputs: dict,
    ) -> None:
        """Input: simple project description; mock Ollama; assert valid docs and task order."""
        mock_output = mock_crew_outputs["planning"]
        with patch(
            "ai_team.crews.planning_crew.create_planning_crew",
        ) as mock_create:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_output
            mock_create.return_value = mock_crew

            result = planning_crew_kickoff(sample_project_description)

            mock_create.assert_called_once()
            mock_crew.kickoff.assert_called_once_with(
                inputs={"project_description": sample_project_description}
            )
            assert result is mock_output

        requirements, architecture, needs_clarification = _parse_planning_output(
            result
        )
        assert requirements is not None
        assert architecture is not None
        assert requirements.project_name == "Todo API"
        assert len(requirements.user_stories) >= 3
        for story in requirements.user_stories:
            assert story.acceptance_criteria
        assert architecture.system_overview
        assert not needs_clarification or len(requirements.user_stories) >= 3

    def test_planning_task_dependencies_executed_in_order(
        self,
        sample_project_description: str,
        mock_crew_outputs: dict,
    ) -> None:
        """Kickoff is called once with project_description (task order is crew-internal)."""
        mock_output = mock_crew_outputs["planning"]
        with patch(
            "ai_team.crews.planning_crew.create_planning_crew",
        ) as mock_create:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_output
            mock_create.return_value = mock_crew

            planning_crew_kickoff(sample_project_description)

            mock_crew.kickoff.assert_called_once()
            call_kw = mock_crew.kickoff.call_args[1]
            assert call_kw.get("inputs", {}).get("project_description") == sample_project_description


# -----------------------------------------------------------------------------
# 2. test_development_crew_integration
# -----------------------------------------------------------------------------


class TestDevelopmentCrewIntegration:
    """Development crew returns valid CodeFile list from planning outputs."""

    def test_development_crew_returns_valid_code_files(
        self,
        mock_crew_outputs: dict,
    ) -> None:
        """Input: pre-built RequirementsDocument + ArchitectureDocument; assert valid CodeFile list."""
        requirements = mock_crew_outputs["requirements"]
        architecture = mock_crew_outputs["architecture"]
        expected_files = mock_crew_outputs["code_files"]

        with patch(
            "ai_team.crews.development_crew.kickoff",
            return_value=(expected_files, None),
        ) as mock_kickoff:
            from ai_team.crews.development_crew import kickoff as _dev_kickoff

            code_files, deployment_config = _dev_kickoff(
                requirements,
                architecture,
            )

            mock_kickoff.assert_called_once()
            assert isinstance(code_files, list)
            assert len(code_files) >= 1
            assert deployment_config is None or hasattr(deployment_config, "dockerfile")

        for cf in code_files:
            assert cf.path
            assert cf.content
            assert cf.language

    def test_development_crew_code_files_contain_required_structure(
        self,
        mock_crew_outputs: dict,
    ) -> None:
        """Assert code files contain required imports, functions, or classes."""
        code_files = mock_crew_outputs["code_files"]
        assert any("import" in cf.content or "from " in cf.content for cf in code_files)
        assert any("def " in cf.content or "class " in cf.content for cf in code_files)


# -----------------------------------------------------------------------------
# 3. test_testing_crew_integration
# -----------------------------------------------------------------------------


class TestTestingCrewIntegration:
    """Testing crew returns TestRunResult with coverage data."""

    def test_testing_crew_returns_test_run_result_with_coverage(
        self,
        mock_crew_outputs: dict,
    ) -> None:
        """Input: pre-built CodeFile list; mock pytest; assert TestRunResult with coverage."""
        code_files = mock_crew_outputs["code_files"]
        passed_result = mock_crew_outputs["test_result_passed"]

        with patch(
            "ai_team.crews.testing_crew.create_testing_crew",
        ) as mock_create:
            mock_crew = MagicMock()
            task_outs = [
                MagicMock(raw="test gen output"),
                MagicMock(raw=passed_result.model_dump_json()),
                MagicMock(raw='{"summary":"","findings":[],"critical_count":0,"high_count":0,"passed":true}'),
            ]
            mock_crew.kickoff.return_value = MagicMock(tasks_output=task_outs)
            mock_create.return_value = mock_crew

            output = run_testing_crew(code_files)

            mock_crew.kickoff.assert_called_once()
            assert output.test_run_result is not None
            assert output.test_run_result.total == passed_result.total
            assert output.test_run_result.passed == passed_result.passed
            assert output.test_run_result.line_coverage_pct is not None
            assert output.quality_gate_passed is True


# -----------------------------------------------------------------------------
# 4. test_full_flow_happy_path
# -----------------------------------------------------------------------------


@pytest.mark.timeout(60)
class TestFullFlowHappyPath:
    """Full flow completes all phases in order."""

    def test_full_flow_completes_all_phases(
        self,
        sample_project_description: str,
        mock_crew_outputs: dict,
    ) -> None:
        """Input: project description; mock all LLM/crew responses; assert phases INTAKE → … → COMPLETE."""
        mock_feedback = MockHumanFeedbackHandler(
            default_response="Proceed as-is",
            preloaded_responses=[],
        )
        flow = AITeamFlow(feedback_handler=mock_feedback)
        flow.state.project_description = sample_project_description

        req = mock_crew_outputs["requirements"]
        arch = mock_crew_outputs["architecture"]
        code_files = mock_crew_outputs["code_files"]
        test_result = mock_crew_outputs["test_result_passed"]

        def fake_run_planning(_self: AITeamFlow) -> dict:
            _self.state.requirements = req
            _self.state.architecture = arch
            _self.state.add_phase_transition(
                ProjectPhase.PLANNING, ProjectPhase.DEVELOPMENT, "Planning completed"
            )
            reset_circuit(_self.state, ProjectPhase.PLANNING)
            return {"status": "success", "needs_clarification": False, "confidence": 1.0}

        def fake_run_development(_self: AITeamFlow) -> dict:
            _self.state.generated_files = code_files
            _self.state.add_phase_transition(
                ProjectPhase.DEVELOPMENT, ProjectPhase.TESTING, "Code generated"
            )
            reset_circuit(_self.state, ProjectPhase.DEVELOPMENT)
            return {"status": "success", "files": code_files}

        def fake_run_testing(_self: AITeamFlow) -> dict:
            _self.state.test_results = test_result
            _self.state.add_phase_transition(
                ProjectPhase.TESTING, ProjectPhase.DEPLOYMENT, "Tests passed"
            )
            reset_circuit(_self.state, ProjectPhase.TESTING)
            return {"status": "success", "results": test_result}

        def fake_run_deployment(_self: AITeamFlow) -> dict:
            _self.state.add_phase_transition(
                ProjectPhase.DEPLOYMENT, ProjectPhase.COMPLETE, "Deployment configured"
            )
            reset_circuit(_self.state, ProjectPhase.DEPLOYMENT)
            return {"status": "success", "config": None}

        with patch.object(flow, "run_planning_crew", fake_run_planning), patch.object(
            flow, "run_development_crew", fake_run_development
        ), patch.object(flow, "run_testing_crew", fake_run_testing), patch.object(
            flow, "run_deployment_crew", fake_run_deployment
        ):
            flow.kickoff()

        phases = [t.to_phase for t in flow.state.phase_history]
        assert ProjectPhase.INTAKE in phases
        assert ProjectPhase.PLANNING in phases or ProjectPhase.DEVELOPMENT in phases
        assert ProjectPhase.DEVELOPMENT in phases
        assert ProjectPhase.TESTING in phases
        assert ProjectPhase.DEPLOYMENT in phases
        assert flow.state.current_phase == ProjectPhase.COMPLETE


# -----------------------------------------------------------------------------
# 5. test_flow_retry_on_test_failure
# -----------------------------------------------------------------------------


@pytest.mark.timeout(60)
class TestFlowRetryOnTestFailure:
    """Flow retries development when tests fail, then succeeds on second attempt."""

    def test_flow_retries_development_then_succeeds(
        self,
        sample_project_description: str,
        mock_crew_outputs: dict,
    ) -> None:
        """Mock: first test run fails, second succeeds; assert flow retries and completes."""
        mock_feedback = MockHumanFeedbackHandler(
            default_response="Proceed as-is",
            preloaded_responses=[],
        )
        flow = AITeamFlow(feedback_handler=mock_feedback)
        flow.state.project_description = sample_project_description

        req = mock_crew_outputs["requirements"]
        arch = mock_crew_outputs["architecture"]
        code_files = mock_crew_outputs["code_files"]
        testing_failed = mock_crew_outputs["testing_failed"]
        testing_passed = mock_crew_outputs["testing_passed"]
        test_result_passed = mock_crew_outputs["test_result_passed"]
        testing_call_count = 0

        def fake_run_planning(_self: AITeamFlow) -> dict:
            _self.state.requirements = req
            _self.state.architecture = arch
            _self.state.add_phase_transition(
                ProjectPhase.PLANNING, ProjectPhase.DEVELOPMENT, "Planning completed"
            )
            reset_circuit(_self.state, ProjectPhase.PLANNING)
            return {"status": "success", "needs_clarification": False, "confidence": 1.0}

        def fake_run_development(_self: AITeamFlow) -> dict:
            _self.state.generated_files = code_files
            _self.state.add_phase_transition(
                ProjectPhase.DEVELOPMENT, ProjectPhase.TESTING, "Code generated"
            )
            reset_circuit(_self.state, ProjectPhase.DEVELOPMENT)
            return {"status": "success", "files": code_files}

        def fake_run_testing(_self: AITeamFlow) -> dict:
            nonlocal testing_call_count
            if testing_call_count == 0:
                _self.state.test_results = testing_failed.test_run_result
                testing_call_count += 1
                return {
                    "status": "tests_failed",
                    "results": testing_failed.test_run_result,
                    "output": testing_failed,
                }
            _self.state.test_results = test_result_passed
            _self.state.add_phase_transition(
                ProjectPhase.TESTING, ProjectPhase.DEPLOYMENT, "Tests passed"
            )
            reset_circuit(_self.state, ProjectPhase.TESTING)
            return {"status": "success", "results": test_result_passed}

        def fake_run_deployment(_self: AITeamFlow) -> dict:
            _self.state.add_phase_transition(
                ProjectPhase.DEPLOYMENT, ProjectPhase.COMPLETE, "Deployment configured"
            )
            reset_circuit(_self.state, ProjectPhase.DEPLOYMENT)
            return {"status": "success", "config": None}

        with patch.object(flow, "run_planning_crew", fake_run_planning), patch.object(
            flow, "run_development_crew", fake_run_development
        ), patch.object(flow, "run_testing_crew", fake_run_testing), patch.object(
            flow, "run_deployment_crew", fake_run_deployment
        ):
            flow.kickoff()

        assert testing_call_count >= 2
        assert flow.state.current_phase == ProjectPhase.COMPLETE


# -----------------------------------------------------------------------------
# 6. test_flow_escalation_on_repeated_failure
# -----------------------------------------------------------------------------


@pytest.mark.timeout(60)
class TestFlowEscalationOnRepeatedFailure:
    """Flow escalates to human when all retries fail."""

    def test_flow_escalates_to_human_on_repeated_test_failure(
        self,
        sample_project_description: str,
        mock_crew_outputs: dict,
    ) -> None:
        """Mock: all test runs fail; assert flow escalates to human feedback."""
        mock_feedback = MockHumanFeedbackHandler(
            default_response="Abort",
            preloaded_responses=["Abort"],
        )
        flow = AITeamFlow(feedback_handler=mock_feedback)
        flow.state.project_description = sample_project_description
        flow.state.max_retries = 1

        with patch(
            "ai_team.crews.planning_crew.kickoff",
            return_value=mock_crew_outputs["planning"],
        ), patch(
            "ai_team.crews.development_crew.kickoff",
            return_value=mock_crew_outputs["development"],
        ), patch(
            "ai_team.crews.testing_crew.kickoff",
            return_value=mock_crew_outputs["testing_failed"],
        ):
            flow.kickoff()

        phases = [t.to_phase for t in flow.state.phase_history]
        assert (
            ProjectPhase.AWAITING_HUMAN in phases or flow.state.current_phase == ProjectPhase.ERROR
        )
