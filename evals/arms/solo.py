"""Solo-agent control arm: one SDK session, no behavioral harness (R2)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.arms.base import ArmRun, ArmSpec, CostControls, Divergence, ScenarioContract
from evals.arms.registry import register


class SoloArm:
    """One general-purpose session; observability hooks stay, behavior does not."""

    arm_id = "solo"

    def __init__(self, *, client_factory: Any | None = None) -> None:
        self._client_factory = client_factory

    def describe(self) -> ArmSpec:
        """Solo spec: no harness components, $3 / 30 min ceilings."""
        return ArmSpec(
            arm_id=self.arm_id,
            family="solo",
            model_ids={"*": "configured-default"},
            harness_components=frozenset(),
            source_ref="local",
            cost_controls=CostControls(
                spend_ceiling_usd=3.0, wall_clock_ceiling_s=1800.0, max_sessions=1
            ),
            divergences=[
                Divergence(
                    field="scenario_brief",
                    expected="thin 1-4 sentence brief",
                    actual="full scenario contract",
                    reason="v1 records detailed contracts as a known limitation (design §9.4)",
                )
            ],
        )

    def run(self, scenario: ScenarioContract, workspace: Path, budget_usd: float) -> ArmRun:
        """Create the standard layout and run one mocked or real session."""
        from ai_team.core.workspace_layout import ensure_workspace_layout

        started = datetime.now(UTC)
        workspace.mkdir(parents=True, exist_ok=True)
        ensure_workspace_layout(workspace, scenario.description)
        (workspace / ".arm_id").write_text(self.arm_id, encoding="utf-8")
        status = "ok"
        if self._client_factory is not None:
            client = self._client_factory()
            sessions = getattr(client, "sessions", None)
            if sessions is not None and int(sessions) != 1:
                status = "failed"
            if getattr(client, "spawned_subagents", 0):
                status = "failed"
            if getattr(client, "guardrails_invoked", False):
                status = "failed"
            run_fn = getattr(client, "run", None)
            if callable(run_fn):
                run_fn(scenario.description, workspace, budget_usd)
        ended = datetime.now(UTC)
        return ArmRun(
            arm_id=self.arm_id,
            sweep_id="",
            workspace=workspace,
            status=status,  # type: ignore[arg-type]
            started_at=started,
            ended_at=ended,
            cost_usd=0.0,
        )


register("solo", SoloArm)
