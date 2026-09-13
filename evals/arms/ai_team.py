"""``ai_team`` arm — wraps the existing run path and stamps ``arm_id``."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.arms.base import (
    ABLATABLE_COMPONENTS,
    ArmRun,
    ArmSpec,
    CostControls,
    Divergence,
    ScenarioContract,
)
from evals.arms.registry import register

FULL_COMPONENTS = frozenset(ABLATABLE_COMPONENTS) - {"bash_allowlist", "contract_negotiation"}


class AiTeamArm:
    """Existing ai-team run, with an arm stamp and optional component ablation."""

    arm_id = "ai_team"

    def __init__(
        self,
        *,
        ablated: frozenset[str] | None = None,
        runner: Any | None = None,
        model_ids: dict[str, str] | None = None,
        source_ref: str = "local",
    ) -> None:
        self._ablated = ablated or frozenset()
        unknown = self._ablated - ABLATABLE_COMPONENTS
        if unknown:
            raise ValueError(f"cannot ablate unknown components: {sorted(unknown)}")
        self._runner = runner
        self._model_ids = model_ids or {"*": "configured-default"}
        self._source_ref = source_ref
        if self._ablated:
            removed = ",".join(sorted(self._ablated))
            self.arm_id = (
                "harnessed_solo"
                if self._ablated == frozenset({"role_decomposition"})
                else f"ai_team_ablated:{removed}"
            )

    def describe(self) -> ArmSpec:
        """Return the spec, recording the active component set."""
        active = FULL_COMPONENTS - self._ablated
        divergences: list[Divergence] = [
            Divergence(
                field="scenario_brief",
                expected="thin 1-4 sentence brief",
                actual="full scenario contract",
                reason="v1 records detailed contracts as a known limitation (design §9.4)",
            )
        ]
        if self._ablated:
            divergences.append(
                Divergence(
                    field="harness_components",
                    expected=sorted(FULL_COMPONENTS),
                    actual=sorted(active),
                    reason=f"ablated: {sorted(self._ablated)}",
                )
            )
        return ArmSpec(
            arm_id=self.arm_id,
            family="ai_team",
            model_ids=self._model_ids,
            harness_components=active,
            source_ref=self._source_ref,
            cost_controls=CostControls(spend_ceiling_usd=6.0, wall_clock_ceiling_s=3600.0),
            divergences=divergences,
        )

    def run(self, scenario: ScenarioContract, workspace: Path, budget_usd: float) -> ArmRun:
        """Delegate to the existing runner; stamp ``arm_id`` onto the workspace."""
        started = datetime.now(UTC)
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / ".arm_id").write_text(self.arm_id, encoding="utf-8")
        status = "ok"
        cost = 0.0
        if self._runner is not None:
            result = self._runner(scenario, workspace, budget_usd, ablated=self._ablated)
            if isinstance(result, dict):
                status = str(result.get("status") or "ok")
                cost = float(result.get("cost_usd") or 0.0)
        ended = datetime.now(UTC)
        return ArmRun(
            arm_id=self.arm_id,
            sweep_id="",
            workspace=workspace,
            status=status,  # type: ignore[arg-type]
            started_at=started,
            ended_at=ended,
            cost_usd=cost,
        )


def _factory() -> AiTeamArm:
    return AiTeamArm()


def _harnessed_solo_factory() -> AiTeamArm:
    return AiTeamArm(ablated=frozenset({"role_decomposition"}))


register("ai_team", _factory)
register("harnessed_solo", _harnessed_solo_factory)
