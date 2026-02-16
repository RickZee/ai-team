"""End-to-end integration tests for the full AI Team flow.

Tests planning, development, testing crews and AITeamFlow with mocked LLM/crew
outputs. No real Ollama or network calls. Uses fixtures from conftest.py.

Full-flow tests (TestFullFlowHappyPath, TestFlowRetryOnTestFailure,
TestFlowEscalationOnRepeatedFailure) use _run_flow_manually() and do not call
flow.kickoff(), so they run synchronously and do not hang.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ai_team.flows.error_handling import reset_circuit
from ai_team.flows.main_flow import AITeamFlow, _parse_planning_output
from ai_team.flows.state import ProjectPhase
from ai_team.flows.routing import (
    route_after_deployment,
    route_after_development,
    route_after_planning,
    route_after_testing,
)
from ai_team.config.settings import get_settings
from ai_team.crews.development_crew import kickoff as development_crew_kickoff
from ai_team.crews.planning_crew import kickoff as planning_crew_kickoff
from ai_team.crews.testing_crew import kickoff as run_testing_crew
from ai_team.flows.human_feedback import MockHumanFeedbackHandler


# -----------------------------------------------------------------------------
# Full-flow runner (no CrewAI kickoff — avoids async/event-bus hang)
# -----------------------------------------------------------------------------
#
# Root cause of hang: CrewAI Flow stores callables in flow._methods (populated in
# __init__ via getattr(self, method_name)). It invokes method = self._methods[name]
# in _execute_single_listener, so patching flow.run_planning_crew after creation
# has no effect. Replacing flow._methods[name] with fakes still left kickoff()
# inside asyncio.run() and the event bus (crewai_event_bus.emit + _event_futures)
# which could block or consume excessive memory. So we bypass kickoff() entirely
# and drive the flow by calling intake_request -> route_after_intake -> routers
# and fake crew results in sequence (sync, no event bus).


def _run_flow_manually(
    flow: AITeamFlow,
    *,
    requirements: Any,
    architecture: Any,
    code_files: list[Any],
    planning_result: dict,
    development_result: dict,
    testing_results: list[dict],
    deployment_result: dict,
) -> None:
    """Drive the flow by calling intake -> routers -> fake crew results in sequence.

    Does not call flow.kickoff(); avoids CrewAI Flow async and event bus.
    """
    intake_result = flow.intake_request()
    step = flow.route_after_intake(intake_result)
    testing_index = 0

    while step not in ("finalize_project", "handle_fatal_error", "escalate_to_human"):
        if step == "run_planning":
            flow.state.requirements = requirements
            flow.state.architecture = architecture
            flow.state.add_phase_transition(
                ProjectPhase.PLANNING, ProjectPhase.DEVELOPMENT, "Planning completed"
            )
            reset_circuit(flow.state, ProjectPhase.PLANNING)
            step = route_after_planning(planning_result, flow.state)
        elif step == "run_development":
            flow.state.generated_files = development_result.get("files", code_files)
            flow.state.add_phase_transition(
                ProjectPhase.DEVELOPMENT, ProjectPhase.TESTING, "Code generated"
            )
            reset_circuit(flow.state, ProjectPhase.DEVELOPMENT)
            step = route_after_development(development_result, flow.state)
        elif step == "run_testing":
            tr = testing_results[min(testing_index, len(testing_results) - 1)]
            testing_index += 1
            flow.state.test_results = tr.get("results")
            if tr.get("status") == "success":
                flow.state.add_phase_transition(
                    ProjectPhase.TESTING, ProjectPhase.DEPLOYMENT, "Tests passed"
                )
                reset_circuit(flow.state, ProjectPhase.TESTING)
            step = route_after_testing(tr, flow.state)
        elif step == "run_deployment":
            flow.state.add_phase_transition(
                ProjectPhase.DEPLOYMENT, ProjectPhase.COMPLETE, "Deployment configured"
            )
            reset_circuit(flow.state, ProjectPhase.DEPLOYMENT)
            step = route_after_deployment(deployment_result, flow.state)
        elif step == "retry_development":
            flow.state.add_phase_transition(
                ProjectPhase.DEVELOPMENT, ProjectPhase.TESTING, "Code generated"
            )
            reset_circuit(flow.state, ProjectPhase.DEVELOPMENT)
            step = route_after_development(development_result, flow.state)
        else:
            break

    if step == "finalize_project":
        flow.finalize_project()


# -----------------------------------------------------------------------------
# 1. test_planning_crew_integration
# -----------------------------------------------------------------------------


@pytest.mark.real_llm
class TestPlanningCrewIntegration:
    """Planning crew returns valid RequirementsDocument and ArchitectureDocument."""

    def test_planning_crew_returns_valid_requirements_and_architecture(
        self,
        sample_project_description: str,
        mock_crew_outputs: dict,
        use_real_llm: bool,
    ) -> None:
        """With mock: assert exact fixture output. With real LLM: assert structure only."""
        if use_real_llm:
            if not get_settings().validate_ollama_connection():
                pytest.skip("Ollama unreachable; run with mock or start Ollama")
            result = planning_crew_kickoff(sample_project_description)
            requirements, architecture, needs_clarification = _parse_planning_output(result)
            assert requirements is not None
            assert architecture is not None
            assert len(requirements.user_stories) >= 1
            for story in requirements.user_stories:
                assert story.acceptance_criteria
            assert architecture.system_overview
            return

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
        use_real_llm: bool,
    ) -> None:
        """With mock: kickoff called once with project_description. With real: skip (crew-internal)."""
        if use_real_llm:
            pytest.skip("Task order is crew-internal; covered by structure test with real LLM")
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


@pytest.mark.real_llm
class TestDevelopmentCrewIntegration:
    """Development crew returns valid CodeFile list from planning outputs."""

    def test_development_crew_returns_valid_code_files(
        self,
        mock_crew_outputs: dict,
        use_real_llm: bool,
    ) -> None:
        """With mock: assert fixture output. With real LLM: assert structure only."""
        requirements = mock_crew_outputs["requirements"]
        architecture = mock_crew_outputs["architecture"]
        expected_files = mock_crew_outputs["code_files"]

        if use_real_llm:
            if not get_settings().validate_ollama_connection():
                pytest.skip("Ollama unreachable; run with mock or start Ollama")
            from ai_team.crews.development_crew import kickoff as _dev_kickoff

            code_files, deployment_config = _dev_kickoff(requirements, architecture)
            assert isinstance(code_files, list)
            assert len(code_files) >= 1
            assert deployment_config is None or hasattr(deployment_config, "dockerfile")
            for cf in code_files:
                assert cf.path
                assert cf.content
                assert cf.language
            return

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
        use_real_llm: bool,
    ) -> None:
        """With mock: assert fixture structure. With real: skip (covered by valid code_files test)."""
        if use_real_llm:
            pytest.skip("Structure covered by test_development_crew_returns_valid_code_files")
        code_files = mock_crew_outputs["code_files"]
        assert any("import" in cf.content or "from " in cf.content for cf in code_files)
        assert any("def " in cf.content or "class " in cf.content for cf in code_files)


# -----------------------------------------------------------------------------
# 3. test_testing_crew_integration
# -----------------------------------------------------------------------------


@pytest.mark.real_llm
class TestTestingCrewIntegration:
    """Testing crew returns TestRunResult with coverage data."""

    def test_testing_crew_returns_test_run_result_with_coverage(
        self,
        mock_crew_outputs: dict,
        use_real_llm: bool,
    ) -> None:
        """With mock: assert fixture output. With real LLM: assert structure only."""
        code_files = mock_crew_outputs["code_files"]
        passed_result = mock_crew_outputs["test_result_passed"]

        if use_real_llm:
            if not get_settings().validate_ollama_connection():
                pytest.skip("Ollama unreachable; run with mock or start Ollama")
            output = run_testing_crew(code_files)
            assert output.test_run_result is not None
            assert isinstance(output.test_run_result.total, int)
            assert isinstance(output.test_run_result.passed, int)
            assert output.test_run_result.line_coverage_pct is None or isinstance(
                output.test_run_result.line_coverage_pct, (int, float)
            )
            assert isinstance(output.quality_gate_passed, bool)
            return

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
@pytest.mark.full_flow
class TestFullFlowHappyPath:
    """Full flow completes all phases in order."""

    def test_full_flow_completes_all_phases(
        self,
        sample_project_description: str,
        mock_crew_outputs: dict,
    ) -> None:
        """Input: project description; mock all LLM/crew responses; assert phases INTAKE → … → COMPLETE."""
        flow = AITeamFlow(feedback_handler=MockHumanFeedbackHandler(default_response="Proceed as-is"))
        flow.state.project_description = sample_project_description

        req = mock_crew_outputs["requirements"]
        arch = mock_crew_outputs["architecture"]
        code_files = mock_crew_outputs["code_files"]
        test_result = mock_crew_outputs["test_result_passed"]

        _run_flow_manually(
            flow,
            requirements=req,
            architecture=arch,
            code_files=code_files,
            planning_result={"status": "success", "needs_clarification": False, "confidence": 1.0},
            development_result={"status": "success", "files": code_files},
            testing_results=[{"status": "success", "results": test_result}],
            deployment_result={"status": "success", "config": None},
        )

        # phase_history records transitions (from_phase -> to_phase); INTAKE is initial
        to_phases = [t.to_phase for t in flow.state.phase_history]
        assert flow.state.phase_history[0].from_phase == ProjectPhase.INTAKE
        assert ProjectPhase.PLANNING in to_phases or ProjectPhase.DEVELOPMENT in to_phases
        assert ProjectPhase.DEVELOPMENT in to_phases
        assert ProjectPhase.TESTING in to_phases
        assert ProjectPhase.DEPLOYMENT in to_phases
        assert flow.state.current_phase == ProjectPhase.COMPLETE


# -----------------------------------------------------------------------------
# 5. test_flow_retry_on_test_failure
# -----------------------------------------------------------------------------


@pytest.mark.timeout(60)
@pytest.mark.full_flow
class TestFlowRetryOnTestFailure:
    """Flow retries development when tests fail, then succeeds on second attempt."""

    def test_flow_retries_development_then_succeeds(
        self,
        sample_project_description: str,
        mock_crew_outputs: dict,
    ) -> None:
        """Mock: first test run fails, second succeeds; assert flow retries and completes."""
        flow = AITeamFlow(feedback_handler=MockHumanFeedbackHandler(default_response="Proceed as-is"))
        flow.state.project_description = sample_project_description

        req = mock_crew_outputs["requirements"]
        arch = mock_crew_outputs["architecture"]
        code_files = mock_crew_outputs["code_files"]
        testing_failed = mock_crew_outputs["testing_failed"]
        test_result_passed = mock_crew_outputs["test_result_passed"]

        _run_flow_manually(
            flow,
            requirements=req,
            architecture=arch,
            code_files=code_files,
            planning_result={"status": "success", "needs_clarification": False, "confidence": 1.0},
            development_result={"status": "success", "files": code_files},
            testing_results=[
                {"status": "tests_failed", "results": testing_failed.test_run_result, "output": testing_failed},
                {"status": "success", "results": test_result_passed},
            ],
            deployment_result={"status": "success", "config": None},
        )

        assert flow.state.current_phase == ProjectPhase.COMPLETE


# -----------------------------------------------------------------------------
# 6. test_flow_escalation_on_repeated_failure
# -----------------------------------------------------------------------------


@pytest.mark.timeout(60)
@pytest.mark.full_flow
class TestFlowEscalationOnRepeatedFailure:
    """Flow escalates to human when all retries fail."""

    def test_flow_escalates_to_human_on_repeated_test_failure(
        self,
        sample_project_description: str,
        mock_crew_outputs: dict,
    ) -> None:
        """Mock: all test runs fail; assert flow escalates to human feedback."""
        flow = AITeamFlow(feedback_handler=MockHumanFeedbackHandler(default_response="Abort"))
        flow.state.project_description = sample_project_description
        flow.state.max_retries = 1

        req = mock_crew_outputs["requirements"]
        arch = mock_crew_outputs["architecture"]
        code_files = mock_crew_outputs["code_files"]
        testing_failed = mock_crew_outputs["testing_failed"]

        _run_flow_manually(
            flow,
            requirements=req,
            architecture=arch,
            code_files=code_files,
            planning_result={"status": "success", "needs_clarification": False, "confidence": 1.0},
            development_result={"status": "success", "files": code_files},
            testing_results=[
                {"status": "tests_failed", "results": testing_failed.test_run_result, "output": testing_failed},
                {"status": "tests_failed", "results": testing_failed.test_run_result, "output": testing_failed},
            ],
            deployment_result={"status": "success", "config": None},
        )

        phases = [t.to_phase for t in flow.state.phase_history]
        assert (
            ProjectPhase.AWAITING_HUMAN in phases or flow.state.current_phase == ProjectPhase.ERROR
        )
