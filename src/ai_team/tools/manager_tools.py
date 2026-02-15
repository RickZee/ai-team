"""
Manager agent tools: task delegation, timeline, blocker resolution, status reporting.

These tools integrate with ProjectState when used within AITeamFlow: status and
phase suggestions can be applied to the flow state by the orchestrator.
"""

from typing import Any, Dict, List, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

import structlog

logger = structlog.get_logger(__name__)

# Default capability hints for delegation (can be overridden by flow/context)
DEFAULT_AGENT_CAPABILITIES: Dict[str, List[str]] = {
    "product_owner": ["requirements", "user_stories", "acceptance_criteria", "prioritization"],
    "architect": ["architecture", "tech_stack", "api_design", "adr"],
    "backend_developer": ["backend", "api", "database", "services"],
    "frontend_developer": ["frontend", "ui", "components", "ux"],
    "devops_engineer": ["ci_cd", "docker", "pipelines", "deployment"],
    "cloud_engineer": ["infrastructure", "terraform", "cloud", "iac"],
    "qa_engineer": ["testing", "automation", "quality", "e2e"],
}


# -----------------------------------------------------------------------------
# Tool input schemas
# -----------------------------------------------------------------------------


class TaskDelegationInput(BaseModel):
    """Input for task_delegation tool."""

    task_description: str = Field(..., description="Clear description of the task to delegate.")
    required_skills: List[str] = Field(
        default_factory=list,
        description="Skills or domains needed (e.g. backend, testing, architecture).",
    )
    current_workload: Optional[str] = Field(
        default=None,
        description="Optional JSON or summary of each agent's current workload to balance assignment.",
    )
    priority: str = Field(default="normal", description="One of: low, normal, high, critical.")


class TimelineManagementInput(BaseModel):
    """Input for timeline_management tool."""

    current_phase: str = Field(
        ...,
        description="Current project phase (e.g. intake, planning, development, testing, deployment).",
    )
    completed_milestones: Optional[str] = Field(
        default=None,
        description="Comma-separated or JSON list of completed milestones.",
    )
    next_milestones: Optional[str] = Field(
        default=None,
        description="Planned next milestones or deliverables.",
    )
    risks_or_delays: Optional[str] = Field(
        default=None,
        description="Any risks or delays affecting the timeline.",
    )


class BlockerResolutionInput(BaseModel):
    """Input for blocker_resolution tool."""

    blocker_description: str = Field(..., description="Description of the blocker.")
    affected_phase: Optional[str] = Field(
        default=None,
        description="Phase or area affected (e.g. development, testing).",
    )
    suggested_actions: Optional[str] = Field(
        default=None,
        description="Optional suggested actions to resolve or escalate.",
    )


class StatusReportingInput(BaseModel):
    """Input for status_reporting tool."""

    project_id: Optional[str] = Field(default=None, description="Project identifier for the report.")
    current_phase: str = Field(
        ...,
        description="Current project phase.",
    )
    summary: str = Field(..., description="Brief status summary.")
    phase_suggestion: Optional[str] = Field(
        default=None,
        description="Suggested next phase transition if any (e.g. planning -> development).",
    )
    blockers: Optional[str] = Field(
        default=None,
        description="Comma-separated list of current blockers.",
    )
    state_updates_json: Optional[str] = Field(
        default=None,
        description="Optional JSON object with suggested ProjectState updates (phase_history, warnings, etc.).",
    )


# -----------------------------------------------------------------------------
# Tools
# -----------------------------------------------------------------------------


class TaskDelegationTool(BaseTool):
    """
    Delegate a task to the most suitable agent based on capabilities and workload.
    Use when the manager needs to assign work to a specific role.
    """

    name: str = "task_delegation"
    description: str = (
        "Assign a task to the best-suited agent based on required skills and current workload. "
        "Use when coordinating work: provide task description, required skills, and optional workload summary. "
        "Returns the recommended agent and a short justification."
    )
    args_schema: Type[BaseModel] = TaskDelegationInput

    def _run(
        self,
        task_description: str,
        required_skills: Optional[List[str]] = None,
        current_workload: Optional[str] = None,
        priority: str = "normal",
    ) -> str:
        required_skills = required_skills or []
        required_lower = [s.lower().strip() for s in required_skills]
        best_agent = None
        best_score = -1
        for agent_name, capabilities in DEFAULT_AGENT_CAPABILITIES.items():
            score = sum(
                1
                for s in required_lower
                if any(c in s or s in c for c in capabilities)
            )
            if score > best_score:
                best_score = score
                best_agent = agent_name
        if not best_agent:
            best_agent = "backend_developer"
        logger.info(
            "task_delegation_recommendation",
            task=task_description[:80],
            recommended_agent=best_agent,
            priority=priority,
        )
        return (
            f"Recommended assignment: **{best_agent}**. "
            f"Task: {task_description[:200]}. "
            f"Priority: {priority}. "
            f"Use this when creating the next task for the crew."
        )


