"""Reference-harness arm wrapping the vendored autonomous-coding quickstart (R3)."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.arms.base import ArmRun, ArmSpec, CostControls, Divergence, ScenarioContract
from evals.arms.registry import register

VENDOR_DIR = Path(__file__).resolve().parent / "vendor" / "autonomous_coding"
VENDOR_PIN = "3313e9716fb5b977248bcd06cb0cc86a8c547b9b"
MAX_FEATURES = 25
DEMO_SCRIPT = "autonomous_agent_demo.py"

WhichFn = Callable[[str], str | None]
RunFn = Callable[..., subprocess.CompletedProcess[str]]


class ReferenceArm:
    """Adapter around the vendored quickstart. The vendor tree is never edited."""

    arm_id = "reference"

    def __init__(
        self,
        *,
        which: WhichFn | None = None,
        runner: RunFn | None = None,
        vendor_dir: Path | None = None,
    ) -> None:
        self._which = which or shutil.which
        self._runner = runner
        self._vendor_dir = vendor_dir or VENDOR_DIR

    def describe(self) -> ArmSpec:
        """Reference spec: $8 / 90 min, feature cap 25, no internal spend ceiling."""
        return ArmSpec(
            arm_id=self.arm_id,
            family="reference",
            model_ids={"*": "configured-default"},
            harness_components=frozenset(),
            source_ref=f"vendor:{VENDOR_PIN[:7]}",
            cost_controls=CostControls(
                spend_ceiling_usd=8.0, wall_clock_ceiling_s=5400.0, max_sessions=1
            ),
            divergences=[
                Divergence(
                    field="max_features",
                    expected=200,
                    actual=MAX_FEATURES,
                    reason="R3.3: beginner scenarios do not need the 200-feature default",
                ),
                Divergence(
                    field="scenario_brief",
                    expected="thin 1-4 sentence brief",
                    actual="full scenario contract",
                    reason="v1 records detailed contracts as a known limitation (design §9.4)",
                ),
                Divergence(
                    field="internal_spend_ceiling",
                    expected="present",
                    actual="absent",
                    reason="expected FM-007 positive; adapter does not patch the vendor",
                ),
            ],
        )

    def _unavailable(self, workspace: Path, started: datetime, reason: str) -> ArmRun:
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / ".arm_id").write_text(self.arm_id, encoding="utf-8")
        (workspace / "logs").mkdir(exist_ok=True)
        (workspace / "logs" / "reference_unavailable.txt").write_text(reason, encoding="utf-8")
        return ArmRun(
            arm_id=self.arm_id,
            sweep_id="",
            workspace=workspace,
            status="unavailable",
            started_at=started,
            ended_at=datetime.now(UTC),
            cost_usd=0.0,
        )

    def _unavailability_cause(self) -> str | None:
        if not (self._vendor_dir / DEMO_SCRIPT).is_file():
            return "vendor tree missing"
        if self._which("claude") is None:
            return "claude CLI unavailable"
        if self._which("node") is None:
            return "node unavailable"
        if os.environ.get("AI_TEAM_REFERENCE_OFFLINE") == "1":
            return "network unavailable"
        return None

    def run(self, scenario: ScenarioContract, workspace: Path, budget_usd: float) -> ArmRun:
        """Write ``app_spec.txt`` and shell the demo, or return ``unavailable``."""
        del budget_usd
        started = datetime.now(UTC)
        cause = self._unavailability_cause()
        if cause:
            return self._unavailable(workspace, started, cause)

        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / ".arm_id").write_text(self.arm_id, encoding="utf-8")
        spec_path = workspace / "app_spec.txt"
        spec_path.write_text(scenario.description or scenario.id, encoding="utf-8")
        stdout_path = workspace / "logs"
        stdout_path.mkdir(exist_ok=True)
        cmd = [
            "python",
            str(self._vendor_dir / DEMO_SCRIPT),
            "--project-dir",
            str(workspace),
            "--max-iterations",
            str(MAX_FEATURES),
        ]
        try:
            if self._runner is not None:
                proc = self._runner(cmd, cwd=str(workspace))
            else:
                proc = subprocess.run(  # noqa: S603 — argument list, shell=False
                    cmd,
                    cwd=str(workspace),
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=self.describe().cost_controls.wall_clock_ceiling_s,
                )
        except subprocess.TimeoutExpired:
            ended = datetime.now(UTC)
            return ArmRun(
                arm_id=self.arm_id,
                sweep_id="",
                workspace=workspace,
                status="budget_exhausted",
                started_at=started,
                ended_at=ended,
                cost_usd=0.0,
            )
        except OSError as exc:
            return self._unavailable(workspace, started, f"subprocess: {exc}")

        (workspace / "logs" / "reference_stdout.txt").write_text(
            (proc.stdout or "") + "\n" + (proc.stderr or ""),
            encoding="utf-8",
        )
        status: str = "ok" if proc.returncode == 0 else "failed"
        return ArmRun(
            arm_id=self.arm_id,
            sweep_id="",
            workspace=workspace,
            status=status,  # type: ignore[arg-type]
            started_at=started,
            ended_at=datetime.now(UTC),
            cost_usd=0.0,
        )


def assemble_reference_spans(stdout: str, *, workspace: Path | None = None) -> dict[str, Any]:
    """Parse ``[Tool:]`` / ``[Done]`` / ``[BLOCKED]`` markers; never invent streams."""
    from datetime import UTC, datetime

    from evals.trace.models import Span

    now = datetime.now(UTC)
    spans: list[Span] = []
    warnings: list[str] = [
        "absent cost stream: reference harness emits no costs.jsonl",
        "absent guardrail stream: reference harness emits no guardrail_check spans",
    ]
    for i, line in enumerate(stdout.splitlines()):
        text = line.strip()
        if text.startswith("[Tool:"):
            name = text[6:].rstrip("]").strip()
            spans.append(
                Span(
                    span_id=f"ref_tool_{i:04d}",
                    type="tool_use",
                    t_start=now,
                    payload={"tool": name, "source": "reference_stdout"},
                )
            )
        elif text.startswith("[Done]"):
            spans.append(
                Span(
                    span_id=f"ref_done_{i:04d}",
                    type="phase_end",
                    t_start=now,
                    phase="development",
                    payload={"marker": "Done", "detail": text},
                )
            )
        elif text.startswith("[BLOCKED]"):
            spans.append(
                Span(
                    span_id=f"ref_blocked_{i:04d}",
                    type="error",
                    t_start=now,
                    payload={"marker": "BLOCKED", "detail": text},
                )
            )
    if workspace is not None:
        features = workspace / "feature_list.json"
        if not features.is_file():
            warnings.append("absent feature_list.json")
        progress = workspace / "claude-progress.txt"
        if not progress.is_file():
            warnings.append("absent claude-progress.txt")
    return {"spans": spans, "warnings": warnings}


def _factory() -> ReferenceArm:
    return ReferenceArm()


register("reference", _factory)
