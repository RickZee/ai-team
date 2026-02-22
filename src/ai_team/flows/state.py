"""
Pydantic models for flow state.

Centralizes ProjectState and supporting types used by AITeamFlow.
Imports document/code types from models and tools; defines phase transitions,
errors, and retry tracking with validators.
"""

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from ai_team.models.architecture import ArchitectureDocument
from ai_team.models.development import CodeFile, DeploymentConfig
from ai_team.models.requirements import RequirementsDocument
from ai_team.tools.test_tools import TestRunResult


# -----------------------------------------------------------------------------
# Phase and transition models
# -----------------------------------------------------------------------------

class ProjectPhase(str, Enum):
    """Phases of the development lifecycle. No skipping allowed in normal path."""

    INTAKE = "intake"
    PLANNING = "planning"
    DEVELOPMENT = "development"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    COMPLETE = "complete"
    ERROR = "error"
    AWAITING_HUMAN = "awaiting_human"
    # Alias for backward compatibility
    FAILED = "error"


# Canonical order for "no skipping" validation (excludes ERROR, AWAITING_HUMAN)
_PHASE_ORDER: List[ProjectPhase] = [
    ProjectPhase.INTAKE,
    ProjectPhase.PLANNING,
    ProjectPhase.DEVELOPMENT,
    ProjectPhase.TESTING,
    ProjectPhase.DEPLOYMENT,
    ProjectPhase.COMPLETE,
]


class PhaseTransition(BaseModel):
    """Record of a single phase transition."""

    from_phase: ProjectPhase = Field(..., description="Phase before transition")
    to_phase: ProjectPhase = Field(..., description="Phase after transition")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the transition occurred",
    )
    reason: str = Field(default="", description="Optional reason or trigger")


class ProjectError(BaseModel):
    """Record of an error during the flow."""

    phase: ProjectPhase = Field(..., description="Phase when the error occurred")
    error_type: str = Field(..., description="Error category or code")
    message: str = Field(..., description="Human-readable message")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the error occurred",
    )
    recoverable: bool = Field(default=True, description="Whether the flow can retry or recover")


# -----------------------------------------------------------------------------
# Main flow state
# -----------------------------------------------------------------------------

class ProjectState(BaseModel):
    """
    Main flow state for the development lifecycle.

    Tracks phase, artifacts (requirements, architecture, code, tests, deployment),
    phase history, errors, and per-phase retries. Validates phase transitions
    (no skipping) and enforces retry limits.
    """

    project_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique project UUID")
    project_description: str = Field(default="", description="User or stakeholder project description")
    current_phase: ProjectPhase = Field(default=ProjectPhase.INTAKE, description="Current lifecycle phase")
    requirements: Optional[RequirementsDocument] = Field(default=None, description="Output from planning")
    architecture: Optional[ArchitectureDocument] = Field(default=None, description="Output from planning")
    generated_files: List[CodeFile] = Field(default_factory=list, description="Code artifacts from development")
    test_results: Optional[TestRunResult] = Field(default=None, description="Result of test execution")
    deployment_config: Optional[DeploymentConfig] = Field(default=None, description="DevOps/deployment output")
    phase_history: List[PhaseTransition] = Field(default_factory=list, description="History of phase transitions")
    errors: List[ProjectError] = Field(default_factory=list, description="Errors encountered")
    retry_counts: Dict[str, int] = Field(default_factory=dict, description="Per-phase retry counts")
    max_retries: int = Field(default=3, ge=0, description="Maximum retries per phase")
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the flow started",
    )
    completed_at: Optional[datetime] = Field(default=None, description="When the flow completed (if any)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata")
    # Human-in-the-loop
    awaiting_human_input: bool = Field(default=False, description="Whether the flow is waiting for user input")
    human_feedback: Optional[str] = Field(default=None, description="Feedback or clarification from user")

    @model_validator(mode="after")
    def _validate_phase_transitions_in_history(self) -> "ProjectState":
        """Ensure every phase transition in history is valid (no skipping)."""
        for t in self.phase_history:
            _validate_transition(t.from_phase, t.to_phase)
        return self

    def add_phase_transition(
        self,
        from_phase: ProjectPhase,
        to_phase: ProjectPhase,
        reason: str = "",
    ) -> None:
        """Append a valid phase transition and update current_phase."""
        _validate_transition(from_phase, to_phase)
        self.phase_history.append(
            PhaseTransition(
                from_phase=from_phase,
                to_phase=to_phase,
                timestamp=datetime.now(timezone.utc),
                reason=reason,
            )
        )
        self.current_phase = to_phase

    def add_error(
        self,
        phase: ProjectPhase,
        error_type: str,
        message: str,
        recoverable: bool = True,
    ) -> None:
        """Record an error for the given phase."""
        self.errors.append(
            ProjectError(
                phase=phase,
                error_type=error_type,
                message=message,
                timestamp=datetime.now(timezone.utc),
                recoverable=recoverable,
            )
        )

    def increment_retry(self, phase: ProjectPhase) -> None:
        """Increment retry count for the given phase. Raises if retry limit exceeded."""
        key = phase.value
        current = self.retry_counts.get(key, 0)
        if current >= self.max_retries:
            raise ValueError(
                f"Retry limit reached for phase {phase.value} ({current} >= {self.max_retries})"
            )
        self.retry_counts[key] = current + 1

    def can_retry(self, phase: ProjectPhase) -> bool:
        """Return True if the phase has not exceeded max_retries."""
        count = self.retry_counts.get(phase.value, 0)
        return count < self.max_retries

    def get_duration(self) -> timedelta:
        """Return elapsed time since started_at; if completed_at set, use that as end."""
        end = self.completed_at or datetime.now(timezone.utc)
        start = self.started_at
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        return end - start

    def to_summary(self) -> str:
        """Human-readable status summary."""
        duration = self.get_duration()
        parts = [
            f"Project {self.project_id[:8]}...",
            f"Phase: {self.current_phase.value}",
            f"Duration: {duration}",
            f"Files: {len(self.generated_files)}",
        ]
        if self.errors:
            parts.append(f"Errors: {len(self.errors)}")
        if self.test_results is not None:
            parts.append(
                f"Tests: {self.test_results.passed}/{self.test_results.total} passed"
            )
        return " | ".join(str(p) for p in parts)


def _validate_transition(from_phase: ProjectPhase, to_phase: ProjectPhase) -> None:
    """
    Validate that a phase transition is allowed (no skipping in main path).

    Allowed:
    - Advance by one step in _PHASE_ORDER (e.g. INTAKE -> PLANNING).
    - Move to ERROR or AWAITING_HUMAN from any phase.
    """
    if to_phase in (ProjectPhase.ERROR, ProjectPhase.FAILED, ProjectPhase.AWAITING_HUMAN):
        return
    try:
        from_idx = _PHASE_ORDER.index(from_phase)
        to_idx = _PHASE_ORDER.index(to_phase)
    except ValueError:
        # One of the phases is not in the main path (e.g. AWAITING_HUMAN)
        return
    if to_idx != from_idx + 1:
        raise ValueError(
            f"Invalid phase transition: {from_phase.value} -> {to_phase.value} "
            "(only sequential phases or transition to error/awaiting_human allowed)"
        )
