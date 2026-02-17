"""
Conditional routing logic for AITeamFlow.

Pure functions that take phase result dicts and ProjectState, log decisions
with reasoning, update state (phase transitions, retry counts) where applicable,
and return the next step name for string-based @router dispatch.

Routing diagram (simplified):

    intake_request
         │
         ▼
    route_after_intake ──┬── success ──► run_planning
                         ├── invalid ──► request_human_feedback
                         └── rejected ──► handle_fatal_error

    run_planning_crew
         │
         ▼
    route_after_planning ──┬── requirements + arch complete, confidence ≥ 0.7 ──► run_development
                          ├── ambiguous (confidence < 0.7) ──► request_human_feedback
                          └── error ──► handle_planning_error

    run_development_crew
         │
         ▼
    route_after_development ──┬── code generated ──► run_testing
                              ├── insufficient_architecture ──► retry_planning
                              └── error ──► handle_development_error

    run_testing_crew
         │
         ▼
    route_after_testing ──┬── all pass, coverage OK ──► run_deployment
                          ├── tests failed, can_retry ──► retry_development (increment retry)
                          ├── retries exhausted / critical ──► escalate_to_human
                          └── execution error ──► handle_testing_error

    run_deployment_crew
         │
         ▼
    route_after_deployment ──┬── success ──► finalize_project
                             └── error ──► handle_deployment_error
"""

from __future__ import annotations

from typing import Any, Dict

import structlog

from ai_team.flows.state import ProjectPhase, ProjectState

logger = structlog.get_logger()


def _set_escalation_metadata(
    state: ProjectState, test_result: Dict[str, Any], reason: str
) -> None:
    """Set metadata for escalate_to_human so the feedback handler can show context."""
    results = test_result.get("results")
    passed = getattr(results, "passed", None) if results else None
    total = getattr(results, "total", None) if results else None
    state.metadata["feedback_resume_to"] = "handle_fatal_error"
    state.metadata["feedback_type"] = "escalation"
    state.metadata["feedback_question"] = (
        f"Tests failed after {state.retry_counts.get(ProjectPhase.TESTING.value, 0)} retries. "
        "Please review and choose: retry development with your feedback, or abort."
    )
    state.metadata["feedback_context"] = {
        "phase": "testing",
        "reason": reason,
        "passed": passed,
        "total": total,
    }
    state.metadata["feedback_options"] = ["Retry development with feedback", "Abort"]
    state.metadata["feedback_default_option"] = "Abort"

# Confidence below this threshold routes planning to human feedback.
PLANNING_CONFIDENCE_THRESHOLD = 0.7


def route_after_planning(planning_result: Dict[str, Any], state: ProjectState) -> str:
    """
    Route after planning crew: run_development, request_human_feedback, or handle_planning_error.

    - run_development: requirements and architecture complete and confidence ≥ threshold.
    - request_human_feedback: requirements ambiguous (confidence < 0.7 or needs_clarification).
    - handle_planning_error: crew execution failed.
    """
    status = planning_result.get("status", "unknown")
    if status != "success":
        reason = "planning_crew_failed"
        logger.warning(
            "routing_after_planning",
            decision="handle_planning_error",
            reason=reason,
            status=status,
            error=planning_result.get("error"),
        )
        return "handle_planning_error"

    needs_clarification = planning_result.get("needs_clarification", False)
    confidence = planning_result.get("confidence")
    if confidence is None:
        confidence = 0.0 if needs_clarification else 1.0
    requirements_ok = state.requirements is not None and (
        not state.requirements.user_stories or len(state.requirements.user_stories) >= 3
    )
    architecture_ok = state.architecture is not None

    if needs_clarification or confidence < PLANNING_CONFIDENCE_THRESHOLD:
        reason = "requirements_ambiguous"
        state.add_phase_transition(
            state.current_phase, ProjectPhase.AWAITING_HUMAN, reason
        )
        state.metadata["feedback_resume_to"] = "run_development"
        state.metadata["feedback_type"] = "approval"
        state.metadata["feedback_question"] = (
            "Requirements are ambiguous (e.g. 'fast' or scope not defined). "
            "Define performance target / scope, or confirm to proceed as-is."
        )
        state.metadata["feedback_context"] = {
            "phase": "planning",
            "confidence": confidence,
            "user_stories_count": len(state.requirements.user_stories) if state.requirements else 0,
        }
        state.metadata["feedback_options"] = ["Proceed as-is", "Add clarification (type below)"]
        state.metadata["feedback_default_option"] = "Proceed as-is"
        logger.info(
            "routing_after_planning",
            decision="request_human_feedback",
            reason=reason,
            confidence=confidence,
            needs_clarification=needs_clarification,
        )
        return "request_human_feedback"

    if not requirements_ok or not architecture_ok:
        reason = "requirements_or_architecture_incomplete"
        logger.warning(
            "routing_after_planning",
            decision="handle_planning_error",
            reason=reason,
            requirements_ok=requirements_ok,
            architecture_ok=architecture_ok,
        )
        return "handle_planning_error"

    logger.info(
        "routing_after_planning",
        decision="run_development",
        reason="requirements_and_architecture_complete",
        confidence=confidence,
    )
    return "run_development"


