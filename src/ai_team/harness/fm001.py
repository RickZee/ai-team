"""FM-001 bus invariant: fenced code with zero write observations."""

from __future__ import annotations

import re
from typing import Any

from ai_team.tools.bus import ToolBus

_FENCE_RE = re.compile(r"```(?:\w+)?\n")


def has_fenced_code(text: str) -> bool:
    """True if *text* contains a markdown code fence."""
    return bool(_FENCE_RE.search(text or ""))


def fm001_violation(
    *,
    assistant_text: str,
    bus: ToolBus,
    phase: str | None = None,
) -> dict[str, Any] | None:
    """Return an error-span payload when the invariant fires, else None.

    A development/testing phase that emits fenced code and has zero successful
    write observations (``ok`` or ``drafted``) is FM-001.
    """
    if not has_fenced_code(assistant_text):
        return None
    writes = [
        s
        for s in bus.spans()
        if s.get("type") == "tool_result"
        and s.get("kind") in {"write", None}
        and s.get("code") in {"ok", "drafted"}
        and (phase is None or s.get("phase") == phase)
    ]
    # Also count any write tool_use that resulted in drafted/ok
    if writes:
        return None
    return {
        "type": "error",
        "fm_id": "FM-001",
        "phase": phase,
        "message": "phase produced fenced code with zero successful write-tool spans",
    }


def salvage_write(path: str, content: str, *, phase: str | None = None) -> Any:
    """Harness-originated write through the bus (auto-commit)."""
    from ai_team.tools.bus import get_bus
    from ai_team.tools.kinds import ToolRequest

    return get_bus().invoke(
        ToolRequest(
            tool="write_file",
            args={"path": path, "content": content},
            agent_role="_harness",
            phase=phase,
            auto_commit=True,
        )
    )
