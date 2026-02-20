"""Integration tests for AITeamFlow state transitions and routing logic.

Tests phase transitions (INTAKE → PLANNING → DEV → QA → DEPLOY), routing at each
phase gate, failure routing (QA fail → back to DEV), and human escalation.
Uses mocked crew outputs to test flow logic independently of LLM.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ai_team.flows.main_flow import AITeamFlow
from ai_team.flows.routing import (
    route_after_deployment,
    route_after_development,
    route_after_planning,
    route_after_testing,
)
from ai_team.flows.state import ProjectPhase, ProjectState
from ai_team.flows.human_feedback import MockHumanFeedbackHandler


# Routing is on the flow instance; route_after_intake is a method. Check routing module.
def _route_after_intake(flow: AITeamFlow, intake_result: dict) -> str:
    """Call flow's route_after_intake."""
    return flow.route_after_intake(intake_result)


# -----------------------------------------------------------------------------
# State transitions: INTAKE → PLANNING → DEV → QA → DEPLOY
# -----------------------------------------------------------------------------


class TestFlowStateTransitions:
    """AITeamFlow state transitions follow INTAKE → PLANNING → DEV → QA → DEPLOY."""

    def test_intake_success_transitions_to_planning(self) -> None:
        """Valid intake routes to run_planning."""
        flow = AITeamFlow()
        flow.state.project_description = "x" * 20  # above MIN length
        result = flow.intake_request()
        assert result.get("status") == "success"
        assert flow.state.current_phase == ProjectPhase.PLANNING
        step = _route_after_intake(flow, result)
        assert step == "run_planning"

    def test_planning_success_transitions_to_development(
        self,
        mock_crew_outputs: dict,
    ) -> None:
        """Planning success with confidence ≥ threshold routes to run_development."""
        flow = AITeamFlow()
        flow.state.project_description = "A REST API"
        flow.state.add_phase_transition(
            ProjectPhase.INTAKE, ProjectPhase.PLANNING, "ok"
        )
        flow.state.requirements = mock_crew_outputs["requirements"]
        flow.state.architecture = mock_crew_outputs["architecture"]

        planning_result = {
            "status": "success",
            "needs_clarification": False,
            "confidence": 0.9,
        }
        step = route_after_planning(planning_result, flow.state)
        assert step == "run_development"

    def test_development_success_transitions_to_testing(
        self,
        mock_crew_outputs: dict,
    ) -> None:
        """Development success with code files routes to run_testing."""
        flow = AITeamFlow()
        flow.state.add_phase_transition(
            ProjectPhase.PLANNING, ProjectPhase.DEVELOPMENT, "ok"
        )
        flow.state.generated_files = mock_crew_outputs["code_files"]

        dev_result = {"status": "success", "files": mock_crew_outputs["code_files"]}
        step = route_after_development(dev_result, flow.state)
        assert step == "run_testing"

    def test_testing_success_transitions_to_deployment(
        self,
        mock_crew_outputs: dict,
    ) -> None:
        """Testing success routes to run_deployment."""
        flow = AITeamFlow()
        flow.state.add_phase_transition(
            ProjectPhase.DEVELOPMENT, ProjectPhase.TESTING, "ok"
        )

        test_result = {"status": "success", "results": mock_crew_outputs["test_result_passed"]}
        step = route_after_testing(test_result, flow.state)
        assert step == "run_deployment"

    def test_deployment_success_transitions_to_finalize(
        self,
    ) -> None:
        """Deployment success routes to finalize_project."""
        flow = AITeamFlow()
        flow.state.add_phase_transition(
            ProjectPhase.TESTING, ProjectPhase.DEPLOYMENT, "ok"
        )

        deploy_result = {"status": "success"}
        step = route_after_deployment(deploy_result, flow.state)
        assert step == "finalize_project"


# -----------------------------------------------------------------------------
# Routing logic per phase gate
# -----------------------------------------------------------------------------


class TestRoutingLogicPerPhase:
    """Routing decisions at each phase gate."""

    def test_intake_invalid_routes_to_human_feedback(self) -> None:
        """Short/invalid intake routes to request_human_feedback."""
        flow = AITeamFlow()
        flow.state.project_description = "short"
        result = flow.intake_request()
        assert result.get("status") == "invalid"
        step = _route_after_intake(flow, result)
        assert step == "request_human_feedback"

    def test_planning_error_routes_to_handle_planning_error(self) -> None:
        """Planning crew error routes to handle_planning_error."""
        flow = AITeamFlow()
        flow.state.requirements = None
        flow.state.architecture = None
        step = route_after_planning(
            {"status": "error", "error": "Crew failed"},
            flow.state,
        )
        assert step == "handle_planning_error"

    def test_planning_low_confidence_routes_to_human_feedback(
        self,
        mock_crew_outputs: dict,
    ) -> None:
        """Planning with confidence < threshold routes to request_human_feedback."""
        flow = AITeamFlow()
        flow.state.add_phase_transition(
            ProjectPhase.INTAKE, ProjectPhase.PLANNING, "ok"
        )
        flow.state.requirements = mock_crew_outputs["requirements"]
        flow.state.architecture = mock_crew_outputs["architecture"]

        step = route_after_planning(
            {
                "status": "success",
                "needs_clarification": True,
                "confidence": 0.5,
            },
            flow.state,
        )
        assert step == "request_human_feedback"

    def test_development_error_routes_to_handle_development_error(self) -> None:
        """Development crew error routes to handle_development_error."""
        flow = AITeamFlow()
        step = route_after_development(
            {"status": "error", "error": "Build failed"},
            flow.state,
        )
        assert step == "handle_development_error"

    def test_testing_error_routes_to_handle_testing_error(self) -> None:
        """Testing crew execution error routes to handle_testing_error."""
        flow = AITeamFlow()
        step = route_after_testing(
            {"status": "error", "error": "Runner failed"},
            flow.state,
        )
        assert step == "handle_testing_error"

    def test_deployment_error_routes_to_handle_deployment_error(self) -> None:
        """Deployment crew error routes to handle_deployment_error."""
        flow = AITeamFlow()
        step = route_after_deployment(
            {"status": "error", "error": "Package failed"},
            flow.state,
        )
        assert step == "handle_deployment_error"


