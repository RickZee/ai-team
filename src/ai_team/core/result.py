"""Unified result model for all orchestration backends."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProjectResult(BaseModel):
    """
    Normalized output from any ``Backend`` implementation.

    CrewAI historically returns ``{"result": ..., "state": ...}``; this model
    carries that in ``raw`` while exposing a stable envelope for CLI and UI.
    """

    backend_name: str = Field(
        ..., description="Backend identifier, e.g. crewai or langgraph."
    )
    success: bool = Field(
        default=True, description="Whether the run completed without fatal error."
    )
    raw: dict[str, Any] = Field(
        default_factory=dict,
        description="Backend-specific payload (e.g. CrewAI result and state dump).",
    )
    error: str | None = Field(
        default=None, description="Error message when success is False."
    )
    team_profile: str = Field(
        default="full", description="Active team profile name for this run."
    )
