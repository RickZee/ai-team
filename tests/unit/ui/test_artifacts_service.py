"""Unit tests for artifact browser service."""

from __future__ import annotations

import json
import os

import pytest
from ai_team.ui.artifacts.service import (
    build_tree,
    load_architecture_panel,
    load_registry,
    load_tests_panel,
    read_artifact_file,
    resolve_run_workspace_dir,
    workspace_zip_bytes,
)


@pytest.fixture
def artifact_dirs(tmp_path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, str]:
    """Point workspace and output roots at tmp_path."""
    ws = tmp_path / "workspace"
    out = tmp_path / "output"
    ws.mkdir()
    out.mkdir()
    monkeypatch.setenv("PROJECT_WORKSPACE_DIR", str(ws))
    monkeypatch.setenv("PROJECT_OUTPUT_DIR", str(out))
    from ai_team.config.settings import reload_settings

    reload_settings()
    return "proj-1", str(ws)


def test_build_tree_workspace(artifact_dirs: tuple[str, str]) -> None:
    project_id, ws_root = artifact_dirs
    ws = os.path.join(ws_root, project_id)
    os.makedirs(os.path.join(ws, "src"), exist_ok=True)
    with open(os.path.join(ws, "src", "app.py"), "w", encoding="utf-8") as f:
        f.write("print('hi')\n")

    tree = build_tree(project_id, "workspace")
    assert len(tree) >= 1
    names = {n.name for n in tree}
    assert "src" in names


def test_resolve_run_workspace_dir_when_env_scoped_to_run(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scoped PROJECT_WORKSPACE_DIR must not double-append project_id."""
    run_ws = tmp_path / "workspace" / "run-abc"
    run_ws.mkdir(parents=True)
    monkeypatch.setenv("PROJECT_WORKSPACE_DIR", str(run_ws))
    from ai_team.config.settings import reload_settings

    (run_ws / "calc.py").write_text("print(1)\n", encoding="utf-8")
    reload_settings()
    assert resolve_run_workspace_dir("run-abc") == run_ws.resolve()
    tree = build_tree("run-abc", "workspace")
    assert len(tree) >= 1


def test_read_artifact_file(artifact_dirs: tuple[str, str]) -> None:
    project_id, ws_root = artifact_dirs
    ws = os.path.join(ws_root, project_id)
    os.makedirs(ws, exist_ok=True)
    path = os.path.join(ws, "readme.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Hello")

    content = read_artifact_file(project_id, "workspace", "readme.md")
    assert content.content == "# Hello"
    assert content.language == "markdown"


def test_sensitive_path_denied(artifact_dirs: tuple[str, str]) -> None:
    project_id, _ = artifact_dirs
    with pytest.raises(ValueError, match="Sensitive"):
        read_artifact_file(project_id, "workspace", ".env")


def test_load_registry_from_index(artifact_dirs: tuple[str, str], tmp_path) -> None:
    project_id, _ = artifact_dirs
    out = tmp_path / "output"
    runs = out / "runs" / project_id
    runs.mkdir(parents=True)
    (runs / "run.json").write_text(
        json.dumps(
            {
                "project_id": project_id,
                "backend": "langgraph",
                "team_profile": "full",
                "started_at": "2026-01-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    (out / "index.json").write_text(
        json.dumps(
            {
                "version": 1,
                "runs": [
                    {
                        "run_id": project_id,
                        "output_dir": str(runs),
                        "backend": "langgraph",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    rows = load_registry()
    assert any(r.run_id == project_id for r in rows)


def test_load_tests_panel(artifact_dirs: tuple[str, str], tmp_path) -> None:
    project_id, _ = artifact_dirs
    bundle = tmp_path / "output" / "runs" / project_id / "artifacts" / "testing"
    bundle.mkdir(parents=True)
    (bundle / "test_results.json").write_text(
        json.dumps(
            {
                "total": 3,
                "passed": 2,
                "failed": 1,
                "failures": [{"test_name": "test_x", "error": "assert 1==2"}],
            }
        ),
        encoding="utf-8",
    )

    panel = load_tests_panel(project_id)
    assert panel.passed == 2
    assert panel.failed == 1
    assert len(panel.failures) == 1


def test_load_architecture_markdown(artifact_dirs: tuple[str, str]) -> None:
    project_id, ws_root = artifact_dirs
    docs = os.path.join(ws_root, project_id, "docs")
    os.makedirs(docs, exist_ok=True)
    with open(os.path.join(docs, "architecture.md"), "w", encoding="utf-8") as f:
        f.write("# System\n\n```\n[A] -> [B]\n```")

    panel = load_architecture_panel(project_id)
    assert panel.markdown_fallback is not None
    assert "System" in panel.markdown_fallback


def test_workspace_zip(artifact_dirs: tuple[str, str]) -> None:
    project_id, ws_root = artifact_dirs
    ws = os.path.join(ws_root, project_id)
    os.makedirs(ws, exist_ok=True)
    with open(os.path.join(ws, "main.py"), "w", encoding="utf-8") as f:
        f.write("x = 1\n")

    data = workspace_zip_bytes(project_id)
    assert len(data) > 0
    assert data[:2] == b"PK"
