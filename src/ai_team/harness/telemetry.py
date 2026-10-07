"""Harness-owned run telemetry.

Records under ``output/runs/<run_id>/logs/``, beside ``run.json``. The agent
does not write these files. ``writer`` is stamped here, not by the caller, so
a call site cannot forge provenance.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_ZERO_SPEND: dict[str, Any] = {
    "budget_usd": 0.0,
    "spent_usd": 0.0,
    "total_tokens": 0,
    "calls": 0,
    "source": "finalize",
}


class TelemetryWriter:
    """Append-only harness telemetry for one run record."""

    def __init__(self, run_dir: Path) -> None:
        """Write under ``run_dir / logs``.

        Args:
            run_dir: The ``output/runs/<run_id>`` directory, not the workspace.
        """
        self._logs = run_dir / "logs"

    def run_total(self, spend: dict[str, Any] | None = None) -> None:
        """Append a ``run_total`` cost row. A missing spend is recorded as zero.

        Args:
            spend: Snapshot from the spend guard. ``None`` means the run made
                no model calls and must still appear as ``spent_usd: 0``.
        """
        payload = dict(spend if spend else _ZERO_SPEND)
        payload["kind"] = "run_total"
        payload["timestamp"] = datetime.now(UTC).isoformat()
        self._append("costs.jsonl", payload)

    def phase_start(self, phase: str, *, run_id: str, backend: str) -> None:
        """Append a ``phase_start`` row for one phase the graph actually entered.

        Args:
            phase: Phase name from the run's own phase history.
            run_id: Run id stamped on the row.
            backend: Backend name stamped on the row.
        """
        self._append(
            "phases.jsonl",
            {
                "phase": phase,
                "status": "phase_start",
                "timestamp": datetime.now(UTC).isoformat(),
                "run_id": run_id,
                "backend": backend,
            },
        )

    def phase_end(
        self,
        phase: str,
        *,
        end_status: str,
        run_id: str,
        backend: str,
    ) -> None:
        """Append a ``phase_end`` row. ``context_pressure`` stays null.

        A window size is not invented here. Checks that need pressure abstain
        instead of reading a guessed number.

        Args:
            phase: Phase name.
            end_status: Status the graph recorded (``complete``, ``error``, …).
            run_id: Run id stamped on the row.
            backend: Backend name stamped on the row.
        """
        self._append(
            "phases.jsonl",
            {
                "phase": phase,
                "status": "phase_end",
                "end_status": end_status,
                "timestamp": datetime.now(UTC).isoformat(),
                "run_id": run_id,
                "backend": backend,
                "context_pressure": None,
            },
        )

    def phases_from_history(
        self,
        history: list[Any],
        *,
        run_id: str,
        backend: str,
    ) -> None:
        """Write a start and an end row for each phase the graph recorded.

        Args:
            history: ``phase_history`` entries (``phase`` and ``status``).
            run_id: Run id stamped on every row.
            backend: Backend name stamped on every row.
        """
        for entry in history:
            if not isinstance(entry, dict):
                continue
            phase = entry.get("phase")
            if not isinstance(phase, str) or not phase:
                continue
            end_status = entry.get("status")
            self.phase_start(phase, run_id=run_id, backend=backend)
            self.phase_end(
                phase,
                end_status=end_status if isinstance(end_status, str) else "complete",
                run_id=run_id,
                backend=backend,
            )

    def _append(self, filename: str, row: dict[str, Any]) -> None:
        """Append one JSON line. ``writer`` is always ``harness``."""
        payload = dict(row)
        payload["writer"] = "harness"
        try:
            self._logs.mkdir(parents=True, exist_ok=True)
            with (self._logs / filename).open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, default=str) + "\n")
        except OSError as exc:
            logger.warning("telemetry_write_skipped", file=filename, error=str(exc))
