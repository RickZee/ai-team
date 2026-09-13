"""Arm protocol, specs, and run records (harness-alignment R1)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

ArmFamily = Literal["solo", "reference", "ai_team"]
ArmStatus = Literal["ok", "failed", "budget_exhausted", "unavailable"]

ABLATABLE_COMPONENTS = frozenset(
    {
        "guardrails.behavioral",
        "guardrails.security",
        "guardrails.quality",
        "smoke_gate",
        "constraints_pinning",
        "lessons_loop",
        "spend_guard",
        "subprocess_isolation",
        "contract_negotiation",
        "session_regression_check",
        "role_decomposition",
        "bash_allowlist",
    }
)

DEFAULT_SWEEP_CEILING_USD = 25.0


class CostControls(BaseModel):
    """Spend, wall-clock, and session ceilings for one arm."""

    spend_ceiling_usd: float = 6.0
    wall_clock_ceiling_s: float = 3600.0
    max_sessions: int = 1


class Divergence(BaseModel):
    """A forced difference from the equal-arm ideal, with a reason."""

    field: str
    expected: Any
    actual: Any
    reason: str


class ArmSpec(BaseModel):
    """Self-description of one comparison arm."""

    arm_id: str
    family: ArmFamily
    model_ids: dict[str, str] = Field(default_factory=dict)
    harness_components: frozenset[str] = Field(default_factory=frozenset)
    source_ref: str = ""
    cost_controls: CostControls = Field(default_factory=CostControls)
    divergences: list[Divergence] = Field(default_factory=list)


class ArmRun(BaseModel):
    """Outcome of one arm execution."""

    arm_id: str
    sweep_id: str
    workspace: Path
    status: ArmStatus
    started_at: datetime
    ended_at: datetime
    cost_usd: float = 0.0
    trace_id: str | None = None


class ScenarioContract(BaseModel):
    """Thin typed wrapper over a scenario JSON document."""

    id: str
    description: str = ""
    ui: dict[str, Any] | None = None
    raw: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScenarioContract:
        """Build from ``evals/scenarios/*.json``."""
        ui = data.get("ui")
        return cls(
            id=str(data.get("id") or "unknown"),
            description=str(data.get("description") or ""),
            ui=ui if isinstance(ui, dict) else None,
            raw=data,
        )


@runtime_checkable
class Arm(Protocol):
    """Adapter that produces a workspace scored by the existing Trace checks."""

    arm_id: str

    def describe(self) -> ArmSpec:
        """Return the static spec for this arm."""
        ...

    def run(self, scenario: ScenarioContract, workspace: Path, budget_usd: float) -> ArmRun:
        """Execute the arm. Must emit a workspace even on budget exhaustion."""
        ...
