"""Pydantic models for the results bundle."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class GeneratedFileEntry(BaseModel):
    path: str = Field(..., description="Path relative to per-run workspace root.")
    sha256: str = Field(..., description="SHA256 of file content (hex).")
    bytes: int = Field(..., description="File size in bytes.")
    phase: str = Field(..., description="Phase that produced this file.")
    agent_role: str = Field(..., description="Agent role responsible for the file write.")
    timestamp: datetime = Field(..., description="UTC timestamp when recorded.")


class RunMetadata(BaseModel):
    project_id: str
    backend: str
    team_profile: str
    env: str | None = None

    started_at: datetime
    completed_at: datetime | None = None

    workspace_dir: str
    output_dir: str

    argv: list[str] = Field(default_factory=list)
    models: dict[str, str] = Field(
        default_factory=dict, description="Role -> model id, when known."
    )
    extra: dict[str, Any] = Field(default_factory=dict)


class Scorecard(BaseModel):
    status: Literal["complete", "error", "partial"] = "partial"
    phases: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Phase -> {status, details...}",
    )
    guardrails: list[dict[str, Any]] = Field(default_factory=list)
    kpis: dict[str, Any] = Field(default_factory=dict)

