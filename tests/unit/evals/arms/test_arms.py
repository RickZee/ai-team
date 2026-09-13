"""Arm protocol, registry, budget, and control-arm unit tests."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from evals.arms.base import ABLATABLE_COMPONENTS, ArmRun, ArmSpec, Divergence, ScenarioContract
from evals.arms.ladder import SweepBudgetError, preflight_budget, resolve_plan, run_arm_with_ceiling
from evals.arms.registry import DuplicateArmError, get_arm, register

pytestmark = pytest.mark.eval_unit


def test_spec_and_divergence_round_trip() -> None:
    spec = ArmSpec(
        arm_id="solo",
        family="solo",
        model_ids={"*": "x"},
        divergences=[Divergence(field="a", expected=1, actual=2, reason="because")],
    )
    restored = ArmSpec.model_validate_json(spec.model_dump_json())
    assert restored == spec
    run = ArmRun(
        arm_id="solo",
        sweep_id="s",
        workspace=Path("/tmp/ws"),
        status="ok",
        started_at=datetime.now(UTC),
        ended_at=datetime.now(UTC),
    )
    assert ArmRun.model_validate_json(run.model_dump_json()).arm_id == "solo"


def test_duplicate_registration_raises() -> None:
    from evals.arms.registry import ensure_arms_loaded

    ensure_arms_loaded()
    with pytest.raises(DuplicateArmError):
        register("solo", lambda: get_arm("solo"))


def test_ai_team_arm_stamps_id_and_matches_direct(tmp_path: Path) -> None:
    from evals.arms.ai_team import AiTeamArm

    written: list[str] = []

    def runner(scenario, workspace, budget, ablated=None):  # noqa: ANN001
        del budget, ablated
        (workspace / "out.txt").write_text(scenario.id, encoding="utf-8")
        written.append(scenario.id)
        return {"status": "ok", "cost_usd": 0.0}

    scenario = ScenarioContract(id="todo-api-beginner", description="x")
    direct = tmp_path / "direct"
    direct.mkdir()
    runner(scenario, direct, 1.0)
    arm = AiTeamArm(runner=runner)
    ws = tmp_path / "arm"
    run = arm.run(scenario, ws, 1.0)
    assert run.arm_id == "ai_team"
    assert (ws / "out.txt").read_text(encoding="utf-8") == (direct / "out.txt").read_text(
        encoding="utf-8"
    )
    assert (ws / ".arm_id").read_text(encoding="utf-8") == "ai_team"


def test_harnessed_solo_one_agent_all_components() -> None:
    from evals.arms.ai_team import AiTeamArm

    arm = AiTeamArm(ablated=frozenset({"role_decomposition"}))
    spec = arm.describe()
    assert arm.arm_id == "harnessed_solo"
    assert "role_decomposition" not in spec.harness_components
    assert spec.harness_components
    assert "smoke_gate" in spec.harness_components


def test_solo_arm_layout_and_mocked_client(tmp_path: Path) -> None:
    from evals.arms.solo import SoloArm

    class _Client:
        sessions = 1
        spawned_subagents = 0
        guardrails_invoked = False

        def run(self, description: str, workspace: Path, budget: float) -> None:
            del description, workspace, budget

    arm = SoloArm(client_factory=_Client)
    run = arm.run(ScenarioContract(id="s", description="brief"), tmp_path / "solo", 3.0)
    assert run.status == "ok"
    assert (tmp_path / "solo" / "docs").is_dir()
    assert (tmp_path / "solo" / "src").is_dir()
    assert (tmp_path / "solo" / "tests").is_dir()
    assert (tmp_path / "solo" / "logs").is_dir()
    assert (tmp_path / "solo" / "docs" / "contracts").is_dir()


def test_sleeping_arm_is_budget_exhausted(tmp_path: Path) -> None:
    class _Slow:
        arm_id = "slow"

        def describe(self):  # noqa: ANN201
            from evals.arms.base import CostControls

            return ArmSpec(
                arm_id="slow",
                family="solo",
                cost_controls=CostControls(wall_clock_ceiling_s=0.05, spend_ceiling_usd=1.0),
            )

        def run(self, scenario, workspace, budget_usd):  # noqa: ANN001
            del scenario, budget_usd
            time.sleep(1.0)
            workspace.mkdir(parents=True, exist_ok=True)
            from datetime import UTC, datetime

            now = datetime.now(UTC)
            return ArmRun(
                arm_id="slow",
                sweep_id="",
                workspace=workspace,
                status="ok",
                started_at=now,
                ended_at=now,
            )

    run = run_arm_with_ceiling(_Slow(), ScenarioContract(id="s"), tmp_path / "slow")
    assert run.status == "budget_exhausted"


def test_dry_run_plan_and_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = resolve_plan("todo-api-beginner", ["solo", "ai_team"], 1)
    assert plan["dry_run"] is True
    assert plan["projected_usd"] > 0
    assert plan["arms"]
    with pytest.raises(SweepBudgetError):
        preflight_budget([get_arm("solo"), get_arm("ai_team")], n=10, ceiling=1.0)


def test_scenarios_without_ui_still_load() -> None:
    from evals.fixtures import load_scenario

    data = load_scenario("hello-world-smoke")
    contract = ScenarioContract.from_dict(data)
    assert contract.ui is None
    assert contract.id


def test_unknown_ablation_fails_loud() -> None:
    from evals.arms.ai_team import AiTeamArm

    with pytest.raises(ValueError, match="cannot ablate"):
        AiTeamArm(ablated=frozenset({"not-a-component"}))
    assert "smoke_gate" in ABLATABLE_COMPONENTS
