"""Append extended-thinking blocks to ``workspace/logs/reasoning.jsonl``."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def append_thinking(
    workspace: Path,
    *,
    thinking: str,
    session_id: str | None = None,
    model: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Record one thinking block for audit."""
    log_dir = workspace / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "reasoning.jsonl"
    row = {
        "timestamp": datetime.now(UTC).isoformat(),
        "session_id": session_id,
        "model": model,
        "thinking": thinking[:50_000],
        **(extra or {}),
    }
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, default=str) + "\n")
    except OSError as e:
        logger.warning("claude_reasoning_log_write_failed", error=str(e))