def route_after_development(dev_result: Dict[str, Any], state: ProjectState) -> str:
    """
    Route after development crew: run_testing, retry_planning, or handle_development_error.

    - run_testing: code files generated successfully.
    - retry_planning: architecture was insufficient (rare; flag in dev_result).
    - handle_development_error: execution failed.
    """
    status = dev_result.get("status", "unknown")
    if status != "success":
        reason = "development_crew_failed"
        logger.warning(
            "routing_after_development",
            decision="handle_development_error",
            reason=reason,
            status=status,
            error=dev_result.get("error"),
        )
        return "handle_development_error"

    if dev_result.get("insufficient_architecture", False):
        reason = "architecture_insufficient"
        state.add_phase_transition(
            state.current_phase, ProjectPhase.PLANNING, reason
        )
        logger.info(
            "routing_after_development",
            decision="retry_planning",
            reason=reason,
        )
        return "retry_planning"

    files = dev_result.get("files") or state.generated_files
    if not files:
        reason = "no_code_files_generated"
        logger.warning(
            "routing_after_development",
            decision="handle_development_error",
            reason=reason,
        )
        return "handle_development_error"

    logger.info(
        "routing_after_development",
        decision="run_testing",
        reason="code_files_generated",
        files_count=len(files),
    )
    return "run_testing"


def route_after_testing(test_result: Dict[str, Any], state: ProjectState) -> str:
    """
    Route after testing crew: run_deployment, retry_development, escalate_to_human, or handle_testing_error.

    - run_deployment: all tests pass and coverage meets threshold.
    - retry_development: tests failed but retry count < max (increments retry, passes feedback).
    - escalate_to_human: retries exhausted or critical failures.
    - handle_testing_error: crew execution error.
    """
    status = test_result.get("status", "unknown")
    if status == "success":
        logger.info(
            "routing_after_testing",
            decision="run_deployment",
            reason="all_tests_pass_coverage_ok",
        )
        return "run_deployment"

    if status == "error":
        reason = "testing_crew_execution_error"
        logger.warning(
            "routing_after_testing",
            decision="handle_testing_error",
            reason=reason,
            error=test_result.get("error"),
        )
        return "handle_testing_error"

    # status == "tests_failed"
    if not state.can_retry(ProjectPhase.TESTING):
        reason = "retries_exhausted"
        state.add_phase_transition(
            state.current_phase, ProjectPhase.AWAITING_HUMAN, reason
        )
        _set_escalation_metadata(state, test_result, reason)
        logger.warning(
            "routing_after_testing",
            decision="escalate_to_human",
            reason=reason,
            retry_count=state.retry_counts.get(ProjectPhase.TESTING.value, 0),
        )
        return "escalate_to_human"

    critical = test_result.get("critical_failures", False)
    if critical:
        reason = "critical_test_failures"
        state.add_phase_transition(
            state.current_phase, ProjectPhase.AWAITING_HUMAN, reason
        )
        _set_escalation_metadata(state, test_result, reason)
        logger.warning(
            "routing_after_testing",
            decision="escalate_to_human",
            reason=reason,
        )
        return "escalate_to_human"

    state.increment_retry(ProjectPhase.TESTING)
    logger.info(
        "routing_after_testing",
        decision="retry_development",
        reason="tests_failed_retry_available",
        retry_count=state.retry_counts.get(ProjectPhase.TESTING.value, 0),
        max_retries=state.max_retries,
    )
    return "retry_development"


def route_after_deployment(deploy_result: Dict[str, Any], state: ProjectState) -> str:
    """
    Route after deployment crew: finalize_project or handle_deployment_error.

    - finalize_project: deployment succeeded.
    - handle_deployment_error: deployment failed.
    """
    status = deploy_result.get("status", "unknown")
    if status == "success":
        logger.info(
            "routing_after_deployment",
            decision="finalize_project",
            reason="deployment_success",
        )
        return "finalize_project"

    reason = "deployment_crew_failed"
    logger.warning(
        "routing_after_deployment",
        decision="handle_deployment_error",
        reason=reason,
        status=status,
        error=deploy_result.get("error"),
    )
    return "handle_deployment_error"