# -----------------------------------------------------------------------------
# Failure routing: QA fail → back to DEV
# -----------------------------------------------------------------------------


class TestFailureRoutingQaFailBackToDev:
    """When tests fail, flow routes back to development (retry) or escalates."""

    def test_tests_failed_with_retry_available_routes_to_retry_development(
        self,
        mock_crew_outputs: dict,
    ) -> None:
        """Tests failed and can_retry → route to retry_development."""
        flow = AITeamFlow()
        flow.state.add_phase_transition(
            ProjectPhase.DEVELOPMENT, ProjectPhase.TESTING, "ok"
        )
        flow.state.max_retries = 3
        # retry_counts[testing] = 0, so can_retry is True
        test_result = {
            "status": "tests_failed",
            "results": mock_crew_outputs["testing_failed"].test_run_result,
            "output": mock_crew_outputs["testing_failed"],
        }
        step = route_after_testing(test_result, flow.state)
        assert step == "retry_development"
        assert flow.state.retry_counts.get(ProjectPhase.TESTING.value, 0) == 1

    def test_tests_failed_retries_exhausted_routes_to_escalate(
        self,
        mock_crew_outputs: dict,
    ) -> None:
        """Tests failed and max retries exceeded → route to escalate_to_human."""
        flow = AITeamFlow()
        flow.state.add_phase_transition(
            ProjectPhase.DEVELOPMENT, ProjectPhase.TESTING, "ok"
        )
        flow.state.max_retries = 1
        flow.state.retry_counts[ProjectPhase.TESTING.value] = 1  # already at max
        test_result = {
            "status": "tests_failed",
            "results": mock_crew_outputs["testing_failed"].test_run_result,
        }
        step = route_after_testing(test_result, flow.state)
        assert step == "escalate_to_human"
        assert flow.state.current_phase == ProjectPhase.AWAITING_HUMAN or (
            any(
                t.to_phase == ProjectPhase.AWAITING_HUMAN
                for t in flow.state.phase_history
            )
        )


# -----------------------------------------------------------------------------
# Human escalation trigger
# -----------------------------------------------------------------------------


class TestHumanEscalationTrigger:
    """Human escalation is triggered and metadata set for feedback handler."""

    def test_escalation_sets_feedback_metadata(
        self,
        mock_crew_outputs: dict,
    ) -> None:
        """When routing to escalate_to_human, metadata has feedback_question and options."""
        flow = AITeamFlow()
        flow.state.add_phase_transition(
            ProjectPhase.DEVELOPMENT, ProjectPhase.TESTING, "ok"
        )
        flow.state.max_retries = 1
        flow.state.retry_counts[ProjectPhase.TESTING.value] = 1
        test_result = {
            "status": "tests_failed",
            "results": mock_crew_outputs["testing_failed"].test_run_result,
        }
        route_after_testing(test_result, flow.state)
        assert flow.state.metadata.get("feedback_question")
        assert "feedback_options" in flow.state.metadata
        assert flow.state.metadata.get("feedback_resume_to") == "handle_fatal_error"

    def test_request_human_feedback_listener_transitions_to_awaiting_human(
        self,
    ) -> None:
        """request_human_feedback step sets awaiting_human_input and AWAITING_HUMAN phase."""
        flow = AITeamFlow(
            feedback_handler=MockHumanFeedbackHandler(default_response="Proceed as-is")
        )
        flow.state.metadata["feedback_question"] = "Proceed?"
        flow.state.metadata["feedback_options"] = ["Yes", "No"]
        flow.state.metadata["feedback_resume_to"] = "run_development"
        flow.state.metadata["feedback_type"] = "approval"
        flow.state.metadata["feedback_context"] = {}
        flow.state.add_phase_transition(
            ProjectPhase.INTAKE, ProjectPhase.PLANNING, "ok"
        )
        result = flow.request_human_feedback()
        assert result.get("resume_to") in ("run_development", "handle_fatal_error")
        assert flow.state.awaiting_human_input is False  # handler resolved it
        phases = [t.to_phase for t in flow.state.phase_history]
        assert ProjectPhase.AWAITING_HUMAN in phases
