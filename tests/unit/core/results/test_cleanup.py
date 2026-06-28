from __future__ import annotations

import json
from pathlib import Path

import pytest
from ai_team.config.settings import reload_settings
from ai_team.core.results import ResultsBundle, delete_run, delete_runs, rebuild_registry
from ai_team.core.results.cleanup import validate_run_id


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


def _seed_run(out_root: Path, ws_root: Path, run_id: str) -> None:
    (ws_root / run_id).mkdir(parents=True)
    (ws_root / run_id / "app.py").write_text("x = 1\n", encoding="utf-8")
    bundle = ResultsBundle(run_id)
    bundle.write_run(bundle.default_run_metadata(backend="test", team_profile="full", env="test"))


def test_delete_run_removes_workspace_bundle_and_registry_entry(
    isolated_dirs: tuple[Path, Path],
) -> None:
    out_root, ws_root = isolated_dirs
    _seed_run(out_root, ws_root, "run-a")

    result = delete_run("run-a")

    assert result.run_id == "run-a"
    assert result.workspace_deleted is True
    assert result.bundle_deleted is True
    assert result.existed is True
    assert not (ws_root / "run-a").exists()
    assert not (out_root / "runs" / "run-a").exists()
    idx = json.loads((out_root / "index.json").read_text(encoding="utf-8"))
    assert idx["runs"] == []
    assert not (out_root / "latest").exists()


def test_delete_run_idempotent_when_missing(isolated_dirs: tuple[Path, Path]) -> None:
    out_root, _ws = isolated_dirs
    rebuild_registry(out_root)

    result = delete_run("missing-run")

    assert result.existed is False
    assert result.workspace_deleted is False
    assert result.bundle_deleted is False


def test_delete_one_of_two_runs_updates_registry(
    isolated_dirs: tuple[Path, Path],
) -> None:
    out_root, ws_root = isolated_dirs
    _seed_run(out_root, ws_root, "first")
    _seed_run(out_root, ws_root, "second")

    delete_run("second")

    idx = json.loads((out_root / "index.json").read_text(encoding="utf-8"))
    assert {r["run_id"] for r in idx["runs"]} == {"first"}
    assert (out_root / "latest").read_text(encoding="utf-8").strip() == "first"
    assert not (out_root / "runs" / "second").exists()
    assert (out_root / "runs" / "first").exists()


def test_delete_last_run_clears_latest(isolated_dirs: tuple[Path, Path]) -> None:
    out_root, ws_root = isolated_dirs
    _seed_run(out_root, ws_root, "only")
    assert (out_root / "latest").exists()

    delete_run("only")

    idx = json.loads((out_root / "index.json").read_text(encoding="utf-8"))
    assert idx["runs"] == []
    assert not (out_root / "latest").exists()


@pytest.mark.parametrize("bad_id", ["", "..", "a/b", r"a\b"])
def test_validate_run_id_rejects_unsafe_values(bad_id: str) -> None:
    with pytest.raises(ValueError, match="Invalid run_id"):
        validate_run_id(bad_id)


def test_delete_run_rejects_unsafe_run_id() -> None:
    with pytest.raises(ValueError, match="Invalid run_id"):
        delete_run("../escape")


def test_delete_runs_returns_one_result_per_id(isolated_dirs: tuple[Path, Path]) -> None:
    out_root, ws_root = isolated_dirs
    _seed_run(out_root, ws_root, "one")
    _seed_run(out_root, ws_root, "two")

    results = delete_runs(["one", "two", "ghost"])

    assert [r.run_id for r in results] == ["one", "two", "ghost"]
    assert results[0].existed is True
    assert results[1].existed is True
    assert results[2].existed is False
    idx = json.loads((out_root / "index.json").read_text(encoding="utf-8"))
    assert idx["runs"] == []
