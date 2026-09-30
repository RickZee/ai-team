"""Replay the thin-slice script through the harness.

Each backend calls :func:`scripted_result_or_none` when a conformance script
is injected. Tool calls go through ``ToolBus.invoke``, writes are committed
only by ``commit_pending_drafts``, and spend goes through ``record_usage``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from ai_team.backends.common.acceptance import apply_quality_gate_acceptance
from ai_team.config.settings import reload_settings, scoped_workspace_dir
from ai_team.core.result import ProjectResult
from ai_team.core.results import ResultsBundle
from ai_team.core.spend_guard import (
    BudgetExceededError,
    record_usage,
    reset_spend_guard,
)
from ai_team.core.team_profile import TeamProfile
from ai_team.tools.bus import get_bus
from ai_team.tools.draft import commit_pending_drafts
from ai_team.tools.kinds import ToolRequest

logger = structlog.get_logger(__name__)


@contextmanager
def _env(updates: dict[str, str]) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in updates}
    os.environ.update(updates)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        reload_settings()


def scripted_result_or_none(
    backend_name: str,
    description: str,
    profile: TeamProfile,
    kwargs: dict[str, Any],
) -> ProjectResult | None:
    """Run the injected script, or return None when this is a normal run."""
    script = kwargs.get("conformance_script")
    if not isinstance(script, dict):
        return None
    return run_scripted(backend_name, description, profile, kwargs)


def run_scripted(
    backend_name: str,
    description: str,
    profile: TeamProfile,
    options: dict[str, Any],
) -> ProjectResult:
    """Execute one thin-slice script and close the run record."""
    _ = description
    run_id = str(options.get("thread_id") or f"{backend_name}-thin")
    workspace = Path(str(options.get("workspace_dir") or f"workspace/{run_id}")).resolve()
    output_root = Path(str(options.get("output_dir") or "output")).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)
    updates = {
        "PROJECT_OUTPUT_DIR": str(output_root),
        "AI_TEAM_DRAFT_WRITES": "1",
    }
    with _env(updates), scoped_workspace_dir(str(workspace)):
        reload_settings()
        return _run_scoped(backend_name, profile, options, run_id, workspace)


def _run_scoped(
    backend_name: str,
    profile: TeamProfile,
    options: dict[str, Any],
    run_id: str,
    workspace: Path,
) -> ProjectResult:
    bundle = ResultsBundle(run_id, workspace_dir=workspace)
    started = datetime.now(UTC)
    model_tier = options.get("model_tier")
    extra: dict[str, Any] = {}
    if isinstance(model_tier, str) and model_tier:
        extra["model_tier"] = model_tier
    bundle.write_run(
        bundle.default_run_metadata(
            backend=backend_name,
            team_profile=profile.name,
            env=None,
            extra=extra,
            started_at=started,
        )
    )
    wall = options.get("wall_clock_s")
    if isinstance(wall, int | float) and float(wall) <= 0:
        return _close(bundle, backend_name, profile, run_id, workspace, "timeout", started)

    budget = options.get("run_budget_usd")
    reset_spend_guard(budget if isinstance(budget, int | float) else 0, run_id=run_id)
    spend = float(options.get("force_spend_usd") or 0.0)
    try:
        record_usage(spend, 12)
    except BudgetExceededError as exc:
        logger.info("conformance_budget_exceeded", error=str(exc))
        return _close(bundle, backend_name, profile, run_id, workspace, "budget_exceeded", started)

    _write_llm_row(bundle)
    script = options.get("conformance_script")
    verdicts = _invoke_steps(script if isinstance(script, dict) else {}, backend_name, run_id)
    commit_pending_drafts(phase="testing")
    tests_passed = True if options.get("skip_pytest") else _pytest(workspace)
    apply_quality_gate_acceptance(
        workspace,
        tests_passed=tests_passed,
        qa_verdicts=verdicts,
    )
    return _close(
        bundle, backend_name, profile, run_id, workspace, "complete", started, tests_passed
    )


def _invoke_steps(script: dict[str, Any], backend_name: str, run_id: str) -> dict[str, str]:
    verdicts: dict[str, str] = {}
    for step in script.get("steps") or []:
        if not isinstance(step, dict):
            continue
        kind = str(step.get("kind") or "")
        if kind == "tool":
            raw_args = step.get("args")
            args = dict(raw_args) if isinstance(raw_args, dict) else {}
            get_bus().invoke(
                ToolRequest(
                    tool=str(step.get("tool") or ""),
                    args=args,
                    agent_role=str(step.get("role") or "") or None,
                    phase="development",
                    backend=backend_name,
                    run_id=run_id,
                )
            )
        elif kind == "verdict":
            verdicts[str(step.get("criterion_id") or "")] = str(step.get("verdict") or "")
    return {key: value for key, value in verdicts.items() if key}


def _write_llm_row(bundle: ResultsBundle) -> None:
    path = bundle.output_dir / "logs" / "costs.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "timestamp": datetime.now(UTC).isoformat(),
        "phase": "development",
        "kind": "llm",
        "cost_usd": 0.0,
        "usage": {"input_tokens": 8, "output_tokens": 4},
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def _pytest(workspace: Path) -> bool:
    if not (workspace / "tests" / "test_calc.py").is_file():
        return False
    env = {**os.environ, "PYTHONPATH": str(workspace)}
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_calc.py",
            "-q",
            "--noconftest",
            "-p",
            "no:cacheprovider",
            "-o",
            "addopts=",
        ],
        cwd=workspace,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    logger.info("thin_slice_pytest", returncode=proc.returncode)
    return proc.returncode == 0


def _close(
    bundle: ResultsBundle,
    backend_name: str,
    profile: TeamProfile,
    run_id: str,
    workspace: Path,
    status: str,
    started: datetime,
    tests_passed: bool | None = None,
) -> ProjectResult:
    _ = started
    bundle.finalize(
        completed_at=datetime.now(UTC),
        final_status=status,
        spend={"usd": 0.0, "source": "spend_guard"},
        backend=backend_name,
    )
    ok = status == "complete" and tests_passed is not False
    return ProjectResult(
        backend_name=backend_name,
        success=ok,
        team_profile=profile.name,
        error=None if ok else status,
        raw={
            "final_status": status,
            "run_id": run_id,
            "output_dir": str(bundle.output_dir),
            "workspace_dir": str(workspace),
            "tests_passed": tests_passed,
        },
    )
