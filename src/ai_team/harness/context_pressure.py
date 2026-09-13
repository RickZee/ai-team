"""Context-window pressure: consumed tokens over usable window (R10.2)."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def context_pressure(
    used_tokens: int | None,
    window_tokens: int | None,
) -> float | None:
    """Return used/window in ``[0, 1]``, or ``None`` when either side is unknown.

    Never guess a window size. A missing value is ``None`` so
    ``CHK-premature-termination`` can return inconclusive instead of a false pass.
    """
    if used_tokens is None or window_tokens is None:
        return None
    if window_tokens <= 0:
        return None
    if used_tokens < 0:
        return None
    return min(1.0, float(used_tokens) / float(window_tokens))


def pressure_from_usage(
    usage: dict[str, Any] | None,
    *,
    window_tokens: int | None,
) -> float | None:
    """Derive pressure from an SDK usage mapping plus a known window."""
    if not usage:
        return context_pressure(None, window_tokens)
    inp = usage.get("input_tokens") or usage.get("prompt_tokens") or usage.get("input")
    out = usage.get("output_tokens") or usage.get("completion_tokens") or usage.get("output")
    try:
        used = (int(inp) if inp is not None else 0) + (int(out) if out is not None else 0)
    except (TypeError, ValueError):
        return None
    if inp is None and out is None:
        return None
    return context_pressure(used, window_tokens)


def configured_window_tokens() -> int | None:
    """Read an explicit window from the environment. Never invent a default."""
    raw = os.environ.get("AI_TEAM_CONTEXT_WINDOW_TOKENS", "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def emit_phase_end(
    workspace: Path,
    phase: str,
    *,
    used_tokens: int | None,
    status: str = "ok",
) -> None:
    """Append a ``phase_end`` row with ``context_pressure`` (possibly None)."""
    logs = workspace / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    row = {
        "phase": phase,
        "status": "phase_end",
        "timestamp": datetime.now(UTC).isoformat(),
        "context_pressure": context_pressure(used_tokens, configured_window_tokens()),
        "end_status": status,
    }
    with (logs / "phases.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
