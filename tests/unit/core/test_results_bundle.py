from __future__ import annotations

import json
from pathlib import Path

import pytest
from ai_team.config.settings import reload_settings
from ai_team.core.results import ResultsBundle
from ai_team.core.results.models import Scorecard


@pytest.fixture()
def isolated_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    out_root = tmp_path / "out"
    ws_root = tmp_path / "ws"
    out_root.mkdir(parents=True, exist_ok=True)
    ws_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PROJECT_OUTPUT_DIR", str(out_root))
    monkeypatch.setenv("PROJECT_WORKSPACE_DIR", str(ws_root))
    reload_settings()
    return out_root, ws_root


def test_results_bundle_creates_layout(isolated_dirs: tuple[Path, Path]) -> None:
    out_root, ws_root = isolated_dirs
    b = ResultsBundle("p1")
    meta = b.default_run_metadata(
        backend="test",
        team_profile="full",
        env="test",
        argv=["ai-team", "run", "x"],
    )
    b.write_run(meta)
    b.append_event({"type": "hello"})
    b.write_state({"current_phase": "complete"})
    b.write_summary("# Summary")
    b.write_scorecard(Scorecard(status="complete"))

    assert (out_root / "runs" / "p1" / "run.json").exists()
    assert (out_root / "runs" / "p1" / "events.jsonl").exists()
    assert (out_root / "runs" / "p1" / "state.json").exists()
    assert (out_root / "runs" / "p1" / "reports" / "summary.md").exists()
    assert (out_root / "index.json").exists()
    assert (out_root / "latest").read_text(encoding="utf-8").strip() == "p1"
    assert (ws_root / "p1").exists()


def test_index_json_structure_and_run_entries(isolated_dirs: tuple[Path, Path]) -> None:
    out_root, _ws = isolated_dirs
    b = ResultsBundle("indexed")
    meta = b.default_run_metadata(
        backend="crewai",
        team_profile="backend-api",
        env="prod",
        argv=["a", "b"],
    )
    b.write_run(meta)
    raw = (out_root / "index.json").read_text(encoding="utf-8")
    idx = json.loads(raw)
    assert idx["version"] == 1
    assert "updated_at" in idx
    assert len(idx["runs"]) == 1
    row = idx["runs"][0]
    assert row["run_id"] == "indexed"
    assert row["backend"] == "crewai"
    assert row["team_profile"] == "backend-api"
    assert "output_dir" in row and "indexed" in row["output_dir"]


def test_registry_multiple_runs_latest_points_to_most_recent(
    isolated_dirs: tuple[Path, Path],
) -> None:
    """Second run written after first should become ``latest`` and first row in index."""
    import time

    out_root, _ws = isolated_dirs
    b_first = ResultsBundle("first-run")
    b_first.write_run(b_first.default_run_metadata(backend="test", team_profile="a", env=None))
    b_first.write_state({"n": 1})
    time.sleep(0.02)
    b_second = ResultsBundle("second-run")
    b_second.write_run(b_second.default_run_metadata(backend="test", team_profile="b", env=None))
    b_second.write_state({"n": 2})

    assert (out_root / "latest").read_text(encoding="utf-8").strip() == "second-run"
    idx = json.loads((out_root / "index.json").read_text(encoding="utf-8"))
    assert {r["run_id"] for r in idx["runs"]} == {"first-run", "second-run"}
    assert idx["runs"][0]["run_id"] == "second-run"


def test_record_generated_file_and_manifest(isolated_dirs: tuple[Path, Path]) -> None:
    out_root, ws_root = isolated_dirs
    b = ResultsBundle("p2")
    (ws_root / "p2").mkdir(parents=True, exist_ok=True)
    (ws_root / "p2" / "app.py").write_text("print('hi')\n", encoding="utf-8")

    e = b.record_generated_file(rel_path="app.py", phase="development", agent_role="dev")
    b.write_code_manifest([e])

    manifest_path = out_root / "runs" / "p2" / "artifacts" / "development" / "code_manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload[0]["path"] == "app.py"
    assert payload[0]["bytes"] > 0
    assert isinstance(payload[0]["sha256"], str) and len(payload[0]["sha256"]) == 64
