"""Keep the record of a run that was stopped mid-graph.

The run_demo watchdog's ``DemoTimeoutError`` and the spend guard's stop unwind
out of a graph's ``invoke``, so the code that writes ``state.json`` and the
phase log after a normal return never runs. The seven September timeouts left
a cost row and no state, and their cause could not be read. This writes the
checkpointer's last state instead.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any, Protocol

from ai_team.harness.telemetry import TelemetryWriter


class CheckpointedGraph(Protocol):
    """The one call this module needs from a compiled LangGraph graph."""

    def get_state(self, config: Any, *, subgraphs: bool = False) -> Any:
        """Return the latest checkpoint snapshot for ``config``."""


class StateBundle(Protocol):
    """The run-record writer: where ``state.json`` and ``logs/`` live."""

    @property
    def output_dir(self) -> Path:
        """The ``output/runs/<run_id>`` directory."""

    def write_state(self, state: dict[str, Any]) -> Path:
        """Write ``state.json``."""


def save_stopped_run(
    graph: CheckpointedGraph,
    config: dict[str, Any],
    bundle: StateBundle,
    *,
    run_id: str,
    backend: str,
    stop: BaseException,
) -> None:
    """Write the last checkpoint of a stopped run, then return.

    ``state.json`` gets the checkpoint values plus ``stopped_by`` (the
    exception type) and ``stopped_in`` (the nodes that were running, with a
    subgraph's messages when the checkpointer kept them). ``phases.jsonl``
    gets the phases the graph had recorded. Best effort: this runs inside the
    watchdog's grace period and must never replace the original stop with an
    error of its own, so every failure is swallowed.
    """
    with contextlib.suppress(Exception):
        snapshot = graph.get_state(config, subgraphs=True)
        values: dict[str, Any] = dict(snapshot.values or {})
        values["stopped_by"] = type(stop).__name__
        running: list[dict[str, Any]] = []
        for task in snapshot.tasks or ():
            entry: dict[str, Any] = {"node": task.name}
            sub_values = getattr(getattr(task, "state", None), "values", None)
            if isinstance(sub_values, dict) and sub_values.get("messages"):
                entry["messages"] = sub_values["messages"]
            running.append(entry)
        values["stopped_in"] = running
        bundle.write_state(values)
        TelemetryWriter(bundle.output_dir).phases_from_history(
            list(values.get("phase_history") or []),
            run_id=run_id,
            backend=backend,
        )
