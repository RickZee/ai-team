"""Ladder sweep orchestration, budget pre-check, and wall-clock kill (R1.5)."""

from __future__ import annotations

import json
import signal
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.arms.base import (
    DEFAULT_SWEEP_CEILING_USD,
    Arm,
    ArmRun,
    ScenarioContract,
)
from evals.arms.registry import get_arm

SWEEP_CEILING_USD = DEFAULT_SWEEP_CEILING_USD


class SweepBudgetError(ValueError):
    """Projected sweep cost exceeds the $25 ceiling."""


class WallClockExpiredError(Exception):
    """Arm exceeded its wall-clock ceiling."""


def project_sweep_cost(arms: list[Arm], n: int) -> float:
    """Sum of per-arm spend ceilings times *n*."""
    return sum(a.describe().cost_controls.spend_ceiling_usd * n for a in arms)


def preflight_budget(arms: list[Arm], n: int, *, ceiling: float = SWEEP_CEILING_USD) -> float:
    """Raise :class:`SweepBudgetError` when the projection exceeds *ceiling*."""
    projected = project_sweep_cost(arms, n)
    if projected > ceiling:
        raise SweepBudgetError(f"projected ${projected:.2f} exceeds sweep ceiling ${ceiling:.2f}")
    return projected


def _kill_arm(signum: int, frame: Any) -> None:
    del signum, frame
    raise WallClockExpiredError("wall-clock ceiling reached")


def run_arm_with_ceiling(arm: Arm, scenario: ScenarioContract, workspace: Path) -> ArmRun:
    """Run *arm* and convert a wall-clock overrun into ``budget_exhausted``."""
    spec = arm.describe()
    ceiling = spec.cost_controls.wall_clock_ceiling_s
    budget = spec.cost_controls.spend_ceiling_usd
    started = datetime.now(UTC)
    if ceiling > 0 and hasattr(signal, "SIGALRM") and hasattr(signal, "setitimer"):
        old = signal.getsignal(signal.SIGALRM)
        try:
            signal.signal(signal.SIGALRM, _kill_arm)
            signal.setitimer(signal.ITIMER_REAL, max(ceiling, 0.01))
            run = arm.run(scenario, workspace, budget)
        except WallClockExpiredError:
            ended = datetime.now(UTC)
            return ArmRun(
                arm_id=arm.arm_id,
                sweep_id="",
                workspace=workspace,
                status="budget_exhausted",
                started_at=started,
                ended_at=ended,
                cost_usd=0.0,
            )
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old)
        return run
    return arm.run(scenario, workspace, budget)


def resolve_plan(
    scenario_id: str,
    arm_ids: list[str],
    n: int,
) -> dict[str, Any]:
    """Resolve arms and print-ready plan without spending."""
    from evals.fixtures import load_scenario

    scenario = ScenarioContract.from_dict(load_scenario(scenario_id))
    arms = [get_arm(i) for i in arm_ids]
    projected = project_sweep_cost(arms, n)
    return {
        "scenario_id": scenario.id,
        "n": n,
        "dry_run": True,
        "projected_usd": projected,
        "ceiling_usd": SWEEP_CEILING_USD,
        "over_ceiling": projected > SWEEP_CEILING_USD,
        "arms": [
            {
                "arm_id": a.describe().arm_id,
                "family": a.describe().family,
                "spend_ceiling_usd": a.describe().cost_controls.spend_ceiling_usd,
                "wall_clock_ceiling_s": a.describe().cost_controls.wall_clock_ceiling_s,
                "harness_components": sorted(a.describe().harness_components),
            }
            for a in arms
        ],
    }


def run_sweep(
    scenario_id: str,
    arm_ids: list[str],
    n: int,
    *,
    execute: bool = False,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """Dry-run by default. ``execute=True`` runs arms sequentially."""
    plan = resolve_plan(scenario_id, arm_ids, n)
    if plan["over_ceiling"]:
        raise SweepBudgetError(
            f"projected ${plan['projected_usd']:.2f} exceeds ${SWEEP_CEILING_USD:.2f}"
        )
    if not execute:
        plan["dry_run"] = True
        return plan

    sweep_id = uuid.uuid4().hex[:12]
    dest = out_dir or Path("evals/results/ladder") / sweep_id
    dest.mkdir(parents=True, exist_ok=True)
    from evals.fixtures import load_scenario

    scenario = ScenarioContract.from_dict(load_scenario(scenario_id))
    runs: list[dict[str, Any]] = []
    for i in range(n):
        for arm_id in arm_ids:
            arm = get_arm(arm_id)
            ws = dest / f"{arm.arm_id}_{i}"
            run = run_arm_with_ceiling(arm, scenario, ws)
            run.sweep_id = sweep_id
            runs.append(run.model_dump(mode="json"))
    manifest = {"sweep_id": sweep_id, "plan": plan, "runs": runs}
    (dest / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )
    return manifest
