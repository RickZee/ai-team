"""The script replays through ToolBus with no framework in the loop."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from ai_team.config.settings import scoped_workspace_dir
from ai_team.tools.bus import get_bus, reset_bus
from ai_team.tools.draft import commit_pending_drafts
from ai_team.tools.kinds import ToolRequest
from tests.conformance.fake_models import load_thin_slice, replay


def test_script_replay_writes_calc_and_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AI_TEAM_DRAFT_WRITES", "1")
    reset_bus()
    script = load_thin_slice()
    workspace = tmp_path / "ws"
    workspace.mkdir()

    def on_step(step: dict) -> None:
        if step.get("kind") != "tool":
            return
        args = step.get("args") if isinstance(step.get("args"), dict) else {}
        get_bus().invoke(
            ToolRequest(
                tool=str(step["tool"]),
                args=dict(args),
                agent_role=str(step.get("role") or ""),
                phase="development",
            )
        )

    with scoped_workspace_dir(str(workspace)):
        replay(script, on_step)
        commit_pending_drafts(phase="testing")

    assert (workspace / "calc.py").is_file()
    assert (workspace / "tests" / "test_calc.py").is_file()
    env = {**os.environ, "PYTHONPATH": str(workspace)}
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_calc.py",
            "-q",
            "--noconftest",
            "-o",
            "addopts=",
        ],
        cwd=workspace,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
