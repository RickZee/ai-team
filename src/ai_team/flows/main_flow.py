"""
AI Team Main Flow Orchestration

This module implements the primary event-driven flow that orchestrates
all crews and manages the end-to-end software development process.
Includes error handling at every step, state persistence, guardrail
integration, flow visualization via plot(), and comprehensive logging.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import structlog
from crewai import Flow
from crewai.flow.flow import listen, router, start

from ai_team.config.settings import get_settings
from ai_team.flows.error_handling import (
    handle_deployment_error as handle_deployment_error_fn,
    handle_development_error as handle_development_error_fn,
    handle_planning_error as handle_planning_error_fn,
    handle_testing_error as handle_testing_error_fn,
    reset_circuit,
)
from ai_team.flows.human_feedback import (
    FeedbackType,
    HumanFeedbackHandler,
    parse_feedback_response,
)
from ai_team.flows.routing import (
    route_after_deployment,
    route_after_development,
    route_after_planning,
    route_after_testing,
)
from ai_team.flows.state import ProjectPhase, ProjectState
from ai_team.models.architecture import ArchitectureDocument
from ai_team.models.development import CodeFile, DeploymentConfig
from ai_team.monitor import MonitorCallback, TeamMonitor
from ai_team.models.requirements import RequirementsDocument
from ai_team.tools.test_tools import TestRunResult

logger = structlog.get_logger()

# Reasonable max length for project description (guardrail)
MAX_PROJECT_DESCRIPTION_LENGTH = 50_000
MIN_PROJECT_DESCRIPTION_LENGTH = 10


# =============================================================================
# HELPERS: planning output extraction
# =============================================================================


def _extract_json_block(text: str) -> Optional[Dict[str, Any]]:
    """Extract first JSON object or array from markdown code block or raw text."""
    if not text or not text.strip():
        return None
    # Code block
    if "```" in text:
        import re
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None


def _persist_state(state: ProjectState) -> None:
    """Write state to output_dir as JSON for persistence. Uses project_id in filename."""
    settings = get_settings()
    out_dir = Path(settings.project.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{state.project_id}_state.json"
    # Serialize; exclude large or non-serializable fields if needed
    data = state.model_dump(mode="json")
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.info("state_persisted", path=str(path))


def _parse_planning_output(crew_result: Any) -> tuple[Optional[RequirementsDocument], Optional[ArchitectureDocument], bool]:
    """
    Extract RequirementsDocument and ArchitectureDocument from Planning Crew output.

    Returns (requirements, architecture, needs_clarification). needs_clarification is True
    if requirements are missing or minimal (e.g. < 3 user stories).
    """
    from ai_team.agents.product_owner import _dict_to_requirements_document

    requirements: Optional[RequirementsDocument] = None
    architecture: Optional[ArchitectureDocument] = None
    needs_clarification = False

    tasks_output = getattr(crew_result, "tasks_output", None) or []
    raw_list = []
    for out in tasks_output:
        raw = getattr(out, "raw", None) or str(out)
        raw_list.append(raw)

    if len(raw_list) >= 1:
        data = _extract_json_block(raw_list[0])
        if data:
            requirements = _dict_to_requirements_document(data)
        if not requirements or (requirements.user_stories and len(requirements.user_stories) < 3):
            needs_clarification = True

    if len(raw_list) >= 2:
        data = _extract_json_block(raw_list[1])
        if data:
            try:
                architecture = ArchitectureDocument.model_validate(data)
            except Exception:
                architecture = ArchitectureDocument(
                    system_overview=data.get("system_overview", "Architecture from planning"),
                    components=[],
                    technology_stack=[],
                )

    if not requirements:
        requirements = RequirementsDocument(
            project_name="Untitled",
            description="Requirements could not be parsed from planning output.",
            user_stories=[],
        )
    if not architecture:
        architecture = ArchitectureDocument(
            system_overview="Architecture could not be parsed.",
            components=[],
            technology_stack=[],
        )

    return requirements, architecture, needs_clarification


# =============================================================================
# MAIN FLOW
# =============================================================================


class AITeamFlow(Flow[ProjectState]):
    """
    Main orchestration flow for the AI development team.

    Coordinates all crews through the software development lifecycle:
    1. Intake & Validation (guardrail: prompt injection, length)
    2. Planning (Requirements + Architecture)
    3. Development (Code Generation)
    4. Testing (QA Validation)
    5. Deployment (DevOps Configuration)

    Use plot() for flow visualization. State is persisted to output_dir on completion/error.
    """

    def __init__(
        self,
        feedback_handler: Optional[HumanFeedbackHandler] = None,
        monitor: Optional[TeamMonitor] = None,
    ) -> None:
        super().__init__()
        self.logger = structlog.get_logger().bind(flow="AITeamFlow")
        self._feedback_handler = feedback_handler
        self._monitor = monitor

    def _get_feedback_handler(self) -> HumanFeedbackHandler:
        """Return injected handler or one built from settings (for CLI/UI and timeout)."""
        if self._feedback_handler is not None:
            return self._feedback_handler
        settings = get_settings()
        fb = settings.human_feedback
        return HumanFeedbackHandler(
            timeout_seconds=fb.timeout_seconds,
            default_response=fb.default_response,
        )

    @start()
    def intake_request(self) -> Dict[str, Any]:
        """
        Entry point: validate project description and run intake guardrails.

        Project description must be set on state before kickoff (e.g. run_ai_team(description)).
        Initializes validation, runs security guardrail, logs project start.
        """
        if self._monitor:
            self._monitor.on_phase_change("intake")
        desc = (self.state.project_description or "").strip()
        self.logger.info("intake_started", request_length=len(desc), project_id=self.state.project_id)

        if len(desc) < MIN_PROJECT_DESCRIPTION_LENGTH:
            self.state.add_error(
                ProjectPhase.INTAKE, "validation_error", "Request too short.", recoverable=True
            )
            self.logger.warning("intake_validation_failed", reason="request_too_short")
            return {"status": "invalid", "reason": "request_too_short"}

        if len(desc) > MAX_PROJECT_DESCRIPTION_LENGTH:
            self.state.add_error(
                ProjectPhase.INTAKE, "validation_error", "Request too long.", recoverable=True
            )
            self.logger.warning("intake_validation_failed", reason="request_too_long")
            return {"status": "invalid", "reason": "request_too_long"}

        from ai_team.guardrails import SecurityGuardrails

        is_safe, message = SecurityGuardrails.validate_prompt_injection(desc)
        if self._monitor:
            self._monitor.on_guardrail(
                "security", "prompt_injection", "pass" if is_safe else "fail", message or ""
            )
        if not is_safe:
            self.state.add_error(
                ProjectPhase.INTAKE, "security_error", message, recoverable=False
            )
            self.logger.warning("intake_guardrail_failed", reason="prompt_injection")
            return {"status": "rejected", "reason": "prompt_injection"}

        self.state.add_phase_transition(ProjectPhase.INTAKE, ProjectPhase.PLANNING, "Input validated")
        return {"status": "success", "request": desc}

    @router(intake_request)
    def route_after_intake(self, intake_result: Dict[str, Any]) -> str:
        """Route based on intake validation results."""
        status = intake_result.get("status", "unknown")
        if status == "success":
            return "run_planning"
        if status == "invalid":
            self.state.metadata["feedback_resume_to"] = "run_planning"
            self.state.metadata["feedback_type"] = "clarification"
            self.state.metadata["feedback_question"] = (
                "Request too short or invalid. Please provide a longer project description or more details."
            )
            self.state.metadata["feedback_context"] = {"phase": "intake", "reason": "validation"}
            self.state.metadata["feedback_options"] = ["Continue with current description", "Abort"]
            self.state.metadata["feedback_default_option"] = "Abort"
            return "request_human_feedback"
        return "handle_fatal_error"

    @listen("run_planning")
    def run_planning_crew(self) -> Dict[str, Any]:
        """Execute PlanningCrew with project description; store requirements and architecture in state."""
        if self._monitor:
            self._monitor.on_phase_change("planning")
            self._monitor.on_log(
                "system",
                "Planning crew started, waiting for first response…",
                "info",
            )
        self.logger.info("planning_started", project_id=self.state.project_id)

        try:
            from ai_team.crews.planning_crew import kickoff as planning_crew_kickoff

            step_cb = task_cb = None
            verbose = None
            if self._monitor:
                cb = MonitorCallback(self._monitor)
                step_cb, task_cb = cb.on_step, cb.on_task
                verbose = False  # avoid CrewAI's live status output; use our TUI only
            result = planning_crew_kickoff(
                self.state.project_description or "",
                step_callback=step_cb,
                task_callback=task_cb,
                verbose=verbose,
            )
            self.state.requirements, self.state.architecture, needs_clarification = _parse_planning_output(
                result
            )
            self.state.add_phase_transition(
                ProjectPhase.PLANNING, ProjectPhase.DEVELOPMENT, "Planning completed"
            )
            reset_circuit(self.state, ProjectPhase.PLANNING)
            try:
                _persist_state(self.state)
            except Exception:
                pass
            confidence = 0.5 if needs_clarification else 1.0
            self.logger.info(
                "planning_complete",
                has_requirements=self.state.requirements is not None,
                has_architecture=self.state.architecture is not None,
                needs_clarification=needs_clarification,
                confidence=confidence,
            )
            return {
                "status": "success",
                "needs_clarification": needs_clarification,
                "confidence": confidence,
            }
        except Exception as e:
            err_msg = str(e)
            self.logger.error("planning_failed", error=err_msg)
            self.state.metadata["last_crew_error"] = {"error": err_msg}
            return {"status": "error", "error": err_msg}

    @router(run_planning_crew)
    def route_after_planning(self, planning_result: Dict[str, Any]) -> str:
        """Route based on planning outcome. Delegates to flows.routing.route_after_planning."""
        return route_after_planning(planning_result, self.state)
    
    @listen("run_development")
    def run_development_crew(self) -> Dict[str, Any]:
        """Execute DevelopmentCrew with planning outputs; store generated files in state."""
        if self._monitor:
            self._monitor.on_phase_change("development")
            self._monitor.on_log(
                "system",
                "Development crew started, waiting for first response…",
                "info",
            )
        self.logger.info("development_started", project_id=self.state.project_id)

        try:
            if not self.state.requirements or not self.state.architecture:
                raise ValueError("Planning outputs missing: requirements and architecture required")
            from ai_team.crews.development_crew import kickoff as development_crew_kickoff

            step_cb = task_cb = None
            verbose = True
            if self._monitor:
                cb = MonitorCallback(self._monitor)
                step_cb, task_cb = cb.on_step, cb.on_task
                verbose = False  # avoid CrewAI's live status output; use our TUI only
            code_files, deployment_config = development_crew_kickoff(
                self.state.requirements,
                self.state.architecture,
                step_callback=step_cb,
                task_callback=task_cb,
                verbose=verbose,
            )
            self.state.generated_files = code_files
            if deployment_config is not None:
                self.state.deployment_config = deployment_config
            self.state.add_phase_transition(
                ProjectPhase.DEVELOPMENT, ProjectPhase.TESTING, "Code generated"
            )
            reset_circuit(self.state, ProjectPhase.DEVELOPMENT)
            try:
                _persist_state(self.state)
            except Exception:
                pass
            self.logger.info(
                "development_complete",
                files_count=len(self.state.generated_files),
                has_deployment_config=self.state.deployment_config is not None,
            )
            return {"status": "success", "files": self.state.generated_files}
        except Exception as e:
            err_msg = str(e)
            self.logger.error("development_failed", error=err_msg)
            self.state.metadata["last_crew_error"] = {"error": err_msg}
            return {"status": "error", "error": err_msg}

    @router(run_development_crew)
    def route_after_development(self, dev_result: Dict[str, Any]) -> str:
        """Route based on development outcome. Delegates to flows.routing.route_after_development."""
        return route_after_development(dev_result, self.state)

    @listen("run_testing")
    def run_testing_crew(self) -> Dict[str, Any]:
        """Execute TestingCrew with code files; store test results in state."""
        if self._monitor:
            self._monitor.on_phase_change("testing")
            self._monitor.on_log(
                "system",
                "Testing crew started, waiting for first response…",
                "info",
            )
        self.logger.info("testing_started", project_id=self.state.project_id)

        try:
            if not self.state.generated_files:
                raise ValueError("No generated files to test")
            from ai_team.crews.testing_crew import kickoff as testing_crew_kickoff

            step_cb = task_cb = None
            verbose = False
            if self._monitor:
                cb = MonitorCallback(self._monitor)
                step_cb, task_cb = cb.on_step, cb.on_task
                verbose = False  # keep False; avoid CrewAI's live status output
            output = testing_crew_kickoff(
                self.state.generated_files,
                step_callback=step_cb,
                task_callback=task_cb,
                verbose=verbose,
            )
            self.state.test_results = output.test_run_result
            if output.quality_gate_passed and output.test_run_result:
                if self._monitor and output.test_run_result:
                    self._monitor.on_test_result(
                        passed=output.test_run_result.passed or 0,
                        failed=output.test_run_result.failed or 0,
                    )
                self.state.add_phase_transition(
                    ProjectPhase.TESTING, ProjectPhase.DEPLOYMENT, "Tests passed"
                )
                reset_circuit(self.state, ProjectPhase.TESTING)
                try:
                    _persist_state(self.state)
                except Exception:
                    pass
                self.logger.info(
                    "testing_complete",
                    quality_gate_passed=True,
                    passed=output.test_run_result.passed,
                    total=output.test_run_result.total,
                )
                return {"status": "success", "results": output.test_run_result}
            self.logger.info(
                "testing_complete",
                quality_gate_passed=False,
                test_run_result=output.test_run_result is not None,
            )
            return {"status": "tests_failed", "results": output.test_run_result, "output": output}
        except Exception as e:
            err_msg = str(e)
            self.logger.error("testing_failed", error=err_msg)
            self.state.metadata["last_crew_error"] = {"error": err_msg}
            return {"status": "error", "error": err_msg}

    @router(run_testing_crew)
    def route_after_testing(self, test_result: Dict[str, Any]) -> str:
        """Route based on testing outcome. Delegates to flows.routing.route_after_testing."""
        return route_after_testing(test_result, self.state)

    @listen("run_deployment")
    def run_deployment_crew(self) -> Dict[str, Any]:
        """Execute DeploymentCrew; package output to output_dir and store deployment config in state."""
        if self._monitor:
            self._monitor.on_phase_change("deployment")
            self._monitor.on_log(
                "system",
                "Deployment crew started, waiting for first response…",
                "info",
            )
        self.logger.info("deployment_started", project_id=self.state.project_id)

        try:
            from ai_team.crews.deployment_crew import DeploymentCrew, package_output

            step_cb = task_cb = None
            if self._monitor:
                cb = MonitorCallback(self._monitor)
                step_cb, task_cb = cb.on_step, cb.on_task
            crew = DeploymentCrew(verbose=False, step_callback=step_cb, task_callback=task_cb)
            product_owner_context = None
            if self.state.requirements:
                product_owner_context = self.state.requirements.description
            deploy_result = crew.kickoff(
                self.state.generated_files,
                self.state.architecture,
                self.state.test_results,
                product_owner_doc_context=product_owner_context,
            )
            settings = get_settings()
            output_dir = Path(settings.project.output_dir) / self.state.project_id
            output_dir.mkdir(parents=True, exist_ok=True)
            package_output(deploy_result, output_dir)
            # DeploymentConfig may be updated from crew if needed; state already has from dev crew
            self.state.add_phase_transition(
                ProjectPhase.DEPLOYMENT, ProjectPhase.COMPLETE, "Deployment configured"
            )
            reset_circuit(self.state, ProjectPhase.DEPLOYMENT)
            try:
                _persist_state(self.state)
            except Exception:
                pass
            self.logger.info("deployment_complete", output_dir=str(output_dir))
            return {"status": "success", "config": self.state.deployment_config}
        except Exception as e:
            err_msg = str(e)
            self.logger.error("deployment_failed", error=err_msg)
            self.state.metadata["last_crew_error"] = {"error": err_msg}
            return {"status": "error", "error": err_msg}

    @router(run_deployment_crew)
    def route_after_deployment(self, deploy_result: Dict[str, Any]) -> str:
        """Route based on deployment outcome. Delegates to flows.routing.route_after_deployment."""
        return route_after_deployment(deploy_result, self.state)

    @listen("finalize_project")
    def finalize_project(self) -> Dict[str, Any]:
        """Package outputs, generate summary, persist state, log completion."""
        if self._monitor:
            self._monitor.on_phase_change("complete")
        self.state.completed_at = datetime.now(timezone.utc)
        duration = self.state.get_duration()
        duration_seconds = duration.total_seconds()

        summary = {
            "project_id": self.state.project_id,
            "status": "complete",
            "files_generated": len(self.state.generated_files),
            "tests_passed": (
                self.state.test_results.passed if self.state.test_results else 0
            ),
            "duration_seconds": duration_seconds,
        }
        self.logger.info("project_complete", **summary)

        try:
            _persist_state(self.state)
        except Exception as e:
            self.logger.warning("state_persistence_failed", error=str(e))

        return summary

    @listen("request_human_feedback")
    def request_human_feedback(self) -> Dict[str, Any]:
        """
        Request clarification/approval from user via HumanFeedbackHandler.

        Called when requirements ambiguous or intake invalid. Reads metadata set by
        routers (feedback_question, context, options, resume_to), calls handler
        (CLI or Gradio callback), parses response, injects into state.human_feedback,
        and returns resume_to so flow can continue from the appropriate step.
        """
        self.state.awaiting_human_input = True
        self.state.add_phase_transition(
            self.state.current_phase, ProjectPhase.AWAITING_HUMAN, "Clarification needed"
        )
        meta = self.state.metadata
        question = meta.get("feedback_question", "Please provide more details.")
        context = meta.get("feedback_context") or {}
        options = meta.get("feedback_options") or ["Continue", "Abort"]
        default_option = meta.get("feedback_default_option") or options[0] if options else ""
        feedback_type_str = meta.get("feedback_type", "clarification")
        try:
            feedback_type = FeedbackType(feedback_type_str)
        except ValueError:
            feedback_type = FeedbackType.CLARIFICATION
        resume_to = meta.get("feedback_resume_to", "handle_fatal_error")

        handler = self._get_feedback_handler()
        response = handler.request_feedback(
            question=question,
            context=context,
            options=options,
            default_option=default_option,
            feedback_type=feedback_type,
            project_id=self.state.project_id,
        )
        parsed = parse_feedback_response(response, options, feedback_type)
        self.state.human_feedback = parsed.raw_response or parsed.free_text or response
        self.state.awaiting_human_input = False
        if parsed.raw_response and "abort" in parsed.raw_response.lower():
            resume_to = "handle_fatal_error"
        self.logger.info(
            "human_feedback_received",
            project_id=self.state.project_id,
            resume_to=resume_to,
            used_default=response == default_option,
        )
        return {"status": "received", "resume_to": resume_to}

    @router(request_human_feedback)
    def route_after_human_feedback(self, feedback_result: Dict[str, Any]) -> str:
        """Resume flow from the step indicated by human feedback (or default)."""
        return feedback_result.get("resume_to", "handle_fatal_error")

    @listen("escalate_to_human")
    def escalate_to_human(self) -> Dict[str, Any]:
        """
        Escalate persistent test failures to human; use same handler as request_human_feedback.

        Presents context (retries, test results), records response in state.human_feedback,
        and returns resume_to: retry_development or handle_fatal_error.
        """
        self.state.add_phase_transition(
            self.state.current_phase, ProjectPhase.AWAITING_HUMAN, "Escalated"
        )
        meta = self.state.metadata
        question = meta.get("feedback_question", "Tests failed multiple times. Retry with feedback or abort?")
        context = meta.get("feedback_context") or {}
        options = meta.get("feedback_options") or ["Retry development with feedback", "Abort"]
        default_option = meta.get("feedback_default_option") or "Abort"
        resume_to = meta.get("feedback_resume_to", "handle_fatal_error")

        handler = self._get_feedback_handler()
        response = handler.request_feedback(
            question=question,
            context=context,
            options=options,
            default_option=default_option,
            feedback_type=FeedbackType.ESCALATION,
            project_id=self.state.project_id,
        )
        parsed = parse_feedback_response(response, options, FeedbackType.ESCALATION)
        self.state.human_feedback = parsed.raw_response or parsed.free_text or response
        if parsed.raw_response and "retry" in parsed.raw_response.lower():
            resume_to = "retry_development"
        retries = self.state.retry_counts.get(ProjectPhase.TESTING.value, 0)
        self.logger.info(
            "escalate_feedback_received",
            project_id=self.state.project_id,
            resume_to=resume_to,
            retries=retries,
        )
        return {"status": "received", "resume_to": resume_to}

    @router(escalate_to_human)
    def route_after_escalate(self, escalate_result: Dict[str, Any]) -> str:
        """Resume after escalation: retry_development or handle_fatal_error."""
        return escalate_result.get("resume_to", "handle_fatal_error")

    @listen("handle_fatal_error")
    def handle_fatal_error(self) -> Dict[str, Any]:
        """Handle unrecoverable errors (e.g. intake rejection). Persist state and transition to ERROR."""
        if self._monitor:
            self._monitor.on_phase_change("error")
        self.state.add_phase_transition(self.state.current_phase, ProjectPhase.ERROR, "Fatal error")
        try:
            _persist_state(self.state)
        except Exception as e:
            self.logger.warning("state_persistence_failed", error=str(e))
        return {"status": "failed", "errors": [e.model_dump() for e in self.state.errors]}

    @listen("handle_planning_error")
    def handle_planning_error(self) -> Dict[str, Any]:
        """Handle planning crew failure: classify, persist, circuit breaker, recovery action."""
        error = self.state.metadata.get("last_crew_error") or {}
        result = handle_planning_error_fn(self.state, error, persist_fn=_persist_state)
        return result

    @router(handle_planning_error)
    def route_after_planning_error(self, handle_result: Dict[str, Any]) -> str:
        """Route after planning error: retry or escalate."""
        if handle_result.get("action") in ("retry", "retry_with_feedback"):
            return "run_planning"
        return "escalate_to_human"

    @listen("retry_planning")
    def retry_planning(self) -> str:
        """Retry planning when architecture was insufficient."""
        self.logger.info("retrying_planning", project_id=self.state.project_id)
        return "run_planning"

    @listen("retry_development")
    def retry_development(self) -> str:
        """Retry development with test feedback."""
        self.logger.info("retrying_development", project_id=self.state.project_id)
        return "run_development"

    @listen("handle_development_error")
    def handle_development_error(self) -> Dict[str, Any]:
        """Handle development crew failure: classify, persist, circuit breaker, recovery action."""
        error = self.state.metadata.get("last_crew_error") or {}
        return handle_development_error_fn(self.state, error, persist_fn=_persist_state)

    @router(handle_development_error)
    def route_after_development_error(self, handle_result: Dict[str, Any]) -> str:
        """Route after development error: retry or escalate."""
        if handle_result.get("action") in ("retry", "retry_with_feedback"):
            return "run_development"
        return "escalate_to_human"

    @listen("handle_testing_error")
    def handle_testing_error(self) -> Dict[str, Any]:
        """Handle testing crew failure: classify, persist, circuit breaker, recovery action."""
        error = self.state.metadata.get("last_crew_error") or {}
        return handle_testing_error_fn(self.state, error, persist_fn=_persist_state)

    @router(handle_testing_error)
    def route_after_testing_error(self, handle_result: Dict[str, Any]) -> str:
        """Route after testing error: retry or escalate."""
        if handle_result.get("action") in ("retry", "retry_with_feedback"):
            return "run_testing"
        return "escalate_to_human"

    @listen("handle_deployment_error")
    def handle_deployment_error(self) -> Dict[str, Any]:
        """Handle deployment crew failure: classify, persist, circuit breaker, recovery action."""
        error = self.state.metadata.get("last_crew_error") or {}
        return handle_deployment_error_fn(self.state, error, persist_fn=_persist_state)

    @router(handle_deployment_error)
    def route_after_deployment_error(self, handle_result: Dict[str, Any]) -> str:
        """Route after deployment error: retry or escalate."""
        if handle_result.get("action") in ("retry", "retry_with_feedback"):
            return "run_deployment"
        return "escalate_to_human"

    def plot(self, path: Optional[Path] = None) -> Optional[str]:
        """
        Flow visualization: return graph representation or save to file.

        If the base Flow provides a plot/get_graph API, delegates to it.
        Otherwise returns a Mermaid-style description of the flow for documentation.
        """
        try:
            if hasattr(super(), "plot"):
                return super().plot(path)  # type: ignore[misc]
            if hasattr(self, "get_graph"):
                graph = self.get_graph()  # type: ignore[attr-defined]
                if path and graph is not None:
                    path = Path(path)
                    path.write_text(str(graph), encoding="utf-8")
                return str(graph) if graph is not None else None
        except Exception:
            pass
        # Fallback: textual flow description
        mermaid = (
            "flowchart TD\n"
            "  intake_request --> route_after_intake\n"
            "  route_after_intake --> run_planning_crew\n"
            "  route_after_intake --> request_human_feedback\n"
            "  route_after_intake --> handle_fatal_error\n"
            "  request_human_feedback --> route_after_human_feedback\n"
            "  route_after_human_feedback --> run_planning_crew\n"
            "  route_after_human_feedback --> run_development_crew\n"
            "  route_after_human_feedback --> handle_fatal_error\n"
            "  run_planning_crew --> route_after_planning\n"
            "  route_after_planning --> run_development_crew\n"
            "  route_after_planning --> request_human_feedback\n"
            "  route_after_planning --> handle_planning_error\n"
            "  handle_planning_error --> route_after_planning_error\n"
            "  route_after_planning_error --> run_planning_crew\n"
            "  route_after_planning_error --> escalate_to_human\n"
            "  run_development_crew --> route_after_development\n"
            "  route_after_development --> run_testing_crew\n"
            "  route_after_development --> retry_planning\n"
            "  route_after_development --> handle_development_error\n"
            "  handle_development_error --> route_after_development_error\n"
            "  route_after_development_error --> run_development_crew\n"
            "  route_after_development_error --> escalate_to_human\n"
            "  retry_planning --> run_planning_crew\n"
            "  run_testing_crew --> route_after_testing\n"
            "  route_after_testing --> run_deployment_crew\n"
            "  route_after_testing --> retry_development\n"
            "  route_after_testing --> escalate_to_human\n"
            "  route_after_testing --> handle_testing_error\n"
            "  handle_testing_error --> route_after_testing_error\n"
            "  route_after_testing_error --> run_testing_crew\n"
            "  route_after_testing_error --> escalate_to_human\n"
            "  escalate_to_human --> route_after_escalate\n"
            "  route_after_escalate --> retry_development\n"
            "  route_after_escalate --> handle_fatal_error\n"
            "  retry_development --> run_development_crew\n"
            "  run_deployment_crew --> route_after_deployment\n"
            "  route_after_deployment --> finalize_project\n"
            "  route_after_deployment --> handle_deployment_error\n"
            "  handle_deployment_error --> route_after_deployment_error\n"
            "  route_after_deployment_error --> run_deployment_crew\n"
            "  route_after_deployment_error --> escalate_to_human\n"
        )
        if path:
            Path(path).write_text(mermaid, encoding="utf-8")
        return mermaid


def run_ai_team(
    project_description: str,
    monitor: Optional[TeamMonitor] = None,
) -> Dict[str, Any]:
    """
    Main entry point to run the AI Team flow.

    Initializes ProjectState with project_description and runs the flow.
    If monitor is provided, starts it before kickoff and stops it after (or on error).
    Returns the final result and full state dump.
    """
    if monitor:
        monitor.start()
    try:
        flow = AITeamFlow(monitor=monitor)
        flow.state.project_description = project_description
        result = flow.kickoff()
        if monitor:
            monitor.stop("complete")
        return {
            "result": result,
            "state": flow.state.model_dump(mode="json"),
        }
    except Exception:
        if monitor:
            monitor.stop("error")
        raise


if __name__ == "__main__":
    result = run_ai_team("Create a simple REST API for managing a todo list")
    print(result)
