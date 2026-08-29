"""Tool classification types for the shared ToolBus.

``ToolKind`` controls execution policy (immediate / draft / gate).
``RiskClass`` scales which guardrails run. They overlap on purpose: a read
can still be customer-visible, and a write can still be low-risk.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ToolKind = Literal["read", "write", "irreversible"]
RiskClass = Literal["low", "write", "irreversible", "customer-visible"]
ObservationCode = Literal[
    "ok",
    "drafted",
    "gated",
    "schema_invalid",
    "permission_denied",
    "not_found",
    "validation_failed",
    "error",
]

SUMMARY_MAX_CHARS = 2000

# Paths whose overwrite is treated as irreversible even when the tool is ``write``.
LOCKFILE_PATHS = frozenset(
    {
        "requirements.txt",
        "pyproject.toml",
        "uv.lock",
        "package-lock.json",
        "poetry.lock",
        ".env",
    }
)


class ToolRequest(BaseModel):
    """Inbound tool call submitted to :class:`~ai_team.tools.bus.ToolBus`."""

    model_config = ConfigDict(extra="forbid")

    tool: str = Field(..., description="Registered tool name.")
    args: dict[str, object] = Field(default_factory=dict, description="Tool arguments.")
    agent_role: str | None = Field(default=None, description="Calling agent role, if known.")
    phase: str | None = Field(default=None, description="Lifecycle phase, if known.")
    backend: str | None = Field(default=None, description="Orchestrator name, if known.")
    run_id: str | None = Field(default=None, description="Run id for audit correlation.")
    allow_irreversible: bool = Field(
        default=False,
        description="Policy token: irreversible tools may execute.",
    )
    human_approved: bool = Field(
        default=False,
        description="Human-interrupt token for irreversible tools.",
    )
    auto_commit: bool = Field(
        default=False,
        description="When True, draft writes are committed immediately (harness salvage).",
    )


class ToolObservation(BaseModel):
    """Structured result returned to the agent. Never a raw shell transcript."""

    ok: bool
    code: ObservationCode
    summary: str = Field(..., description="Capped to SUMMARY_MAX_CHARS by ToolBus.")
    artifact_refs: list[str] = Field(default_factory=list)
    tool: str
    kind: ToolKind
    risk_class: RiskClass
    duration_ms: int = 0
    detail: dict[str, object] = Field(default_factory=dict)
