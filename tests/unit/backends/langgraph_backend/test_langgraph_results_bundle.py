from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from ai_team.backends.langgraph_backend.backend import LangGraphBackend
from ai_team.config.settings import reload_settings
from ai_team.core.team_profile import TeamProfile


@dataclass
class _Snap:
    values: dict[str, Any]


class _DummyGraph:
    def __init__(self, final_state: dict[str, Any]) -> None:
        self._final_state = final_state

    def stream(self, initial_state: dict[str, Any], config: dict[str, Any], stream_mode: str):
        _ = initial_state, config, stream_mode
        yield {"planning": {"current_phase": "planning"}}

    def get_state(self, config: dict[str, Any]) -> _Snap:
        _ = config
        return _Snap(values=self._final_state)


def test_langgraph_stream_writes_results_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    out_root = tmp_path / "out"
    out_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PROJECT_OUTPUT_DIR", str(out_root))
    reload_settings()

    backend = LangGraphBackend()
    profile = TeamProfile(name="backend-api", agents=["manager"], phases=["intake"])

    final_state = {"project_id": "tid", "current_phase": "complete"}
    monkeypatch.setattr(backend, "_compile_for_run", lambda mode, cp: _DummyGraph(final_state))

    events = list(backend.iter_stream_events("x", profile, thread_id="tid", graph_mode="full"))
    assert any(e.get("type") == "langgraph_done" for e in events)

    run_json = out_root / "tid" / "run.json"
    state_json = out_root / "tid" / "state.json"
    events_jsonl = out_root / "tid" / "events.jsonl"
    assert run_json.exists()
    assert state_json.exists()
    assert events_jsonl.exists()

    state = json.loads(state_json.read_text(encoding="utf-8"))
    assert state["project_id"] == "tid"
