"""FM-001 bus invariant and salvage."""

from __future__ import annotations

from pathlib import Path

import pytest
from ai_team.harness.fm001 import fm001_violation, salvage_write
from ai_team.tools.bus import reset_bus
from ai_team.tools.kinds import ToolRequest


def test_fenced_code_without_write_is_violation() -> None:
    bus = reset_bus(empty=True)
    payload = fm001_violation(
        assistant_text="```python\nprint(1)\n```",
        bus=bus,
        phase="development",
    )
    assert payload is not None
    assert payload["fm_id"] == "FM-001"


def test_write_span_clears_violation() -> None:
    from ai_team.tools.bus import ToolSpec
    from ai_team.tools.kinds import ToolObservation
    from pydantic import BaseModel

    class Empty(BaseModel):
        pass

    def handler(args: dict, request: ToolRequest) -> ToolObservation:
        _ = args
        _ = request
        return ToolObservation(
            ok=True,
            code="ok",
            summary="wrote",
            tool="write_file",
            kind="write",
            risk_class="write",
        )

    bus = reset_bus(empty=True)
    bus.register(
        ToolSpec(
            name="write_file",
            kind="write",
            risk_class="write",
            args_schema=Empty,
            handler=handler,
        )
    )
    bus.invoke(ToolRequest(tool="write_file", args={}, phase="development"))
    payload = fm001_violation(
        assistant_text="```python\nprint(1)\n```",
        bus=bus,
        phase="development",
    )
    assert payload is None


@pytest.mark.bus_draft
def test_salvage_uses_bus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROJECT_WORKSPACE_DIR", str(tmp_path))
    monkeypatch.setenv("PROJECT_OUTPUT_DIR", str(tmp_path / "out"))
    (tmp_path / "out").mkdir()
    from ai_team.config.settings import reload_settings

    reload_settings()
    reset_bus()
    obs = salvage_write("src/x.py", "x=1\n", phase="development")
    assert obs.tool == "write_file"
    assert obs.ok is True
