"""Tests for ``scripts/monitor_output.load_latest_state``."""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

import pytest

# tests/unit/scripts/test_monitor_output.py -> repo root is parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_monitor_module() -> object:
    path = _REPO_ROOT / "scripts" / "monitor_output.py"
    spec = importlib.util.spec_from_file_location("monitor_output_script", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def monitor() -> object:
    return _load_monitor_module()


def test_load_latest_state_prefers_runs_and_latest_file(tmp_path: Path, monitor: object) -> None:
    load_latest_state = monitor.load_latest_state
    (tmp_path / "runs" / "abc").mkdir(parents=True)
    state_path = tmp_path / "runs" / "abc" / "state.json"
    state_path.write_text(json.dumps({"project_id": "abc", "current_phase": "complete"}))
    (tmp_path / "latest").write_text("abc\n", encoding="utf-8")
    legacy = tmp_path / "zzz_state.json"
    legacy.write_text(json.dumps({"project_id": "legacy"}))
    time.sleep(0.01)
    # Legacy file is newer on disk; resolver should still prefer latest + runs/
    legacy.write_text(json.dumps({"project_id": "legacy", "n": 2}))
    path, data = load_latest_state(tmp_path)
    assert path == state_path
    assert data is not None
    assert data.get("project_id") == "abc"


def test_load_latest_state_legacy_glob_when_no_registry(tmp_path: Path, monitor: object) -> None:
    load_latest_state = monitor.load_latest_state
    p = tmp_path / "myproj_state.json"
    p.write_text(json.dumps({"project_id": "myproj", "current_phase": "planning"}))
    path, data = load_latest_state(tmp_path)
    assert path == p
    assert data is not None and data.get("project_id") == "myproj"


def test_load_latest_state_returns_none_for_empty_dir(tmp_path: Path, monitor: object) -> None:
    load_latest_state = monitor.load_latest_state
    assert load_latest_state(tmp_path) == (None, None)


def test_load_latest_state_invalid_json_returns_path_and_none_data(
    tmp_path: Path, monitor: object
) -> None:
    load_latest_state = monitor.load_latest_state
    (tmp_path / "runs" / "bad").mkdir(parents=True)
    bad = tmp_path / "runs" / "bad" / "state.json"
    bad.write_text("not json {{{")
    (tmp_path / "latest").write_text("bad\n", encoding="utf-8")
    path, data = load_latest_state(tmp_path)
    assert path == bad
    assert data is None


def test_load_latest_state_falls_back_when_latest_points_to_missing_state(
    tmp_path: Path, monitor: object
) -> None:
    """If ``latest`` references a run dir without ``state.json``, use legacy glob."""
    load_latest_state = monitor.load_latest_state
    (tmp_path / "runs" / "ghost").mkdir(parents=True)
    (tmp_path / "latest").write_text("ghost\n", encoding="utf-8")
    leg = tmp_path / "solo_state.json"
    leg.write_text(json.dumps({"project_id": "solo"}))
    path, data = load_latest_state(tmp_path)
    assert path == leg
    assert data is not None and data.get("project_id") == "solo"
