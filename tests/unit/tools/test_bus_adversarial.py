"""Adversarial ToolBus tests: traversal, secrets, confirm-without-policy."""

from __future__ import annotations

from pathlib import Path

import pytest
from ai_team.tools.bus import get_bus, reset_bus
from ai_team.tools.kinds import ToolRequest

pytestmark = [pytest.mark.eval_unit, pytest.mark.bus_draft]


@pytest.fixture
def bus_ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ws = tmp_path / "workspace"
    out = tmp_path / "output"
    ws.mkdir()
    out.mkdir()
    monkeypatch.setenv("PROJECT_WORKSPACE_DIR", str(ws))
    monkeypatch.setenv("PROJECT_OUTPUT_DIR", str(out))
    from ai_team.config.settings import reload_settings

    reload_settings()
    reset_bus()
    yield ws
    reset_bus()


def test_path_traversal_does_not_write(bus_ws: Path) -> None:
    obs = get_bus().invoke(
        ToolRequest(tool="write_file", args={"path": "../outside.txt", "content": "nope"})
    )
    assert obs.ok is False
    assert obs.code in {"validation_failed", "error", "gated"}
    assert not (bus_ws.parent / "outside.txt").exists()


def test_env_write_gated(bus_ws: Path) -> None:
    obs = get_bus().invoke(
        ToolRequest(tool="write_file", args={"path": ".env", "content": "SECRET=1\n"})
    )
    assert obs.code == "gated"
    assert not (bus_ws / ".env").exists()


def test_shell_injection_shaped_gated_without_policy(bus_ws: Path) -> None:
    _ = bus_ws
    obs = get_bus().invoke(ToolRequest(tool="execute_shell", args={"command": "echo hi; rm -rf /"}))
    assert obs.code == "gated"


def test_confirm_true_delete_still_gated(bus_ws: Path) -> None:
    (bus_ws / "keep.txt").write_text("keep", encoding="utf-8")
    obs = get_bus().invoke(
        ToolRequest(tool="delete_file", args={"path": "keep.txt", "confirm": True})
    )
    assert obs.code == "gated"
    assert (bus_ws / "keep.txt").is_file()