class TimelineManagementTool(BaseTool):
    """
    Track and report on project timeline, milestones, and phase transitions.
    Output can be used to update ProjectState.phase_history and status.
    """

    name: str = "timeline_management"
    description: str = (
        "Manage and report project timeline: current phase, completed and upcoming milestones, "
        "risks or delays. Use to maintain project status and recommend phase transitions. "
        "Returns a timeline summary and optional phase transition suggestion for ProjectState."
    )
    args_schema: Type[BaseModel] = TimelineManagementInput

    def _run(
        self,
        current_phase: str,
        completed_milestones: Optional[str] = None,
        next_milestones: Optional[str] = None,
        risks_or_delays: Optional[str] = None,
    ) -> str:
        lines = [
            f"Current phase: **{current_phase}**.",
            f"Completed: {completed_milestones or 'None specified'}.",
            f"Next: {next_milestones or 'None specified'}.",
        ]
        if risks_or_delays:
            lines.append(f"Risks/delays: {risks_or_delays}.")
        logger.info(
            "timeline_management",
            current_phase=current_phase,
        )
        return " ".join(lines) + " Use this to update project status and phase_history in ProjectState."


class BlockerResolutionTool(BaseTool):
    """
    Record and suggest resolution for blockers; can recommend human escalation.
    """

    name: str = "blocker_resolution"
    description: str = (
        "Record a blocker and get resolution suggestions. Use when a task or phase is blocked. "
        "If the blocker requires human input or critical decisions, recommend escalating (set "
        "awaiting_human_input and human_feedback in ProjectState)."
    )
    args_schema: Type[BaseModel] = BlockerResolutionInput

    def _run(
        self,
        blocker_description: str,
        affected_phase: Optional[str] = None,
        suggested_actions: Optional[str] = None,
    ) -> str:
        phase = affected_phase or "unknown"
        actions = suggested_actions or "Assess impact; consider reassigning or escalating to human."
        logger.info(
            "blocker_resolution",
            blocker=blocker_description[:80],
            affected_phase=phase,
        )
        return (
            f"Blocker recorded: {blocker_description}. "
            f"Affected phase: {phase}. "
            f"Suggested actions: {actions}. "
            "If this requires human decision or clarification, use human escalation (awaiting_human_input=true)."
        )


class StatusReportingTool(BaseTool):
    """
    Produce a status report and optional ProjectState updates.
    Integrates with ProjectState: summary, phase_suggestion, and state_updates_json
    can be applied by the flow to update state.
    """

    name: str = "status_reporting"
    description: str = (
        "Produce a project status report. Provide current phase, summary, optional next phase suggestion, "
        "and blockers. Use state_updates_json to suggest ProjectState updates (e.g. phase transition, "
        "warnings). The flow will merge these into ProjectState."
    )
    args_schema: Type[BaseModel] = StatusReportingInput

    def _run(
        self,
        current_phase: str,
        summary: str,
        project_id: Optional[str] = None,
        phase_suggestion: Optional[str] = None,
        blockers: Optional[str] = None,
        state_updates_json: Optional[str] = None,
    ) -> str:
        lines = [
            f"Project: {project_id or 'current'}.",
            f"Phase: **{current_phase}**.",
            f"Summary: {summary}.",
        ]
        if phase_suggestion:
            lines.append(f"Suggested next phase: {phase_suggestion}.")
        if blockers:
            lines.append(f"Blockers: {blockers}.")
        if state_updates_json:
            lines.append(f"State updates (for flow): {state_updates_json}.")
        logger.info(
            "status_reporting",
            project_id=project_id,
            current_phase=current_phase,
        )
        return " ".join(lines)


def get_manager_tools() -> List[BaseTool]:
    """Return the list of tools for the Manager agent."""
    return [
        TaskDelegationTool(),
        TimelineManagementTool(),
        BlockerResolutionTool(),
        StatusReportingTool(),
    ]
